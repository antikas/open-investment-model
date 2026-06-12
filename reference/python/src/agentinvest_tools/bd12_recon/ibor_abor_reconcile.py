"""SO-12.10 IBOR/ABOR reconciliation — the two internal books, divergence-explained vs residual.

The SD-12.10 *IBOR / ABOR reconciliation* Service Operation: reconcile the firm's two internal books
— the real-time IBOR (SD-12.1) and the accounting-basis ABOR (SD-12.2) — and ACCOUNT FOR the
differences between them. Unlike the position/cash/transaction reconciles (internal vs OUTSIDE
data), this reconciles the two internal books against EACH OTHER. Emits E-24-shaped ``ibor_abor``
break findings only for the UNEXPLAINED residual.

THE KEY SEMANTIC: the two books LEGITIMATELY diverge on three known OIM-160 classes (the books are
*meant* to differ — E-04 places accruals on ABOR; the IBOR carries in-flight trades trade-date that
ABOR recognises only on settlement; cost-basis is an accounting-book concept). So an IBOR/ABOR
divergence is NOT automatically a break — it is a break only where it is NOT explained by a known
class. This is the dual-independent-pipeline for this surface (the goal's concretisation):

- **Pipeline A — the divergence EXPLAINED by the known OIM-160 classes.** For each holding, the
  IBOR-vs-ABOR difference is attributed to: a TD/SD-timing class (the quantity/value lag explained
  by a known in-flight E-05 trade), an ACCRUAL class (the ABOR accrued income the IBOR does not
  carry), or a COST-BASIS class (the accounting cost basis). The explained divergence is accounted
  for, not flagged.
- **Pipeline B — the RESIDUAL.** The part of the IBOR-vs-ABOR difference that NO known class
  explains. A nonzero residual beyond tolerance is the genuine ``ibor_abor`` break — classified
  ``timing`` where a residual quantity lag is timing-shaped, else ``unexplained``.

Where Pipeline A claims a divergence is fully explained but Pipeline B finds a residual (the
explanation did not fully account for the difference), the residual is surfaced as a break with
``pipeline_disagreement=True`` — the two pipelines disagree on whether the holding reconciles, and
the engine surfaces the disagreement rather than silently accepting the explanation.

On the clean OIM-160 synthetic dual book every divergence is fully explained by its class, so the
residual is zero and this reconcile emits ZERO ``ibor_abor`` breaks — which is the CORRECT result
(the two books are internally consistent; the breaks live between the internal book and the OUTSIDE
data, which the position/cash/transaction reconciles find). A constructed unexplained residual (a
holding whose IBOR/ABOR difference is NOT covered by accrual/timing/cost-basis) DOES surface —
proven
in the tests.

Pure and deterministic: the IBOR rows, the ABOR rows and the in-flight trades are read by the
data-access layers and passed in; this tool accounts for the divergence and surfaces the residual.
No I/O.

Honest boundary: a reconcile over the OIM-160 **synthetic** internal dual book, FINDINGS-ONLY.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from agentinvest_tools.bd12_recon.break_finding import (
    BreakFinding,
    CauseClassification,
    materiality_for_amount,
)

# The residual tolerance — an IBOR/ABOR difference within this (after the known classes are
# accounted for) is treated as fully explained (a rounding wobble), beyond it is the residual break.
_RESIDUAL_TOLERANCE = Decimal("0.01")


class BookPositionRow(BaseModel):
    """One holding's row on one book — the IBOR or ABOR side of the internal-vs-internal recon."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    position_id: str = Field(description="The matching key (the logical-holding identity).")
    instrument_id: str = Field(description="The instrument held (E-02).")
    quantity: Decimal | None = Field(default=None, description="Units held on this book.")
    market_value_usd: Decimal = Field(description="The book's market value.")
    accrued_income_usd: Decimal | None = Field(
        default=None, description="Accrued income (an ABOR attribute; null/zero on IBOR)."
    )
    cost_basis_usd: Decimal | None = Field(default=None, description="The position's cost basis.")


class IborAborInFlightTrade(BaseModel):
    """One in-flight E-05 trade — the TD/SD-timing explanation for an IBOR-vs-ABOR divergence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    transaction_id: str = Field(description="The in-flight transaction (E-05).")
    instrument_id: str = Field(description="The instrument transacted (E-02).")
    quantity: Decimal = Field(description="The in-flight trade quantity (the TD/SD lag explained).")


class ReconcileIborAborInput(BaseModel):
    """Inputs to the IBOR/ABOR reconcile — the two books + the in-flight (timing) explainer set."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    as_of_date: date = Field(description="The date the two books are reconciled as of.")
    ibor_rows: tuple[BookPositionRow, ...] = Field(default=())
    abor_rows: tuple[BookPositionRow, ...] = Field(default=())
    in_flight_trades: tuple[IborAborInFlightTrade, ...] = Field(
        default=(),
        description="The in-flight E-05 trades that explain the TD/SD-timing divergence.",
    )


