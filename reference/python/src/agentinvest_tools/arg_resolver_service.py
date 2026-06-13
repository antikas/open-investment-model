"""The ``argResolver`` Python Restate service — the abstract-arg → concrete-tool-input seam.

The orchestrator's planning step (the one ``.plan()`` loop) emits a plan whose steps name a
tool (``soId``) and ABSTRACT args (``fund``, ``period``, a sector/asset-class axis) — the
planner cannot know the concrete begin/end NAV or the per-segment weights, those live in the
canonical marts. The DISPATCH step needs the tools' CONCRETE inputs (SO-09-01's begin/end NAV
+ flows; SO-09-05's per-segment weights+returns). This service is the cross-language seam that
bridges the two: given a fund + a window it READS the OIM-111 marts and DERIVES the concrete
inputs both BD-09 return tools need.

REUSE, NOT RE-IMPLEMENTATION (the SSOT point). The derivation is OIM-115's: the demo's
``read_fund_window`` (the single marts join → the per-segment + fund begin/end NAV, cross-checked
against ``mart_fund_nav``) and the demo's ``_total_return_args`` / ``_breakdown_args`` (the
``FundWindowData`` → the SO-09-01 / SO-09-05 input dicts). This service IMPORTS those functions
from ``agentinvest_demo`` — it does not re-implement the marts read or the input derivation. The
OIM-115 demo resolved the args BY HAND in an explicit two-step script; this service is that same
derivation moved into the orchestrator's flow so the chain runs AUTONOMOUSLY (the planner decides
the tools; this resolves their args; dispatch runs them).

Topology (ADR-0054): ``argResolver`` is a model-free Restate *service* — a data tool boundary in
the Python tool+data layer. It carries NO reasoning loop. It is sibling to ``navData`` (the
NAV-strike workflow's marts-read seam) and ``bd09`` (the dispatch service) on the service axis.

HONESTLY BOUNDED TO THE BD-09 RETURN TOOLS (v0.1). The resolver knows how to derive the inputs
for SO-09-01 (total return) and SO-09-05 (contribution breakdown) — the OIM-115 demo's two tools.
A request for any other ``soId`` is a clean ``TerminalError`` (a deterministic "I cannot resolve
this tool's args" — the orchestrator surfaces it as a CLEAN STEP FAILURE, never fabricated inputs).
A general resolver for the ~900-tool catalogue is forward (OIM-120+). NEVER fabricate inputs: if
the marts cannot resolve a step (an unknown tool, a missing fund, an unbuilt store) the resolver
fails LOUD — no fake data driving a real-looking attribution.

The read is wrapped in ``ctx.run`` so the marts read is a journaled durable step: on a
crash/replay the resolved args are read back from the journal, the store is NOT re-queried
(replay-grade reproducibility — the same resolution feeds the same dispatch).

SYNTHETIC, NOT PRODUCTION. The resolved inputs are derived from the synthetic marts; a green
resolution proves the abstract-arg→concrete-input plumbing, not a production attribution.
"""

from __future__ import annotations

from typing import Any, TypedDict

import restate
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from restate.exceptions import TerminalError

# REUSE OIM-115's derivation — the marts read AND the FundWindowData → tool-input mappings. These
# are the demo's by-hand resolution functions; this service moves them into the orchestrator flow.
from agentinvest_demo.marts import (
    DEFAULT_BEGIN_DATE,
    DEFAULT_END_DATE,
    MartsUnavailableError,
    read_fund_window,
)
from agentinvest_demo.phase2_demo import _breakdown_args, _total_return_args
from agentinvest_tools.request_serde import PassThroughJsonSerde

ARG_RESOLVER_SERVICE_NAME = "argResolver"

# The BD-09 return tools this v0.1 resolver knows how to resolve (the OIM-115 demo's two tools).
# Mapped to the demo's derivation function that produces each tool's concrete input dict from the
# shared FundWindowData. Any soId NOT in this map is a clean "cannot resolve" terminal failure —
# the honest v0.1 bound (a general ~900-tool resolver is forward), never a fabricated input.
_RESOLVABLE_SO_IDS = ("SO-09-01", "SO-09-05")

