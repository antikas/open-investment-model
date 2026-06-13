"""The ``bd12`` model-free Restate dispatch service — the BD-12 book-of-record read boundary.

This is the BD-12 (Investment Operations & Servicing) entry on the *service* axis: a model-free
Restate service that hosts the SD-12.1 IBOR + SD-12.2 ABOR **read** tool catalogue and dispatches a
*named* Service Operation to its tool as a journaled durable step. It is the ``bd09_service.py``
analogue — same ``execute_so`` / ``list_capabilities`` envelope shape — so the MCP/OpenAPI ingress
and the orchestrator reach it identically.

Service, not agent (the load-bearing topology point). The per-BD layer is a **model-free dispatch /
tool-hosting boundary** that carries **no reasoning loop**. It routes a *named* SO to its read tool;
it does **not** decide which SO to call (that is the one orchestrating ``.plan()`` loop). It also
does **not reconcile** the two books — it exposes each book to be read; the reconciliation engine is
a separate service. And it writes **nothing**: every handler is strictly read-only.

The I/O distinction. Unlike ``bd09`` (pure compute), the
``bd12`` tools are **I/O-touching** — each reads the canonical dual book through the
``book_of_record_data`` data-access layer at the requested as-of, then maps the typed rows onto the
pure tool's input and runs the tool. So the error classification distinguishes two classes:

- a **deterministic** failure — a Pydantic ``ValidationError`` on the request args (unknown/missing
  arg under ``extra="forbid"``), an unknown ``book`` / unknown SO, or any other deterministic
  condition (a ``MartsUnavailableError`` — the store is not provisioned, the portfolio has no rows)
  — is a ``TerminalError`` (Restate does not retry a failure that re-running cannot fix);
- there is **no genuinely-transient** failure surface in this read path against a local duckdb file
  (a missing store / missing portfolio is a deterministic data condition, not a recoverable blip),
  so ``MartsUnavailableError`` is classified **terminal** (422), consistent with the ``navData`` /
  ``canonicalData`` read seams. A future I/O tool against a networked store would raise a typed
  *retryable* error this layer lets propagate.

The read is wrapped in ``ctx.run`` so the canonical read + the tool shaping is a journaled durable
step: on a crash/replay the result is read back from the journal, the store is NOT re-queried
(replay-grade reproducibility — the same as-of read feeds the same result).

Provenance is replay-safe by construction: the metadata is derived solely from the request and the
tool's deterministic output (the so_id, the tool name). No wall-clock or other non-deterministic
source is read inside the journaled step.

Honest boundary: this wires the *synthetic* BD-12 read surface over the durable substrate. A green
dispatch proves typed-dispatch + the canonical read + the as-of plumbing + the IBOR/ABOR divergence;
it is **not** a production book-of-record service and **not** a read against a live custodian.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, TypedDict

import restate
import restate.serde
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from restate.exceptions import TerminalError

from agentinvest_demo.book_of_record_data import (
    latest_struck_book_date,
    read_cash_flows,
    read_pending_activity,
    read_positions,
    read_transactions,
)
from agentinvest_demo.marts import MartsUnavailableError
from agentinvest_tools.bd12 import (
    AccruedIncomeRow,
    CashFlowRow,
    CostBasisRow,
    PendingTransaction,
    PositionRow,
    ReadAccruedIncomeInput,
    ReadAccruedIncomeOutput,
    ReadBookCloseStateInput,
    ReadBookCloseStateOutput,
    ReadCashExposureInput,
    ReadCashExposureOutput,
    ReadCashFlowsInput,
    ReadCashFlowsOutput,
    ReadCostBasisInput,
    ReadCostBasisOutput,
    ReadPendingActivityInput,
    ReadPendingActivityOutput,
    ReadPositionInput,
    ReadPositionOutput,
    ReadTransactionsInput,
    ReadTransactionsOutput,
    TransactionRow,
    UnsettledTradeLeg,
    read_abor_accrued_income,
    read_abor_book_close_state,
    read_abor_cost_basis,
    read_cash_flow_events,
    read_ibor_cash_and_exposure,
    read_ibor_pending_activity,
    read_position,
)
from agentinvest_tools.bd12 import (
    read_transactions as run_read_transactions,
)

BD12_SERVICE_NAME = "bd12"

# A reused exact-zero Decimal for the sum() identity / a missing cost basis (no float, no per-call
# Decimal(0) churn). The reads are exact-decimal end-to-end (no float drift across the boundary).
_ZERO = Decimal(0)


class ReadRequest(BaseModel):
    """The abstract read request the orchestrator emits — a book, a portfolio, an as-of date.

    The BD-12 read tools take their rows from the data-access layer, so the *request* is abstract
    (which book / portfolio / as-of to read), not the concrete rows. ``book`` is required for the
    book-discriminated reads (position / cash+exposure / accruals / cost-basis / book-close);
    ``portfolio_id`` is required for every portfolio-scoped read; ``as_of_date`` defaults to the
    canonical book date. ``extra="forbid"`` — an unrecognised arg is a deterministic 400.
    """

    model_config = ConfigDict(extra="forbid")

    book: str = Field(default="", description="The book of record — 'ibor' or 'abor'.")
    portfolio_id: str = Field(default="", description="The portfolio to read.")
    as_of_date: str = Field(
        default="2026-03-31", description="The as-of date (defaults to the canonical book date)."
    )


@dataclass(frozen=True)
class ToolSpec:
    """One registry entry — a named Service Operation bound to its read tool + canonical reader.

    ``read_and_run`` is the per-SO closure that (1) reads the canonical layer via the data-access
    layer at the request's as-of, (2) maps the typed rows onto the pure tool's input, (3) runs the
    tool, and (4) returns the typed output. ``input_model`` / ``output_model`` are the pure tool's
    Pydantic I/O models — the source of truth for the catalogue + the MCP/OpenAPI surfaces.
    ``books`` names which books the SO applies to (for the catalogue + a clean unknown-book error).
    """

    so_id: str
    name: str
    summary: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    read_and_run: Callable[[ReadRequest], BaseModel]
    books: tuple[str, ...]


# --- the per-SO read+run closures: read the canonical layer, map rows, run the pure tool ----------


def _require_book(req: ReadRequest, allowed: tuple[str, ...]) -> str:
    if req.book not in allowed:
        raise MartsUnavailableError(
            f"book {req.book!r} is not valid for this read — expected one of {list(allowed)}."
        )
    return req.book


def _require_portfolio(req: ReadRequest) -> str:
    if not req.portfolio_id:
        raise MartsUnavailableError(
            "this read needs a portfolio_id (the abstract 'portfolio_id' arg is missing) — "
            "surfaced as a clean failure, never a fabricated read."
        )
    return req.portfolio_id


def _as_of(req: ReadRequest) -> date:
    return date.fromisoformat(req.as_of_date)


def _read_position(req: ReadRequest) -> ReadPositionOutput:
    book = _require_book(req, ("ibor", "abor"))
    pf = _require_portfolio(req)
    rows = read_positions(book, pf, req.as_of_date)
    return read_position(
        ReadPositionInput(
            book=book,  # type: ignore[arg-type]
            portfolio_id=pf,
            as_of_date=_as_of(req),
            rows=tuple(
                PositionRow(
                    position_id=r.position_id,
                    book=r.book,  # type: ignore[arg-type]
                    portfolio_id=r.portfolio_id,
                    instrument_id=r.instrument_id,
                    instrument_name=r.instrument_name,
                    asset_class_code=r.asset_class_code,
                    as_of_date=r.as_of_date,
                    quantity=r.quantity,
                    commitment_usd=r.commitment_usd,
                    cost_basis_usd=r.cost_basis_usd,
                    market_value_usd=r.market_value_usd,
                    accrued_income_usd=r.accrued_income_usd,
                    currency=r.currency,
                )
                for r in rows
            ),
        )
    )


def _read_ibor_cash_and_exposure(req: ReadRequest) -> ReadCashExposureOutput:
    _require_book(req, ("ibor",))
    pf = _require_portfolio(req)
    positions = read_positions("ibor", pf, req.as_of_date)
    gross_mv = sum((p.market_value_usd for p in positions), _ZERO)
    pending = read_pending_activity(pf, req.as_of_date)
    # The realised (settled) cash for the portfolio = Σ the realised E-06 cash flows up to the
    # as-of.
    cash_flows = read_cash_flows(pf, req.as_of_date)
    settled_cash = sum((cf.amount for cf in cash_flows), _ZERO)
    return read_ibor_cash_and_exposure(
        ReadCashExposureInput(
            portfolio_id=pf,
            as_of_date=_as_of(req),
            settled_cash_usd=settled_cash,
            gross_market_value_usd=gross_mv,
            unsettled_legs=tuple(
                UnsettledTradeLeg(
                    transaction_id=t.transaction_id,
                    instrument_id=t.instrument_id,
                    settlement_date=t.settlement_date,
                    amount_usd=t.amount_usd,
                )
                for t in pending
                if t.settlement_date is not None
            ),
        )
    )


def _read_ibor_pending_activity(req: ReadRequest) -> ReadPendingActivityOutput:
    _require_book(req, ("ibor",))
    pf = _require_portfolio(req)
    pending = read_pending_activity(pf, req.as_of_date)
    return read_ibor_pending_activity(
        ReadPendingActivityInput(
            portfolio_id=pf,
            as_of_date=_as_of(req),
            transactions=tuple(
                PendingTransaction(
                    transaction_id=t.transaction_id,
                    transaction_type=t.transaction_type,
                    portfolio_id=t.portfolio_id,
                    instrument_id=t.instrument_id,
                    trade_date=t.trade_date,
                    settlement_date=t.settlement_date,
                    quantity=t.quantity,
                    amount_usd=t.amount_usd,
                    status=t.status,  # type: ignore[arg-type]
                )
                for t in pending
                if t.settlement_date is not None
            ),
        )
    )


def _read_transactions(req: ReadRequest) -> ReadTransactionsOutput:
    pf = _require_portfolio(req)
    rows = read_transactions(pf, req.as_of_date)
    return run_read_transactions(
        ReadTransactionsInput(
            portfolio_id=pf,
            as_of_date=_as_of(req),
            rows=tuple(
                TransactionRow(
                    transaction_id=r.transaction_id,
                    transaction_type=r.transaction_type,
                    portfolio_id=r.portfolio_id,
                    instrument_id=r.instrument_id,
                    trade_date=r.trade_date,
                    settlement_date=r.settlement_date,
                    quantity=r.quantity,
                    amount_usd=r.amount_usd,
                    status=r.status,
                    source=r.source,
                )
                for r in rows
            ),
        )
    )


def _read_cash_flows(req: ReadRequest) -> ReadCashFlowsOutput:
    pf = _require_portfolio(req)
    rows = read_cash_flows(pf, req.as_of_date)
    return read_cash_flow_events(
        ReadCashFlowsInput(
            portfolio_id=pf,
            as_of_date=_as_of(req),
            rows=tuple(
                CashFlowRow(
                    cash_flow_id=r.cash_flow_id,
                    portfolio_id=r.portfolio_id,
                    instrument_id=r.instrument_id,
                    transaction_id=r.transaction_id,
                    cash_flow_date=r.cash_flow_date,
                    cash_flow_type=r.cash_flow_type,
                    direction=r.direction,
                    amount=r.amount,
                    currency=r.currency,
                    source=r.source,
                )
                for r in rows
            ),
        )
    )


def _read_abor_accrued_income(req: ReadRequest) -> ReadAccruedIncomeOutput:
    _require_book(req, ("abor",))
    pf = _require_portfolio(req)
    positions = read_positions("abor", pf, req.as_of_date)
    return read_abor_accrued_income(
        ReadAccruedIncomeInput(
            portfolio_id=pf,
            as_of_date=_as_of(req),
            rows=tuple(
                AccruedIncomeRow(
                    position_id=p.position_id,
                    portfolio_id=p.portfolio_id,
                    instrument_id=p.instrument_id,
                    accrued_income_usd=p.accrued_income_usd,
                    currency=p.currency,
                )
                for p in positions
                if p.accrued_income_usd is not None
            ),
        )
    )


def _read_abor_cost_basis(req: ReadRequest) -> ReadCostBasisOutput:
    _require_book(req, ("abor",))
    pf = _require_portfolio(req)
    positions = read_positions("abor", pf, req.as_of_date)
    return read_abor_cost_basis(
        ReadCostBasisInput(
            portfolio_id=pf,
            as_of_date=_as_of(req),
            rows=tuple(
                CostBasisRow(
                    position_id=p.position_id,
                    portfolio_id=p.portfolio_id,
                    instrument_id=p.instrument_id,
                    cost_basis_usd=p.cost_basis_usd if p.cost_basis_usd is not None else _ZERO,
                    market_value_usd=p.market_value_usd,
                    unrealised_gain_usd=p.market_value_usd
                    - (p.cost_basis_usd if p.cost_basis_usd is not None else _ZERO),
                    currency=p.currency,
                )
                for p in positions
            ),
        )
    )


def _read_abor_book_close_state(req: ReadRequest) -> ReadBookCloseStateOutput:
    _require_book(req, ("abor",))
    struck = latest_struck_book_date("abor")
    return read_abor_book_close_state(
        ReadBookCloseStateInput(as_of_date=_as_of(req), latest_struck_book_date=struck)
    )


# The registered BD-12 read tool catalogue — the SD-12.1 IBOR + SD-12.2 ABOR Service Operations.
# Each so_id maps to its read+run closure plus the pure tool's Pydantic models. Adding a BD-12 read
# tool is one row here; the dispatch, the catalogue and the schemas all derive from it.
_REGISTRY: dict[str, ToolSpec] = {
    spec.so_id: spec
    for spec in (
        ToolSpec(
            so_id="SO-12.1-01",
            name="read_ibor_position",
            summary="The IBOR (real-time) position per portfolio, as of a date.",
            input_model=ReadRequest,
            output_model=ReadPositionOutput,
            read_and_run=_read_position,
            books=("ibor",),
        ),
        ToolSpec(
            so_id="SO-12.1-02",
            name="read_ibor_cash_and_exposure",
            summary="The IBOR projected cash + exposure incl. the cash impact of unsettled trades.",
            input_model=ReadRequest,
            output_model=ReadCashExposureOutput,
            read_and_run=_read_ibor_cash_and_exposure,
            books=("ibor",),
        ),
        ToolSpec(
            so_id="SO-12.1-03",
            name="read_ibor_pending_activity",
            summary="The IBOR pending activity — the agreed-but-unsettled (in-flight) trades.",
            input_model=ReadRequest,
            output_model=ReadPendingActivityOutput,
            read_and_run=_read_ibor_pending_activity,
            books=("ibor",),
        ),
        ToolSpec(
            so_id="SO-12.1-04",
            name="read_transaction",
            summary="The E-05 Transaction records the book is built from (per portfolio, as-of).",
            input_model=ReadRequest,
            output_model=ReadTransactionsOutput,
            read_and_run=_read_transactions,
            books=("ibor", "abor"),
        ),
        ToolSpec(
            so_id="SO-12.1-05",
            name="read_cash_flow_event",
            summary="The E-06 Cash Flow Event records (per portfolio, as-of).",
            input_model=ReadRequest,
            output_model=ReadCashFlowsOutput,
            read_and_run=_read_cash_flows,
            books=("ibor", "abor"),
        ),
        ToolSpec(
            so_id="SO-12.2-01",
            name="read_abor_position",
            summary="The ABOR (accounting-basis) position per portfolio, as of a date.",
            input_model=ReadRequest,
            output_model=ReadPositionOutput,
            read_and_run=_read_position,
            books=("abor",),
        ),
        ToolSpec(
            so_id="SO-12.2-02",
            name="read_abor_accrued_income",
            summary="The ABOR accrued income (the accrual the IBOR book does not carry).",
            input_model=ReadRequest,
            output_model=ReadAccruedIncomeOutput,
            read_and_run=_read_abor_accrued_income,
            books=("abor",),
        ),
        ToolSpec(
            so_id="SO-12.2-03",
            name="read_abor_cost_basis",
            summary="The ABOR cost basis / unrealised gain (per portfolio, as-of).",
            input_model=ReadRequest,
            output_model=ReadCostBasisOutput,
            read_and_run=_read_abor_cost_basis,
            books=("abor",),
        ),
        ToolSpec(
            so_id="SO-12.2-04",
            name="read_abor_book_close_state",
            summary="The ABOR book-close (period-lock) state, derived from the struck-book date.",
            input_model=ReadRequest,
            output_model=ReadBookCloseStateOutput,
            read_and_run=_read_abor_book_close_state,
            books=("abor",),
        ),
    )
}


class ExecuteSoInput(BaseModel):
    """The ``execute_so`` request envelope — a named SO plus its abstract read args.

    A **Pydantic model** so the Restate auto-generated OpenAPI/MCP surface derives a real typed
    request schema. ``soId`` is the Service-Operation identifier (e.g. ``"SO-12.1-01"``); ``args``
    is
    the abstract read request (book / portfolio / as_of) mapped onto ``ReadRequest`` inside the
    journaled step. The envelope is permissive on ``args`` (the per-tool validation belongs to
    ``ReadRequest``'s ``extra="forbid"``); the envelope only types the transport shape.
    """

    model_config = ConfigDict(extra="forbid")

    soId: str = Field(description="The Service-Operation identifier to dispatch, e.g. 'SO-12.1-01'")
    args: dict[str, Any] = Field(
        default_factory=dict,
        description="The abstract read args (book / portfolio_id / as_of_date) as a JSON object.",
    )


class ExecuteSoProvenance(TypedDict):
    """Replay-safe provenance — derived from the request + the tool's deterministic output."""

    soId: str
    tool: str


class ExecuteSoOutput(TypedDict):
    """The ``execute_so`` result envelope — the typed read result plus provenance."""

    result: dict[str, Any]
    provenance: ExecuteSoProvenance
    computedBy: str


class CapabilityDescriptor(TypedDict):
    """One catalogue entry — a named SO with its I/O JSON schema + the books it applies to."""

    soId: str
    name: str
    summary: str
    books: list[str]
    inputSchema: dict[str, Any]
    outputSchema: dict[str, Any]


class ListCapabilitiesOutput(TypedDict):
    """The ``list_capabilities`` result — the registered BD-12 read tool catalogue."""

    service: str
    capabilities: list[CapabilityDescriptor]


bd12 = restate.Service(BD12_SERVICE_NAME)


class ExecuteSoEnvelopeSerde(restate.serde.Serde[Any]):
    """A permissive pass-through JSON deserialiser so the in-handler envelope guard owns the status.

    The ``bd09`` precedent: the Restate SDK re-wraps a serde-raised exception as a status-less 500,
    so the serde must NEVER raise — it parses the body and returns the raw value (a dict, or a
    non-dict for a malformed body) for the handler's ``_coerce_envelope`` to classify as a clean
    terminal 400. The handler keeps its typed ``ExecuteSoInput`` annotation, so the auto-generated
    OpenAPI/MCP surface stays typed.
    """

    def deserialize(self, buf: bytes) -> Any:
        if not buf:
            return {}
        try:
            return json.loads(buf)
        except Exception:
            # Never raise (the SDK re-wraps a serde error as a status-less 500). Any parse failure
            # returns the raw decoded text as a non-dict str so ``_coerce_envelope`` rejects it as a
            # clean terminal 400 via its non-dict branch.
            return buf.decode("utf-8", errors="replace")

    def serialize(self, obj: Any) -> bytes:
        if obj is None:
            return b""
        return json.dumps(obj).encode("utf-8")


def _dispatch(spec: ToolSpec, args: dict[str, Any]) -> ExecuteSoOutput:
    """Validate the args, read the canonical layer, run the read tool, and shape the result.

    Runs inside the journaled ``ctx.run`` step. The classification:

    - a Pydantic ``ValidationError`` mapping ``args`` onto ``ReadRequest`` (unknown/missing/mistyped
      arg under ``extra="forbid"``) is a **terminal 400** — a deterministic input error;
    - a ``MartsUnavailableError`` from the canonical read (the store is not provisioned, an unknown
      book, a missing portfolio, a bad as-of date) is a **terminal 422** — a deterministic data
      condition that re-running cannot fix (the read path against a local duckdb file has no
      genuinely-transient surface — the same classification as the ``navData`` / ``canonicalData``
      read seams). A future networked-store I/O tool would raise a typed *retryable* error this
      layer
      lets propagate instead;
    - any other deterministic compute failure (a bad date string → ``ValueError``) is a terminal
    422.

    The tool is **read-only** — it reads the canonical layer and shapes the result; it never writes,
    never mutates, produces no E-24, and never reads the comparator feed.
    """
    try:
        request = ReadRequest.model_validate(args)
    except ValidationError as exc:
        raise TerminalError(
            f"{spec.so_id} ({spec.name}): invalid arguments — {exc.error_count()} error(s): {exc}",
            status_code=400,
        ) from exc

    try:
        output = spec.read_and_run(request)
    except MartsUnavailableError as exc:
        # A deterministic data condition (no store / unknown book / missing portfolio / no rows) —
        # terminal so Restate does NOT retry it; the orchestrator surfaces it as a clean step
        # failure.
        raise TerminalError(
            f"{spec.so_id} ({spec.name}): {exc}",
            status_code=422,
        ) from exc
    except (ValueError, TypeError, KeyError) as exc:
        # Any other deterministic compute failure (e.g. a malformed as-of date) — terminal, never a
        # retry storm. The read path is deterministic against the local store, so terminal is safe.
        raise TerminalError(
            f"{spec.so_id} ({spec.name}): {type(exc).__name__}: {exc}",
            status_code=422,
        ) from exc

    return {
        "result": output.model_dump(mode="json"),
        "provenance": {"soId": spec.so_id, "tool": spec.name},
        "computedBy": f"python:{BD12_SERVICE_NAME}",
    }


def _coerce_envelope(req: Any) -> dict[str, Any]:
    """Validate the request body against the published envelope schema, or fail terminal 400.

    The ``bd09`` precedent: a valid body is either an ``ExecuteSoInput`` model (the typed Restate
    ingress path) or a plain ``dict`` (the programmatic / unit-test path) validated through
    ``ExecuteSoInput`` (``extra="forbid"`` + ``soId`` string). A non-dict body, an extra top-level
    key, a non-string / missing ``soId`` is a clean ``TerminalError`` (400) — run in the handler
    body
    so the 400 is not re-wrapped by the SDK as a status-less 500.
    """
    if isinstance(req, ExecuteSoInput):
        return req.model_dump()
    if not isinstance(req, dict):
        raise TerminalError(
            f"execute_so: request body must be a JSON object with 'soId' and 'args' — "
            f"got {type(req).__name__}",
            status_code=400,
        )
    try:
        envelope = ExecuteSoInput.model_validate(req)
    except ValidationError as exc:
        raise TerminalError(
            f"execute_so: invalid request envelope — {exc.error_count()} error(s): {exc}",
            status_code=400,
        ) from exc
    return envelope.model_dump()


@bd12.handler(name="execute_so", input_serde=ExecuteSoEnvelopeSerde())
async def execute_so(ctx: restate.Context, req: ExecuteSoInput) -> ExecuteSoOutput:
    """Dispatch a named BD-12 read Service Operation to its tool as a journaled durable step.

    Model-free dispatch — it routes the *named* ``soId`` to its registered read tool; it does not
    decide which SO to call (that is the orchestrator's ``.plan()`` loop). The read + the tool
    shaping
    runs inside the journaled step (replay reads the result back, the store is not re-queried).

    Strictly read-only — every registered SO reads the canonical dual book and shapes a
    typed
    result; none writes, mutates, produces an E-24 break, or reads the comparator feed. An unknown
    ``soId`` is a terminal 404; a bad/extra/missing arg or a deterministic data condition is
    terminal
    (400 / 422) — never a retry storm.
    """
    envelope = _coerce_envelope(req)

    so_id = envelope.get("soId")
    spec = _REGISTRY.get(so_id) if so_id is not None else None
    if spec is None:
        raise TerminalError(
            f"unknown Service Operation '{so_id}' — registered: {sorted(_REGISTRY)}",
            status_code=404,
        )

    args = envelope.get("args", {})

    # The read + tool call is a journaled durable step. _dispatch classifies every deterministic
    # failure as a TerminalError before it escapes the step, so Restate records a terminal failure
    # (no retry) rather than retrying a deterministic error forever.
    return await ctx.run(f"so-{spec.so_id}", lambda: _dispatch(spec, args))


@bd12.handler(name="list_capabilities")
async def list_capabilities(ctx: restate.Context) -> ListCapabilitiesOutput:
    """Return the registered BD-12 read tool catalogue — each so_id with its real I/O JSON schema.

    The schemas are the live Pydantic ``model_json_schema()`` of each tool's input (the abstract
    ``ReadRequest``) and output, the single source the MCP and OpenAPI surfaces generate from.
    Read-only; no journaled step (it derives from the static registry). Arity-0 — called with an
    empty request body over the ingress.
    """
    capabilities: list[CapabilityDescriptor] = [
        {
            "soId": spec.so_id,
            "name": spec.name,
            "summary": spec.summary,
            "books": list(spec.books),
            "inputSchema": spec.input_model.model_json_schema(),
            "outputSchema": spec.output_model.model_json_schema(),
        }
        for spec in _REGISTRY.values()
    ]
    return {"service": BD12_SERVICE_NAME, "capabilities": capabilities}
