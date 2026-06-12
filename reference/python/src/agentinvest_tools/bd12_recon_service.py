"""The ``bd12Recon`` model-free Restate dispatch service — the SD-12.10 reconciliation boundary.

The SD-12.10 (Reconciliation) entry on the *service* axis: a model-free Restate service that hosts
the four reconcile tools (position · cash · transaction-matching · IBOR/ABOR) and dispatches a
*named* Service Operation to its tool as a journaled durable step. It is the ``bd12_service.py``
analogue — same ``execute_so`` / ``list_capabilities`` envelope shape — so the MCP/OpenAPI ingress
and the orchestrator reach it identically.

Service, not agent (the load-bearing topology point — ADR-0054). The per-BD layer is a **model-free
dispatch / tool-hosting boundary** that carries **no reasoning loop**. It routes a *named* SO to its
reconcile tool; it does **not** decide which SO to call (that is the one orchestrating ``.plan()``
loop). And it adds **no LLM** — the cause-classification is the deterministic of-record classifier
(cycle-1); the propose-only LLM over the ``unexplained`` residue is OIM-162 cycle-2.

THE I/O the reconcile touches:

- the **internal dual book** (via ``book_of_record_data`` — the OIM-161 read surface): the per-book
  positions (E-04), the E-05 transactions, the E-06 cash flows, the in-flight pending activity;
- the **external comparator feed** (via ``comparator_feed_data`` — the outside-data seam): the
  custodian holdings/cash + the administrator statement.

Each ``execute_so`` reads both sides at the requested as-of, runs the reconcile tool, **persists the
break findings append-only** to the engine-owned break store, and returns the findings. The read +
reconcile + APPEND is wrapped in ``ctx.run`` so it is a journaled durable step: on a crash/replay
the result is read back from the journal (the stores are NOT re-queried and the breaks are NOT
re-appended — the deterministic run-scoped break ids + the insert-only ``on conflict do nothing``
keep an actual re-append idempotent regardless).

THE APPEND IS NOT A STATE-MUTATION. It writes a NEW ``status = open`` break event (append-only,
immutable); it never updates a break, never transitions a ``status``, never writes a correcting
entry to ABOR, never mutates IBOR/ABOR. The first state-mutation (the correcting entry, behind the
breach gate) is OIM-163.

Error classification (the ``bd12`` precedent): a Pydantic ``ValidationError`` on the request args is
a terminal 400; a ``MartsUnavailableError`` / ``BreakStoreUnavailableError`` (a deterministic data
condition — the store is not provisioned) is a terminal 422; any other deterministic compute failure
is a terminal 422. There is no genuinely-transient surface in this local-duckdb path.

Honest boundary: this wires the *synthetic* SD-12.10 reconcile surface over the durable substrate. A
green dispatch proves typed-dispatch + the dual read + the dual-pipeline reconcile + the append-only
persistence; it is **not** a production reconciliation against a live custodian, and **not** a
resolved/gated correcting entry.
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
    read_pending_activity,
    read_transactions,
)
from agentinvest_demo.comparator_feed_data import (
    read_admin_statement,
    read_custodian_cash,
    read_custodian_holdings,
)
from agentinvest_demo.marts import MartsUnavailableError
from agentinvest_tools.bd12_recon import (
    AdminCashBalance,
    AdminTransaction,
    BookPositionRow,
    BreakStoreUnavailableError,
    CustodianCashBalance,
    CustodianPositionRow,
    IborAborInFlightTrade,
    InFlightTrade,
    InternalCashReplay,
    InternalPositionRow,
    InternalTransaction,
    ReconcileCashInput,
    ReconcileIborAborInput,
    ReconcilePositionInput,
    ReconcileTransactionsInput,
    append_breaks,
    reconcile_cash,
    reconcile_ibor_abor,
    reconcile_position,
    reconcile_transactions,
)
from agentinvest_tools.bd12_recon.break_finding import BreakFinding

BD12_RECON_SERVICE_NAME = "bd12Recon"

_ZERO = Decimal(0)


class ReconcileRequest(BaseModel):
    """The reconcile request the orchestrator emits — an as-of date (+ optional break-store toggle).

    The reconcile reads the internal book + the comparator feed for the whole as-of snapshot (the
    comparator is a firm-wide feed), so the request is an as-of date. ``persist`` controls whether
    the run appends the findings to the engine-owned break store (default true — the engine
    persists;
    a caller can run a non-persisting preview). ``extra="forbid"`` — an unrecognised arg is a
    deterministic 400.
    """

    model_config = ConfigDict(extra="forbid")

    as_of_date: str = Field(
        default="2026-03-31", description="The as-of date (defaults to the canonical book date)."
    )
    persist: bool = Field(
        default=True,
        description="Append the findings to the engine-owned break store (append-only).",
    )


@dataclass(frozen=True)
class ToolSpec:
    """One registry entry — a named Service Operation bound to its reconcile closure + I/O model."""

    so_id: str
    name: str
    summary: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    reconcile: Callable[[ReconcileRequest], tuple[BaseModel, list[BreakFinding]]]


def _as_of(req: ReconcileRequest) -> date:
    return date.fromisoformat(req.as_of_date)


# --- the per-SO reconcile closures: read both sides, run the dual-pipeline reconcile --------------


def _reconcile_position(req: ReconcileRequest) -> tuple[BaseModel, list[BreakFinding]]:
    as_of = req.as_of_date
    # The comparator is firm-wide (position_id-aligned across all funds), so read the internal book
    # across every portfolio the custodian feed covers — gather all internal IBOR positions.
    custodian = read_custodian_holdings(as_of)
    internal_rows = _read_all_internal_positions("ibor", as_of)
    # the in-flight trades (per instrument) that explain TD/SD timing across the funds in the feed.
    in_flight = _read_all_in_flight(as_of)
    # the E-07 mark (Pipeline B) is carried on the internal-position read (current_valuation_usd).
    out = reconcile_position(
        ReconcilePositionInput(
            as_of_date=_as_of(req),
            internal_rows=tuple(
                InternalPositionRow(
                    position_id=r.position_id,
                    instrument_id=r.instrument_id,
                    quantity=r.quantity,
                    book_market_value_usd=r.book_market_value_usd,
                    mark_value_usd=r.mark_value_usd,
                    currency=r.currency,
                )
                for r in internal_rows
            ),
            custodian_rows=tuple(
                CustodianPositionRow(
                    position_id=c.position_id,
                    instrument_id=c.instrument_id,
                    quantity=c.quantity,
                    market_value_usd=c.market_value_usd,
                    currency=c.currency,
                )
                for c in custodian
            ),
            in_flight_trades=tuple(in_flight),
        )
    )
    return out, list(out.breaks)


def _reconcile_cash(req: ReconcileRequest) -> tuple[BaseModel, list[BreakFinding]]:
    as_of = req.as_of_date
    cust = read_custodian_cash(as_of)
    admin_cash = read_admin_statement(as_of, record_type="cash")
    # Pipeline B: the E-06 replay-derived internal balance per fund (Σ the cash flows up to the
    # as-of). Read for each fund present in the external feed.
    funds = sorted({c.portfolio_id for c in cust} | {a.portfolio_id for a in admin_cash})
    replay = []
    for fund in funds:
        try:
            from agentinvest_demo.book_of_record_data import read_cash_flows

            flows = read_cash_flows(fund, as_of)
        except MartsUnavailableError:
            continue
        bal = sum((f.amount for f in flows), _ZERO)
        replay.append(InternalCashReplay(portfolio_id=fund, replay_balance_usd=bal))
    out = reconcile_cash(
        ReconcileCashInput(
            as_of_date=_as_of(req),
            custodian_balances=tuple(
                CustodianCashBalance(
                    portfolio_id=c.portfolio_id, balance_usd=c.balance_usd, currency=c.currency
                )
                for c in cust
            ),
            admin_balances=tuple(
                AdminCashBalance(
                    portfolio_id=a.portfolio_id, balance_usd=a.amount_usd, currency=a.currency
                )
                for a in admin_cash
            ),
            replay_balances=tuple(replay),
        )
    )
    return out, list(out.breaks)


def _reconcile_transactions(req: ReconcileRequest) -> tuple[BaseModel, list[BreakFinding]]:
    as_of = req.as_of_date
    admin_txns = read_admin_statement(as_of, record_type="transaction")
    internal_txns = _read_all_settled_transactions(as_of)
    out = reconcile_transactions(
        ReconcileTransactionsInput(
            as_of_date=_as_of(req),
            internal_transactions=tuple(
                InternalTransaction(
                    transaction_id=t.transaction_id,
                    portfolio_id=t.portfolio_id,
                    amount_usd=t.amount_usd,
                )
                for t in internal_txns
            ),
            admin_transactions=tuple(
                AdminTransaction(
                    ref=a.ref or a.admin_record_id,
                    portfolio_id=a.portfolio_id,
                    amount_usd=a.amount_usd,
                )
                for a in admin_txns
            ),
        )
    )
    return out, list(out.breaks)


def _reconcile_ibor_abor(req: ReconcileRequest) -> tuple[BaseModel, list[BreakFinding]]:
    as_of = req.as_of_date
    ibor = _read_all_internal_positions("ibor", as_of)
    abor = _read_all_internal_positions("abor", as_of)
    in_flight = _read_all_in_flight(as_of)
    out = reconcile_ibor_abor(
        ReconcileIborAborInput(
            as_of_date=_as_of(req),
            ibor_rows=tuple(
                BookPositionRow(
                    position_id=r.position_id,
                    instrument_id=r.instrument_id,
                    quantity=r.quantity,
                    market_value_usd=r.book_market_value_usd,
                    accrued_income_usd=None,
                    cost_basis_usd=r.cost_basis_usd_b,
                )
                for r in ibor
            ),
            abor_rows=tuple(
                BookPositionRow(
                    position_id=r.position_id,
                    instrument_id=r.instrument_id,
                    quantity=r.quantity,
                    market_value_usd=r.book_market_value_usd,
                    accrued_income_usd=r.accrued_income_usd_b,
                    cost_basis_usd=r.cost_basis_usd_b,
                )
                for r in abor
            ),
            in_flight_trades=tuple(
                IborAborInFlightTrade(
                    transaction_id=t.transaction_id,
                    instrument_id=t.instrument_id,
                    quantity=t.quantity,
                )
                for t in in_flight
            ),
        )
    )
    return out, list(out.breaks)


# --- the data-access helpers: read the internal book across the whole as-of snapshot --------------


@dataclass(frozen=True)
class _InternalPosFull:
    """An internal position carrying the book value AND the E-07 mark + accrual + cost-basis."""

    position_id: str
    instrument_id: str
    quantity: Decimal | None
    book_market_value_usd: Decimal
    mark_value_usd: Decimal | None
    accrued_income_usd_b: Decimal | None
    cost_basis_usd_b: Decimal | None
    currency: str


def _portfolios_in_feed() -> list[str]:
    """The portfolios the internal book carries (the read scope for the firm-wide reconcile)."""
    from agentinvest_demo.book_of_record_data import list_portfolios

    return list_portfolios()


def _read_all_internal_positions(book: str, as_of: str) -> list[_InternalPosFull]:
    """Read every internal position on ``book`` across all portfolios, with the E-07 mark carried.

    The reconcile is firm-wide (the comparator feed spans funds), so it reads the whole book. Pulls
    the book value (Pipeline A), the E-07 mark (Pipeline B), the accrual and the cost-basis from the
    canonical ``int_position_valuation`` via the data-access layer's position read, which already
    carries ``current_valuation_usd``. Reads through the data-access layer's connection (read-only).
    """
    # Read directly from the canonical layer for the extra columns (mark, accrual, cost-basis) the
    # book-of-record position read carries, across all portfolios.
    from pathlib import Path

    from agentinvest_demo.marts import _connect, resolve_duckdb_path

    path: Path = resolve_duckdb_path()
    con = _connect(path)
    try:
        rows = con.execute(
            """
            select position_id, instrument_id, quantity, e04_market_value_usd,
                current_valuation_usd, accrued_income_usd, cost_basis_usd, currency
            from main_intermediate.int_position_valuation
            where book = ? and as_of_date <= ?
            order by position_id
            """,
            [book, as_of],
        ).fetchall()
    finally:
        con.close()
    return [
        _InternalPosFull(
            position_id=str(r[0]),
            instrument_id=str(r[1]),
            quantity=None if r[2] is None else Decimal(str(r[2])),
            book_market_value_usd=Decimal(str(r[3])),
            mark_value_usd=None if r[4] is None else Decimal(str(r[4])),
            accrued_income_usd_b=None if r[5] is None else Decimal(str(r[5])),
            cost_basis_usd_b=None if r[6] is None else Decimal(str(r[6])),
            currency=str(r[7]),
        )
        for r in rows
    ]


def _read_all_in_flight(as_of: str) -> list[InFlightTrade]:
    """Read every in-flight (pending/confirmed, settle>as_of) E-05 trade across all portfolios."""
    trades: list[InFlightTrade] = []
    for pf in _portfolios_in_feed():
        for t in read_pending_activity(pf, as_of):
            if t.quantity is not None:
                trades.append(
                    InFlightTrade(
                        transaction_id=t.transaction_id,
                        instrument_id=t.instrument_id,
                        quantity=t.quantity,
                    )
                )
    return trades


def _read_all_settled_transactions(as_of: str) -> list[InternalTransaction]:
    """Read every settled internal E-05 transaction across all portfolios (the match A-side)."""
    out: list[InternalTransaction] = []
    for pf in _portfolios_in_feed():
        for t in read_transactions(pf, as_of):
            if t.status == "settled":
                out.append(
                    InternalTransaction(
                        transaction_id=t.transaction_id,
                        portfolio_id=t.portfolio_id,
                        amount_usd=t.amount_usd,
                    )
                )
    return out


# The registered SD-12.10 reconcile tool catalogue. Each so_id maps to its reconcile closure plus
# the tool's Pydantic I/O models. Adding a reconcile tool is one row here.
_REGISTRY: dict[str, ToolSpec] = {}


def _register() -> None:
    from agentinvest_tools.bd12_recon import (
        ReconcileCashOutput,
        ReconcileIborAborOutput,
        ReconcilePositionOutput,
        ReconcileTransactionsOutput,
    )

    specs = (
        ToolSpec(
            so_id="SO-12.10-01",
            name="reconcile_position",
            summary="Position reconciliation — internal book vs custodian (dual-pipeline → E-24).",
            input_model=ReconcileRequest,
            output_model=ReconcilePositionOutput,
            reconcile=_reconcile_position,
        ),
        ToolSpec(
            so_id="SO-12.10-02",
            name="reconcile_cash",
            summary="Cash reconciliation — custodian vs administrator (dual-pipeline → E-24).",
            input_model=ReconcileRequest,
            output_model=ReconcileCashOutput,
            reconcile=_reconcile_cash,
        ),
        ToolSpec(
            so_id="SO-12.10-03",
            name="reconcile_transactions",
            summary="Transaction matching — internal vs administrator, both directions (→ E-24).",
            input_model=ReconcileRequest,
            output_model=ReconcileTransactionsOutput,
            reconcile=_reconcile_transactions,
        ),
        ToolSpec(
            so_id="SO-12.10-04",
            name="reconcile_ibor_abor",
            summary="IBOR/ABOR reconciliation — the two internal books, residual-surfaced (E-24).",
            input_model=ReconcileRequest,
            output_model=ReconcileIborAborOutput,
            reconcile=_reconcile_ibor_abor,
        ),
    )
    for spec in specs:
        _REGISTRY[spec.so_id] = spec


_register()


class ExecuteSoInput(BaseModel):
    """The ``execute_so`` request envelope — a named SO plus its reconcile args.

    A Pydantic model so the Restate auto-generated OpenAPI/MCP surface derives a typed request
    schema. ``soId`` is the Service-Operation identifier (e.g. ``"SO-12.10-01"``); ``args`` is the
    reconcile request (as_of_date / persist) mapped onto ``ReconcileRequest`` inside the journaled
    step.
    """

    model_config = ConfigDict(extra="forbid")

    soId: str = Field(description="The Service-Operation identifier to dispatch, e.g. SO-12.10-01")
    args: dict[str, Any] = Field(
        default_factory=dict,
        description="The reconcile args (as_of_date / persist) as a JSON object.",
    )


class ExecuteSoProvenance(TypedDict):
    soId: str
    tool: str
    runId: str
    breakIds: list[str]
    persisted: bool


class ExecuteSoOutput(TypedDict):
    result: dict[str, Any]
    provenance: ExecuteSoProvenance
    computedBy: str


class CapabilityDescriptor(TypedDict):
    soId: str
    name: str
    summary: str
    inputSchema: dict[str, Any]
    outputSchema: dict[str, Any]


class ListCapabilitiesOutput(TypedDict):
    service: str
    capabilities: list[CapabilityDescriptor]


bd12Recon = restate.Service(BD12_RECON_SERVICE_NAME)


class ExecuteSoEnvelopeSerde(restate.serde.Serde[Any]):
    """A permissive pass-through JSON deserialiser so the in-handler envelope guard owns the status.

    The ``bd12`` precedent: the Restate SDK re-wraps a serde-raised exception as a status-less 500,
    so the serde must NEVER raise — it parses the body and returns the raw value for the handler's
    ``_coerce_envelope`` to classify as a clean terminal 400.
    """

    def deserialize(self, buf: bytes) -> Any:
        if not buf:
            return {}
        try:
            return json.loads(buf)
        except Exception:
            return buf.decode("utf-8", errors="replace")

    def serialize(self, obj: Any) -> bytes:
        if obj is None:
            return b""
        return json.dumps(obj).encode("utf-8")


def _dispatch(spec: ToolSpec, args: dict[str, Any], run_id: str) -> ExecuteSoOutput:
    """Validate the args, read both sides, run the reconcile, append the breaks, shape the result.

    Runs inside the journaled ``ctx.run`` step. The append is append-only insert-only (a new
    ``status = open`` break event); it never updates a break / transitions a status / writes a
    correcting entry. The deterministic run-scoped break ids + the insert-only ``on conflict do
    nothing`` keep a replay/re-append idempotent.
    """
    try:
        request = ReconcileRequest.model_validate(args)
    except ValidationError as exc:
        raise TerminalError(
            f"{spec.so_id} ({spec.name}): invalid arguments — {exc.error_count()} error(s): {exc}",
            status_code=400,
        ) from exc

    try:
        output, findings = spec.reconcile(request)
    except (MartsUnavailableError, BreakStoreUnavailableError) as exc:
        raise TerminalError(f"{spec.so_id} ({spec.name}): {exc}", status_code=422) from exc
    except (ValueError, TypeError, KeyError) as exc:
        raise TerminalError(
            f"{spec.so_id} ({spec.name}): {type(exc).__name__}: {exc}", status_code=422
        ) from exc

    break_ids: list[str] = []
    if request.persist and findings:
        try:
            break_ids = append_breaks(findings, run_id=run_id)
        except BreakStoreUnavailableError as exc:
            raise TerminalError(f"{spec.so_id} ({spec.name}): {exc}", status_code=422) from exc

    return {
        "result": output.model_dump(mode="json"),
        "provenance": {
            "soId": spec.so_id,
            "tool": spec.name,
            "runId": run_id,
            "breakIds": break_ids,
            "persisted": bool(request.persist and findings),
        },
        "computedBy": f"python:{BD12_RECON_SERVICE_NAME}",
    }


def _coerce_envelope(req: Any) -> dict[str, Any]:
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


@bd12Recon.handler(name="execute_so", input_serde=ExecuteSoEnvelopeSerde())
async def execute_so(ctx: restate.Context, req: ExecuteSoInput) -> ExecuteSoOutput:
    """Dispatch a named SD-12.10 reconcile Service Operation to its tool as a journaled step.

    Model-free dispatch — it routes the *named* ``soId`` to its registered reconcile tool; it does
    not decide which SO to call (the orchestrator's ``.plan()`` loop does). The read + reconcile +
    append-only persistence runs inside the journaled step (replay reads the result back; the
    deterministic run-scoped break ids keep an actual re-append idempotent).

    The append writes a NEW ``status = open`` break only — no update, no status transition, no
    correcting entry, no IBOR/ABOR mutation (those are OIM-163, behind the breach gate). An unknown
    ``soId`` is a terminal 404; a bad/extra arg or a deterministic data condition is terminal
    (400 / 422) — never a retry storm. No LLM (cycle-1 is deterministic).
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
    # The run id scopes a reconcile run's break ids; derived from the invocation id (replay-stable)
    # + the so_id + the as-of, so a replay reproduces the SAME ids (the append stays idempotent).
    as_of = args.get("as_of_date", "2026-03-31") if isinstance(args, dict) else "2026-03-31"
    run_id = f"{ctx.request().id}-{spec.so_id}-{as_of}"

    return await ctx.run(f"so-{spec.so_id}", lambda: _dispatch(spec, args, run_id))


@bd12Recon.handler(name="list_capabilities")
async def list_capabilities(ctx: restate.Context) -> ListCapabilitiesOutput:
    """Return the registered SD-12.10 reconcile tool catalogue — each so_id with its I/O schema.

    Read-only; no journaled step (it derives from the static registry). Arity-0 — called with an
    empty request body over the ingress.
    """
    capabilities: list[CapabilityDescriptor] = [
        {
            "soId": spec.so_id,
            "name": spec.name,
            "summary": spec.summary,
            "inputSchema": spec.input_model.model_json_schema(),
            "outputSchema": spec.output_model.model_json_schema(),
        }
        for spec in _REGISTRY.values()
    ]
    return {"service": BD12_RECON_SERVICE_NAME, "capabilities": capabilities}