# The BD-12 book-of-record READ tools this resolver knows how to resolve (OIM-161, added
# INCREMENTALLY — the standing decision). Unlike the BD-09 return tools, the BD-12 read args are
# ABSTRACT by design — the bd12 service reads the canonical rows itself — so the resolver derives
# the read request ({book, portfolio_id, as_of_date}) from the plan step WITHOUT a marts read: book
# is implied by the SO (the SD-12.1 IBOR SOs read 'ibor'; the SD-12.2 ABOR SOs read 'abor'; the two
# entity reads default to 'ibor', the owning book), the portfolio comes from the plan, the as-of
# defaults to the canonical book date. This stays additive to the BD-09 derivation above.
_BD12_DEFAULT_AS_OF = "2026-03-31"
_BD12_IBOR_SO_IDS = ("SO-12.1-01", "SO-12.1-02", "SO-12.1-03", "SO-12.1-04", "SO-12.1-05")
_BD12_ABOR_SO_IDS = ("SO-12.2-01", "SO-12.2-02", "SO-12.2-03", "SO-12.2-04")
_BD12_RESOLVABLE_SO_IDS = _BD12_IBOR_SO_IDS + _BD12_ABOR_SO_IDS
# SO-12.2-04 (book-close state) is book-scoped but portfolio-AGNOSTIC (it reads the struck-book
# date, not a portfolio); every other BD-12 read needs a portfolio.
_BD12_NO_PORTFOLIO_SO_IDS = ("SO-12.2-04",)

# The SD-12.10 RECONCILE tools (OIM-162, added INCREMENTALLY — the standing decision). The
# reconcile args are abstract by design (an as-of snapshot over the firm-wide internal book +
# comparator feed), and the reconcile is firm-wide (NOT portfolio-scoped — the comparator is a
# firm-wide feed), so the resolver derives the reconcile request ({as_of_date}) from the plan step
# WITHOUT a marts read and WITHOUT a portfolio. The as-of defaults to the canonical book date.
# Additive to the BD-09/BD-12 resolution above.
_BD12_RECON_SO_IDS = ("SO-12.10-01", "SO-12.10-02", "SO-12.10-03", "SO-12.10-04")

# The SD-12.10 PROPOSE-ONLY cause-proposer (OIM-162 cycle-2, added INCREMENTALLY + additively). Its
# args are abstract ({as_of_date, capture}) — the bd12Recon service gathers the `unexplained`
# residue itself — so the resolver derives only the run scope, like the reconcile resolver. Kept
# separate from `_BD12_RECON_SO_IDS` so the reconcile resolver (the four SOs) is byte-unperturbed.
_BD12_PROPOSER_SO_ID = "SO-12.10-05"


class ResolveStepArgsRequest(BaseModel):
    """Wire shape of a resolve request — one plan step's tool + the abstract window args.

    ``soId`` is the tool the plan step selected; ``fundId`` / ``beginDate`` / ``endDate`` are the
    plan's abstract window args (the fund + the period the attribution is over). ``beginDate`` /
    ``endDate`` default to the OIM-115 demo's one-year window when omitted, so a plan that names a
    fund but not an explicit window resolves over the canonical window. ``fundId`` is required.

    A **Pydantic model** with ``extra="forbid"`` (not a bare ``TypedDict``): an UNRECOGNISED
    request key is a clean ``TerminalError`` (400) at the handler, never silently ignored — the
    same fiduciary-surface reject-unknown-keys hardening as the ``navData`` request contracts. The
    valid keys are unchanged (the existing v0.1-bound refusal and the missing-fund refusal still
    fire as 422). ``soId`` / ``fundId`` default to empty so the existing in-handler refusals own
    those messages; ``beginDate`` / ``endDate`` default to ``None`` so the canonical-window
    default still applies.
    """

    model_config = ConfigDict(extra="forbid")

    soId: str = Field(default="", description="The tool the plan step selected.")
    fundId: str = Field(default="", description="The fund the attribution is over (BD-09 tools).")
    beginDate: str | None = Field(default=None, description="Window start (defaults to canonical).")
    endDate: str | None = Field(default=None, description="Window end (defaults to canonical).")
    # The BD-12 book-of-record read args (OIM-161, additive). ``portfolioId`` is the portfolio the
    # read is over; ``book`` overrides the SO-implied book; ``asOfDate`` overrides the canonical
    # book date. All optional so the BD-09 path is byte-unchanged — read only for a BD-12 SO.
    portfolioId: str = Field(default="", description="The portfolio the BD-12 read is over.")
    book: str | None = Field(default=None, description="Override the SO-implied book (ibor/abor).")
    asOfDate: str | None = Field(default=None, description="Override the canonical as-of date.")