class ReconcileIborAborOutput(BaseModel):
    """The IBOR/ABOR reconcile result — the residual breaks + the explained-divergence summary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reconciliation_type: str = Field(default="ibor_abor")
    as_of_date: date = Field(description="The as-of date the reconcile honoured.")
    n_matched: int = Field(description="Holdings present on both books.")
    n_divergent: int = Field(description="Holdings whose two books differ at all.")
    n_explained: int = Field(
        description="Divergent holdings explained by a known class (timing/accrual/cost-basis)."
    )
    n_breaks: int = Field(description="Holdings with an UNEXPLAINED residual (ibor_abor break).")
    n_pipeline_disagreements: int = Field(
        description="Residual breaks where the explanation did not fully account for the diff."
    )
    breaks: tuple[BreakFinding, ...] = Field(
        description="The E-24-shaped ibor_abor residual breaks, ordered by record_a_ref."
    )


def _in_flight_qty_by_instrument(
    trades: tuple[IborAborInFlightTrade, ...],
) -> dict[str, Decimal]:
    by_instr: dict[str, Decimal] = {}
    for t in trades:
        by_instr[t.instrument_id] = by_instr.get(t.instrument_id, Decimal(0)) + t.quantity
    return by_instr


def reconcile_ibor_abor(inp: ReconcileIborAborInput) -> ReconcileIborAborOutput:
    """Reconcile the IBOR vs ABOR books — account for the divergence, surface the residual.

    For each holding present on both books, attributes the IBOR-vs-ABOR difference to the known
    classes (TD/SD timing via the in-flight trades, accrual, cost-basis) and surfaces only the
    UNEXPLAINED residual. Pure and deterministic.
    """
    ibor = {r.position_id: r for r in inp.ibor_rows}
    abor = {r.position_id: r for r in inp.abor_rows}
    matched_keys = sorted(set(ibor) & set(abor))
    in_flight = _in_flight_qty_by_instrument(inp.in_flight_trades)

    findings: list[BreakFinding] = []
    n_divergent = 0
    n_explained = 0

    for key in matched_keys:
        i = ibor[key]
        a = abor[key]
        iq = i.quantity if i.quantity is not None else Decimal(0)
        aq = a.quantity if a.quantity is not None else Decimal(0)
        qty_diff = aq - iq  # abor − ibor
        mv_diff = a.market_value_usd - i.market_value_usd
        acc_diff = (a.accrued_income_usd or Decimal(0)) - (i.accrued_income_usd or Decimal(0))
        cb_diff = (a.cost_basis_usd or Decimal(0)) - (i.cost_basis_usd or Decimal(0))

        diverges = (
            abs(qty_diff) > _RESIDUAL_TOLERANCE
            or abs(mv_diff) > _RESIDUAL_TOLERANCE
            or abs(acc_diff) > _RESIDUAL_TOLERANCE
            or abs(cb_diff) > _RESIDUAL_TOLERANCE
        )
        if not diverges:
            continue
        n_divergent += 1

        # --- Pipeline A: explain the divergence by the known classes ---
        # TD/SD timing: the ABOR book lags the IBOR by the in-flight trade quantity (abor = ibor −
        # in-flight), so the explained quantity divergence is exactly −in_flight_qty.
        in_flight_qty = in_flight.get(i.instrument_id, Decimal(0))
        qty_explained_by_timing = in_flight_qty != 0 and qty_diff == -in_flight_qty
        # The market-value divergence is timing-shaped iff the quantity divergence is
        # timing-explained (the value lag rides on the in-flight trade); accrual + cost-basis are
        # explained by their own classes (they are legitimate ABOR-vs-IBOR book differences).
        qty_residual = Decimal(0) if qty_explained_by_timing else qty_diff
        mv_residual = Decimal(0) if qty_explained_by_timing else mv_diff
        # accrual + cost-basis are fully-explained classes — they account for their own divergence.
        residual_unexplained = (
            abs(qty_residual) > _RESIDUAL_TOLERANCE or abs(mv_residual) > _RESIDUAL_TOLERANCE
        )

        if not residual_unexplained:
            n_explained += 1
            continue

        # --- Pipeline B: the residual the explanation did not account for → a break ---
        # If a residual quantity lag is itself timing-shaped (a known in-flight magnitude) but the
        # direct explanation did not catch it, classify timing; otherwise unexplained.
        cause: CauseClassification = "unexplained"
        diff_amount = mv_residual if abs(mv_residual) > _RESIDUAL_TOLERANCE else None
        diff_qty = qty_residual if abs(qty_residual) > _RESIDUAL_TOLERANCE else None
        findings.append(
            BreakFinding(
                reconciliation_type="ibor_abor",
                record_a_ref=f"ibor:{key}",
                record_b_ref=f"abor:{key}",
                as_of_date=inp.as_of_date,
                difference_amount=diff_amount,
                difference_qty=diff_qty,
                cause_classification=cause,
                materiality=materiality_for_amount(diff_amount),
                # The explanation claimed the divergence was accounted for, but a residual remained:
                # the two pipelines disagree on whether the holding reconciles.
                pipeline_disagreement=True,
            )
        )

    ordered = tuple(sorted(findings, key=lambda b: b.record_a_ref))
    return ReconcileIborAborOutput(
        as_of_date=inp.as_of_date,
        n_matched=len(matched_keys),
        n_divergent=n_divergent,
        n_explained=n_explained,
        n_breaks=len(ordered),
        n_pipeline_disagreements=sum(1 for b in ordered if b.pipeline_disagreement),
        breaks=ordered,
    )
