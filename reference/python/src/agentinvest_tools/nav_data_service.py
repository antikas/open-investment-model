"""The ``navData`` Python Restate service — the NAV-strike workflow's marts-read seam.

The ``navCalculation`` workflow (TS) journals a NAV strike as durable steps over the
COMPONENTS of the canonical fund NAV. The components live in the dbt-built ``mart_fund_nav``
mart, read by the Python data layer (duckdb). This service is the thin cross-language seam:
the TS workflow calls ``navData/getFundNavComponents({fundId})`` over Restate, and this
handler reads the components from ``mart_fund_nav`` (the §A1 NAV identity SSOT) and returns
them as exact decimal STRINGS (no float drift across the boundary).

Topology: ``navData`` is a model-free Restate *service* — a namespace + dispatch
boundary in the Python tool+data layer — NOT an "agent". It carries no reasoning loop. The
single orchestrating loop is the planner's ``.plan()``; the NAV strike is a durable
*workflow* (a reusable orchestration), and this service is the data tool it reads.

The read is wrapped in ``ctx.run`` so the marts read is a journaled durable step: on a
crash/replay the read result is read back from the journal, the store is NOT re-queried
(replay-grade reproducibility — the same components feed the same struck NAV).

SYNTHETIC, NOT A STRUCK PRODUCTION NAV. The components are the synthetic data-layer §A1
NAV, not a fiduciary published NAV (oracle-anchored production is the named arc).
"""

from __future__ import annotations

from typing import Any, TypedDict

import restate
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from restate.exceptions import TerminalError

from agentinvest_demo.marts import MartsUnavailableError
from agentinvest_demo.nav_marts_read import (
    read_fund_holdings_gross,
    read_fund_nav_components,
)
from agentinvest_tools.request_serde import PassThroughJsonSerde

NAV_DATA_SERVICE_NAME = "navData"


class FundNavComponentsRequest(BaseModel):
    """Wire shape of the request — the fund to strike, optionally as-of a knowledge date.

    ``fundId`` is required; ``navKnowledgeDate`` is optional. A non-null ``navKnowledgeDate``
    is REFUSED on the wire (the latest-holdings bound): the latest-holdings path cannot soundly strike
    a PAST as-of NAV, so the handler forwards the date to the read and the refusal fires as a
    clean ``TerminalError`` (422) — never a silently-struck current NAV under a past-date
    request.

    A **Pydantic model** with ``extra="forbid"`` (not a bare ``TypedDict``): an UNRECOGNISED
    request key is a clean ``TerminalError`` (400) at the handler, never silently ignored. The
    silent-mis-key gap this closes: a caller passing snake_case ``nav_knowledge_date`` instead
    of the contract field ``navKnowledgeDate`` used to get a CURRENT NAV with no error (the
    off-contract key was dropped); it now fails loud. The valid contract keys are unchanged —
    only unknown keys now reject. ``navKnowledgeDate`` defaults to ``None`` so it stays genuinely
    optional on the wire; ``fundId`` is required.
    """

    model_config = ConfigDict(extra="forbid")

    fundId: str = Field(description="The fund to strike (required).")
    navKnowledgeDate: str | None = Field(
        default=None,
        description="Optional as-of knowledge date; a non-null past date is refused (422).",
    )


class FundNavComponentsResult(TypedDict):
    """Wire shape of the per-fund NAV components — exact decimal strings (no float drift).

    ``grossMarketValue + accruedIncome - fees`` recomputes ``navUsd`` to the penny (the
    §A1 identity the TS workflow asserts at roll-up). ``navUsd`` is the mart's PUBLISHED
    value, so the workflow's struck NAV reconciles to ``mart_fund_nav`` by construction.
    """

    fundId: str
    fundName: str
    shareClass: str | None
    nPositions: int
    grossMarketValue: str
    accruedIncome: str
    fees: str
    navUsd: str
    computedBy: str


class FundHoldingsGrossRequest(BaseModel):
    """Wire shape of the holdings-roll-up request — the fund whose positions to roll up.

    A **Pydantic model** with ``extra="forbid"``: an unrecognised request key is a clean
    ``TerminalError`` (400) at the handler, never silently ignored (the same fiduciary-surface
    reject-unknown-keys hardening as ``FundNavComponentsRequest``). ``fundId`` is required.
    """

    model_config = ConfigDict(extra="forbid")

    fundId: str = Field(description="The fund whose positions to roll up (required).")


class FundHoldingsGrossResult(TypedDict):
    """Wire shape of the fund's gross market value rolled up from ``mart_portfolio_holdings``.

    ``holdingsGrossMarketValue`` is Σ each held position's ``market_value_usd`` from the
    HOLDINGS mart — an INDEPENDENT mart / SQL path from ``mart_fund_nav``'s gross. The
    workflow reconciles this against the fund-NAV mart's gross (the genuine cross-mart check).
    """

    fundId: str
    fundName: str
    nPositions: int
    holdingsGrossMarketValue: str
    computedBy: str


navData = restate.Service(NAV_DATA_SERVICE_NAME)