class ResolveStepArgsResult(TypedDict):
    """Wire shape of the resolved concrete tool inputs + the window provenance.

    ``args`` is the tool's CONCRETE input dict (ready to dispatch to ``bd09.execute_so`` for
    ``soId``), derived from the marts. ``fundId`` / ``fundName`` / ``beginDate`` / ``endDate`` /
    ``periodDays`` echo the resolved window so the orchestrator + the aggregate can carry it. The
    money figures inside ``args`` are exact decimal STRINGS (no float drift across the boundary —
    the OIM-115 derivation already serialises them as strings).
    """

    soId: str
    fundId: str
    fundName: str
    beginDate: str
    endDate: str
    periodDays: int
    beginNav: str
    endNav: str
    args: dict[str, Any]
    computedBy: str


argResolver = restate.Service(ARG_RESOLVER_SERVICE_NAME)


def _coerce_request(req: Any) -> ResolveStepArgsRequest:
    """Validate the raw body against ``ResolveStepArgsRequest`` (``extra="forbid"``), or fail 400.

    A valid body is either an already-built ``ResolveStepArgsRequest`` (a typed-ingress path) or a
    plain ``dict`` (the pass-through-serde / unit-test path); the dict is validated through
    ``model_validate`` so an UNRECOGNISED request key is a clean ``TerminalError`` (400), never a
    silently-dropped off-contract arg. A non-dict body is likewise a clean 400. Run in the HANDLER
    BODY (the SDK re-wraps a serde error as a status-less 500); the message is clean of build cruft.
    """
    if isinstance(req, ResolveStepArgsRequest):
        return req
    if not isinstance(req, dict):
        raise TerminalError(
            f"resolveStepArgs: request body must be a JSON object — got {type(req).__name__}",
            status_code=400,
        )
    try:
        return ResolveStepArgsRequest.model_validate(req)
    except ValidationError as exc:
        raise TerminalError(
            f"resolveStepArgs: invalid request — {exc.error_count()} error(s): {exc}",
            status_code=400,
        ) from exc


@argResolver.handler(name="resolveStepArgs", input_serde=PassThroughJsonSerde())
async def resolve_step_args(
    ctx: restate.Context, req: ResolveStepArgsRequest
) -> ResolveStepArgsResult:
    """Resolve one plan step's abstract window args into the tool's concrete inputs from the marts.

    Reads the OIM-111 marts via the OIM-115 derivation (``read_fund_window``) and derives the
    concrete input dict for the step's ``soId`` (SO-09-01 begin/end NAV via ``_total_return_args``;
    SO-09-05 per-segment weights+returns via ``_breakdown_args`` — both REUSED from the demo). The
    read is wrapped in ``ctx.run`` so the resolution is a journaled durable step (replay reads it
    back, the store is not re-queried).

    Clean failures, never fabricated inputs (the honest v0.1 bound + the OIM-131 partial-failure
    discipline):
      - an ``soId`` the v0.1 resolver does not know how to resolve (anything but SO-09-01/05) is a
        ``TerminalError`` (422) — the orchestrator surfaces it as a CLEAN step failure (a general
        resolver is forward), NOT a guessed input;
      - a missing fund / an unbuilt store / a window with no data is a ``MartsUnavailableError`` →
        a ``TerminalError`` (422), surfaced cleanly. The chain fails LOUD rather than dispatch a
        tool on fabricated data.

    An UNRECOGNISED request key is a clean ``TerminalError`` (400) before the resolution (the
    reject-unknown-keys hardening): a mis-keyed abstract arg fails loud rather than silently
    resolving over a wrong/default window. The valid keys are unchanged.
    """
    request = _coerce_request(req)
    so_id = request.soId
    fund_id = request.fundId
    begin_date = request.beginDate or DEFAULT_BEGIN_DATE
    end_date = request.endDate or DEFAULT_END_DATE

    if so_id not in _RESOLVABLE_SO_IDS:
        # The v0.1 honest bound: the resolver derives inputs only for the BD-09 return tools the
        # OIM-115 derivation covers. An unknown/unresolvable tool is a deterministic terminal
        # failure (no retry storm) — the orchestrator surfaces it cleanly, never fabricating args.
        raise TerminalError(
            f"argResolver cannot resolve args for {so_id!r}: this resolver derives inputs only "
            f"for the performance-return tools {list(_RESOLVABLE_SO_IDS)}. This step surfaces as a "
            f"clean failure rather than dispatching on fabricated inputs.",
            status_code=422,
        )

    if not fund_id:
        raise TerminalError(
            "argResolver: the plan step has no resolvable fund (the abstract 'fundId' arg is "
            "missing) — cannot derive the tool's inputs from the marts. Surfaced as a clean "
            "failure, not a fabricated input.",
            status_code=422,
        )

    def _resolve() -> ResolveStepArgsResult:
        try:
            # REUSE: the OIM-115 marts join → the per-segment + fund begin/end NAV (cross-checked
            # against mart_fund_nav). NOT re-implemented here.
            data = read_fund_window(fund_id=fund_id, begin_date=begin_date, end_date=end_date)
        except MartsUnavailableError as exc:
            # A deterministic data condition (no fund / no store / incomplete window) — terminal,
            # so Restate does NOT retry it; the orchestrator surfaces it as a clean step failure.
            raise TerminalError(str(exc), status_code=422) from exc
        except ValueError as exc:
            # A bad window (end <= begin) — deterministic, terminal.
            raise TerminalError(f"argResolver: {exc}", status_code=422) from exc

        # REUSE: the OIM-115 demo's FundWindowData → tool-input derivations. SO-09-01 takes the
        # fund begin/end NAV + period + (empty) flows; SO-09-05 takes the per-segment weights +
        # returns. The orchestrator dispatches these concrete dicts to bd09.execute_so.
        if so_id == "SO-09-01":
            args = _total_return_args(data)
        else:  # SO-09-05 (guarded above)
            args = _breakdown_args(data)

        return {
            "soId": so_id,
            "fundId": data.fund_id,
            "fundName": data.fund_name,
            "beginDate": data.begin_date,
            "endDate": data.end_date,
            "periodDays": data.period_days,
            "beginNav": str(data.begin_nav),
            "endNav": str(data.end_nav),
            "args": args,
            "computedBy": f"python:{ARG_RESOLVER_SERVICE_NAME}",
        }

    return await ctx.run(f"resolve-{so_id}-{fund_id}", _resolve)


# --- BD-12 book-of-record read resolution (OIM-161, incremental + additive)
# ------------------------


class ResolveBd12StepArgsResult(TypedDict):
    """The resolved BD-12 read request args + the read provenance.

    ``args`` is the abstract read request dict ({book, portfolio_id, as_of_date}) ready to dispatch
    to ``bd12.execute_so`` for ``soId`` — the bd12 service reads the canonical rows itself, so the
    resolver derives the read scope, NOT concrete rows (which is why this is a no-marts-read
    resolution, distinct from the BD-09 window derivation). ``book`` echoes the resolved book.
    """

    soId: str
    book: str
    portfolioId: str
    asOfDate: str
    args: dict[str, Any]
    computedBy: str


def _bd12_book_for_so(so_id: str, override: str | None) -> str:
    """The book a BD-12 read SO applies to — the explicit override, else the SO-implied book.

    The SD-12.1 IBOR SOs read 'ibor'; the SD-12.2 ABOR SOs read 'abor'; the two shared entity reads
    (SO-12.1-04 transaction / SO-12.1-05 cash-flow, owned by SD-12.1) default to 'ibor'. An explicit
    ``book`` override wins (validated to 'ibor'/'abor'); an invalid override is a clean terminal
    422.
    """
    if override is not None:
        if override not in ("ibor", "abor"):
            raise TerminalError(
                f"argResolver: book {override!r} is invalid — expected 'ibor' or 'abor'.",
                status_code=422,
            )
        return override
    return "abor" if so_id in _BD12_ABOR_SO_IDS else "ibor"