def _coerce_request[ModelT: BaseModel](
    req: Any, model: type[ModelT], handler_name: str
) -> ModelT:
    """Validate the raw request body against ``model`` (``extra="forbid"``), or fail terminal 400.

    A valid body is either an already-built ``model`` instance (a programmatic / typed-ingress path)
    or a plain ``dict`` (the pass-through-serde / unit-test path); the dict is validated through
    ``model.model_validate`` so an UNRECOGNISED request key (the silent-mis-key class) is a clean
    ``TerminalError`` (400), not a silently-dropped off-contract key. A non-dict body is likewise a
    clean 400. Run in the HANDLER BODY (not the serde — the SDK re-wraps a serde error as a
    status-less 500); the message is kept clean of build cruft (it can reach a consumer surface).
    """
    if isinstance(req, model):
        return req
    if not isinstance(req, dict):
        raise TerminalError(
            f"{handler_name}: request body must be a JSON object — got {type(req).__name__}",
            status_code=400,
        )
    try:
        return model.model_validate(req)
    except ValidationError as exc:
        raise TerminalError(
            f"{handler_name}: invalid request — {exc.error_count()} error(s): {exc}",
            status_code=400,
        ) from exc


@navData.handler(name="getFundNavComponents", input_serde=PassThroughJsonSerde())
async def get_fund_nav_components(
    ctx: restate.Context, req: FundNavComponentsRequest
) -> FundNavComponentsResult:
    """Read the per-fund §A1 NAV components from ``mart_fund_nav`` for a CURRENT strike.

    Wrapped in ``ctx.run`` so the marts read is a journaled durable step (replay reads the
    components back, the store is not re-queried). A missing fund / unprovisioned store / a
    REFUSED past-as-of date is a ``TerminalError`` (a deterministic data condition — no
    retry-storm), surfaced cleanly to the workflow so it aborts rather than retries.

    ``navKnowledgeDate`` IS forwarded to the read: a non-null value drives the latest-holdings
    refusal (a past-as-of strike on the latest-holdings path is UNSOUND) → a clean 422 on the
    wire, matching the contract's honest boundary. The field must be forwarded, not dropped —
    dropping it would let a past date silently return the CURRENT NAV.

    An UNRECOGNISED request key is a clean ``TerminalError`` (400) before the read (the
    reject-unknown-keys hardening): a caller mis-keying the request (e.g. snake_case
    ``nav_knowledge_date``) fails loud rather than silently striking a current NAV. The valid
    keys — the current strike AND the past-as-of refusal — are unchanged.
    """

    request = _coerce_request(req, FundNavComponentsRequest, "getFundNavComponents")
    fund_id = request.fundId
    nav_knowledge_date = request.navKnowledgeDate

    def _read() -> FundNavComponentsResult:
        try:
            c = read_fund_nav_components(fund_id, nav_knowledge_date=nav_knowledge_date)
        except MartsUnavailableError as exc:
            # A deterministic data condition (no fund / no store / past-as-of refused) — a
            # terminal error so Restate does NOT retry it; the workflow surfaces it cleanly.
            raise TerminalError(str(exc), status_code=422) from exc
        return {
            "fundId": c.fund_id,
            "fundName": c.fund_name,
            "shareClass": c.share_class,
            "nPositions": c.n_positions,
            "grossMarketValue": str(c.gross_market_value),
            "accruedIncome": str(c.accrued_income),
            "fees": str(c.fees),
            "navUsd": str(c.nav_usd),
            "computedBy": "python:navData",
        }

    return await ctx.run("read-fund-nav-components", _read)


@navData.handler(name="getFundHoldingsGross", input_serde=PassThroughJsonSerde())
async def get_fund_holdings_gross(
    ctx: restate.Context, req: FundHoldingsGrossRequest
) -> FundHoldingsGrossResult:
    """Roll up the fund's gross market value from ``mart_portfolio_holdings`` — independently.

    The workflow's load-positions step reads THIS (Σ the held positions' market values from
    the HOLDINGS mart) and reconciles it against ``mart_fund_nav.gross_market_value`` — two
    marts, two SQL paths, a falsifiable cross-mart check (NOT the within-row tautology).
    Wrapped in ``ctx.run`` so the read is a journaled durable step (replay reads it back).
    A missing fund / unprovisioned store is a ``TerminalError`` (422) — surfaced cleanly.

    An UNRECOGNISED request key is a clean ``TerminalError`` (400) before the read (the
    reject-unknown-keys hardening); the valid ``fundId`` path is unchanged.
    """

    request = _coerce_request(req, FundHoldingsGrossRequest, "getFundHoldingsGross")
    fund_id = request.fundId

    def _read() -> FundHoldingsGrossResult:
        try:
            h = read_fund_holdings_gross(fund_id)
        except MartsUnavailableError as exc:
            raise TerminalError(str(exc), status_code=422) from exc
        return {
            "fundId": h.fund_id,
            "fundName": h.fund_name,
            "nPositions": h.n_positions,
            "holdingsGrossMarketValue": str(h.holdings_gross_market_value),
            "computedBy": "python:navData",
        }

    return await ctx.run("read-fund-holdings-gross", _read)