@argResolver.handler(name="resolveBd12StepArgs", input_serde=PassThroughJsonSerde())
async def resolve_bd12_step_args(
    ctx: restate.Context, req: ResolveStepArgsRequest
) -> ResolveBd12StepArgsResult:
    """Resolve a BD-12 book-of-record read step into the bd12 read request args (SO-12.1/12.2).

    The incremental BD-12 resolution (the standing per-tool-incremental decision). The BD-12 read
    args are abstract by design — the bd12 service reads the canonical dual book itself — so this
    resolver derives the read SCOPE ({book, portfolio_id, as_of_date}) from the plan step WITHOUT a
    marts read: the book is implied by the SO (IBOR SOs → 'ibor', ABOR SOs → 'abor', overridable),
    the portfolio comes from the plan, the as-of defaults to the canonical book date. It is wrapped
    in ``ctx.run`` for journaling parity with the BD-09 resolution (a no-I/O derivation, so the step
    is trivially replay-stable).

    Clean failures, never fabricated args:
      - a ``soId`` that is not a BD-12 read SO is a ``TerminalError`` (422) — the orchestrator
        surfaces it as a clean step failure (the BD-09 window tools resolve via
        ``resolveStepArgs``);
      - a portfolio-scoped read with no ``portfolioId`` is a ``TerminalError`` (422) — surfaced
        cleanly, never a fabricated portfolio. SO-12.2-04 (book-close state) is portfolio-agnostic.
    """
    request = _coerce_request(req)
    so_id = request.soId

    if so_id not in _BD12_RESOLVABLE_SO_IDS:
        raise TerminalError(
            f"argResolver cannot resolve BD-12 read args for {so_id!r}: this handler resolves only "
            f"the BD-12 book-of-record read tools {list(_BD12_RESOLVABLE_SO_IDS)}. This step is "
            f"as a clean failure rather than dispatching on fabricated inputs.",
            status_code=422,
        )

    book = _bd12_book_for_so(so_id, request.book)
    portfolio_id = request.portfolioId
    if so_id not in _BD12_NO_PORTFOLIO_SO_IDS and not portfolio_id:
        raise TerminalError(
            f"argResolver: the BD-12 read step {so_id} has no resolvable portfolio (the abstract "
            "'portfolioId' arg is missing) — cannot derive the read scope. Surfaced as a clean "
            "failure, not a fabricated read.",
            status_code=422,
        )
    as_of = request.asOfDate or _BD12_DEFAULT_AS_OF

    def _resolve() -> ResolveBd12StepArgsResult:
        args: dict[str, Any] = {"book": book, "as_of_date": as_of}
        if so_id not in _BD12_NO_PORTFOLIO_SO_IDS:
            args["portfolio_id"] = portfolio_id
        return {
            "soId": so_id,
            "book": book,
            "portfolioId": portfolio_id,
            "asOfDate": as_of,
            "args": args,
            "computedBy": f"python:{ARG_RESOLVER_SERVICE_NAME}",
        }

    return await ctx.run(f"resolve-bd12-{so_id}-{portfolio_id or 'book'}", _resolve)


# --- SD-12.10 reconcile resolution (OIM-162, incremental + additive) ------------------------------


class ResolveReconStepArgsResult(TypedDict):
    """The resolved SD-12.10 reconcile request args + the run provenance.

    ``args`` is the abstract reconcile request dict ({as_of_date, persist}) ready to dispatch to
    ``bd12Recon.execute_so`` for ``soId`` — the bd12Recon service reads the internal book + the
    comparator feed itself, so the resolver derives only the run SCOPE (the as-of, and whether to
    persist), NOT concrete rows. The reconcile is firm-wide (no portfolio scope).
    """

    soId: str
    asOfDate: str
    persist: bool
    args: dict[str, Any]
    computedBy: str


@argResolver.handler(name="resolveReconStepArgs", input_serde=PassThroughJsonSerde())
async def resolve_recon_step_args(
    ctx: restate.Context, req: ResolveStepArgsRequest
) -> ResolveReconStepArgsResult:
    """Resolve an SD-12.10 reconcile step into the bd12Recon reconcile request args (SO-12.10-*).

    The incremental SD-12.10 resolution (the standing per-tool-incremental decision). The reconcile
    args are abstract by design — the bd12Recon service reads the internal book + the comparator
    feed
    itself — so this resolver derives the run SCOPE ({as_of_date, persist}) from the plan step
    WITHOUT
    a marts read and WITHOUT a portfolio (the reconcile is firm-wide). The as-of defaults to the
    canonical book date; ``persist`` defaults to true (the engine persists the findings
    append-only).
    Wrapped in ``ctx.run`` for journaling parity (a no-I/O derivation, trivially replay-stable).

    Clean failures, never fabricated args: a ``soId`` that is not an SD-12.10 reconcile SO is a
    ``TerminalError`` (422) — the orchestrator surfaces it as a clean step failure.
    """
    request = _coerce_request(req)
    so_id = request.soId

    if so_id not in _BD12_RECON_SO_IDS:
        raise TerminalError(
            f"argResolver cannot resolve reconcile args for {so_id!r}: this handler resolves only "
            f"the SD-12.10 reconcile tools {list(_BD12_RECON_SO_IDS)}. This step surfaces as a "
            f"clean failure rather than dispatching on fabricated inputs.",
            status_code=422,
        )

    as_of = request.asOfDate or _BD12_DEFAULT_AS_OF

    def _resolve() -> ResolveReconStepArgsResult:
        args: dict[str, Any] = {"as_of_date": as_of, "persist": True}
        return {
            "soId": so_id,
            "asOfDate": as_of,
            "persist": True,
            "args": args,
            "computedBy": f"python:{ARG_RESOLVER_SERVICE_NAME}",
        }

    return await ctx.run(f"resolve-recon-{so_id}", _resolve)


# --- SD-12.10 propose-only cause-proposer resolution (OIM-162 cycle-2, incremental + additive) ---


class ResolveProposerStepArgsResult(TypedDict):
    """The resolved SD-12.10 propose-only cause-proposer args + the run provenance.

    ``args`` is the abstract proposer request dict ({as_of_date, capture}) ready to dispatch to
    ``bd12Recon.execute_so`` for ``SO-12.10-05`` — the bd12Recon service gathers the `unexplained`
    residue itself, so the resolver derives only the run SCOPE (the as-of, and whether to capture).
    """

    soId: str
    asOfDate: str
    capture: bool
    args: dict[str, Any]
    computedBy: str


@argResolver.handler(name="resolveProposerStepArgs", input_serde=PassThroughJsonSerde())
async def resolve_proposer_step_args(
    ctx: restate.Context, req: ResolveStepArgsRequest
) -> ResolveProposerStepArgsResult:
    """Resolve the SD-12.10 propose-only cause-proposer step into its args (SO-12.10-05).

    The incremental, ADDITIVE resolution for the cycle-2 proposer (the reconcile resolver above is
    byte-unperturbed). The proposer args are abstract by design — the bd12Recon service gathers the
    `unexplained` residue + assembles the bundles itself — so this resolver derives the run SCOPE
    ({as_of_date, capture}) WITHOUT a marts read and WITHOUT a portfolio. The as-of defaults to the
    canonical book date; ``capture`` defaults to true (the flywheel captures every proposal).

    Clean failures, never fabricated args: a ``soId`` that is not the proposer SO is a
    ``TerminalError`` (422).
    """
    request = _coerce_request(req)
    so_id = request.soId

    if so_id != _BD12_PROPOSER_SO_ID:
        raise TerminalError(
            f"argResolver cannot resolve proposer args for {so_id!r}: this handler resolves only "
            f"the SD-12.10 propose-only cause-proposer {_BD12_PROPOSER_SO_ID!r}. This step "
            f"surfaces as a clean failure rather than dispatching on fabricated inputs.",
            status_code=422,
        )

    as_of = request.asOfDate or _BD12_DEFAULT_AS_OF

    def _resolve() -> ResolveProposerStepArgsResult:
        args: dict[str, Any] = {"as_of_date": as_of, "capture": True}
        return {
            "soId": so_id,
            "asOfDate": as_of,
            "capture": True,
            "args": args,
            "computedBy": f"python:{ARG_RESOLVER_SERVICE_NAME}",
        }

    return await ctx.run(f"resolve-proposer-{so_id}", _resolve)
