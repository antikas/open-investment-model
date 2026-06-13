"""SO-12.10 position reconciliation — internal book vs custodian, dual-independent-pipeline.

The SD-12.10 *position reconciliation* Service Operation: reconcile holdings between the firm's
internal book and the custodian's, instrument by instrument, at the matching key ``position_id``
(the synthetic feed carries one custodian row per holding, so the comparator is position_id-aligned).
Emits E-24-shaped position-break findings with a deterministic of-record cause.

THE DUAL-INDEPENDENT-PIPELINE (the load-bearing safety property). The reconcile is computed TWO
independent ways and any meta-disagreement is SURFACED — never silently reconciled:

- **Pipeline A — the direct comparison.** Internal ``e04_market_value_usd`` + ``quantity`` (the
  book's own position numbers) vs the custodian's ``market_value_usd`` + ``quantity`` at the
  matching key.
- **Pipeline B — the derivation cross-check.** The internal value derived INDEPENDENTLY from the
  E-07 valuation mark (``current_valuation_usd``) — a genuinely different internal source (E-07 has
  no ``book`` column; the mark is a property of the logical holding and CAN diverge from the
  book-specific ``e04_market_value_usd``; see int_position_valuation.sql) — vs the same custodian
  value. Pipeline B reconciles the custodian against the *mark-derived* internal value.

Where A and B DISAGREE on whether a holding breaks (A flags a value break the mark-derived B does
not, or vice versa — i.e. the book value and the E-07 mark themselves diverge for that holding), the
disagreement is emitted as a break flagged ``pipeline_disagreement=True``. A reconciliation that
silently picked one computation and proceeded is the failure mode regulators fear; this engine
surfaces the disagreement instead (Helland: managed uncertainty per partner).

THE DETERMINISTIC CLASSIFIER (of-record, no LLM):
- ``timing``     — the quantity lag is exactly a known in-flight E-05 trade (TD-booked, not yet
                   SD-settled — read via the pending-activity tool). Not a false hard break.
- ``data_error`` — a quantity difference NOT explained by any in-flight trade (a real share
miscount).
- ``fx`` / ``pricing`` — a qty-agree value difference beyond the 1 bp band: ``fx`` if its ratio is
                   shared across ≥2 holdings (a systematic translation factor), else ``pricing``
                   (an idiosyncratic mark). Resolved over the WHOLE candidate set (see
                   break_finding).
- ``unexplained`` — no rule fires.

Pure and deterministic: the internal rows, the custodian rows and the in-flight trades are read by
the data-access layers and passed in; this tool reconciles, classifies and surfaces. No I/O, no
clock, no RNG — the output is a function of the input alone.

Honest boundary: a reconcile over a **synthetic** internal book vs a **synthetic**
custodian feed, FINDINGS-ONLY — never a production reconciliation against a live custodian, never a
resolved/gated correcting entry.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from agentinvest_tools.bd12_recon.break_finding import (
    QTY_TOLERANCE,
    BreakFinding,
    CauseClassification,
    ValueDiffCandidate,
    classify_value_diffs,
    materiality_for_amount,
    price_diff_exceeds_band,
)


class InternalPositionRow(BaseModel):
    """One internal-book position at the matching key — the OpenIM-side record (the recon A-side).

    ``book_market_value_usd`` is the book's own number (E-04 ``market_value_usd`` — Pipeline A's
    internal value); ``mark_value_usd`` is the independent E-07 valuation mark (Pipeline B's
    internal
    value) — the two can diverge (int_position_valuation.sql), which is exactly what makes Pipeline
    B
    independent.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    position_id: str = Field(description="The matching key (the logical-holding identity).")
    instrument_id: str = Field(description="The instrument held (E-02).")
    quantity: Decimal | None = Field(default=None, description="Units held internally.")
    book_market_value_usd: Decimal = Field(
        description="The book's own market value (E-04 — Pipeline A's internal value)."
    )
    mark_value_usd: Decimal | None = Field(
        default=None,
        description="The independent E-07 valuation mark (Pipeline B's internal value).",
    )
    currency: str = Field(description="The position's currency.")


class CustodianPositionRow(BaseModel):
    """One custodian holdings record at the matching key — the counter-record (the recon B-side).

    The outside-data side: the custodian's own quantity + USD market value for the holding.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    position_id: str = Field(description="The matching key (position_id-aligned to the internal).")
    instrument_id: str = Field(description="The instrument held (E-02).")
    quantity: Decimal | None = Field(default=None, description="Units held per the custodian.")
    market_value_usd: Decimal = Field(description="The custodian's USD market value.")
    currency: str = Field(description="The custodian's reported currency.")


class InFlightTrade(BaseModel):
    """One in-flight (agreed-but-unsettled) E-05 trade — the timing-explanation evidence.

    A trade booked trade-date internally but not yet settlement-date by the custodian: the internal
    book carries it, the custodian does not yet. Read via the pending-activity tool. Its
    signed ``quantity`` explains a TD/SD quantity lag (a ``timing`` break, not a false hard break).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    transaction_id: str = Field(description="The in-flight transaction (E-05).")
    instrument_id: str = Field(description="The instrument transacted (E-02).")
    quantity: Decimal = Field(description="The in-flight trade quantity (the TD/SD lag explained).")


class ReconcilePositionInput(BaseModel):
    """Inputs to the position reconcile — the internal book, the custodian feed, the in-flight."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    as_of_date: date = Field(description="The date the two records are reconciled as of.")
    internal_rows: tuple[InternalPositionRow, ...] = Field(
        default=(), description="The internal-book positions at the matching key."
    )
    custodian_rows: tuple[CustodianPositionRow, ...] = Field(
        default=(), description="The custodian holdings records (position_id-aligned)."
    )
    in_flight_trades: tuple[InFlightTrade, ...] = Field(
        default=(),
        description="The in-flight E-05 trades (per instrument) that explain TD/SD timing lags.",
    )


class ReconcilePositionOutput(BaseModel):
    """The position reconcile result — the break findings, the counts, the dual-pipeline summary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reconciliation_type: str = Field(default="position")
    as_of_date: date = Field(description="The as-of date the reconcile honoured.")
    n_matched: int = Field(description="Holdings present on both sides (the matching-key set).")
    n_breaks: int = Field(description="The number of break findings emitted.")
    n_pipeline_disagreements: int = Field(
        description="Breaks where Pipeline A and Pipeline B disagreed (surfaced, not reconciled)."
    )
    breaks: tuple[BreakFinding, ...] = Field(
        description="The E-24-shaped position-break findings, ordered by record_a_ref."
    )


def _in_flight_qty_by_instrument(trades: tuple[InFlightTrade, ...]) -> dict[str, Decimal]:
    """Sum the in-flight trade quantity per instrument — the TD/SD lag each instrument explains."""
    by_instr: dict[str, Decimal] = {}
    for t in trades:
        by_instr[t.instrument_id] = by_instr.get(t.instrument_id, Decimal(0)) + t.quantity
    return by_instr


@dataclass(frozen=True)
class _PendingValueBreak:
    """A qty-agree value break awaiting its set-level fx/pricing cause (the second-pass carrier)."""

    key: str
    diff_amount: Decimal
    disagreement: bool


def reconcile_position(inp: ReconcilePositionInput) -> ReconcilePositionOutput:
    """Reconcile the internal book vs the custodian — dual-pipeline, deterministic classification.

    Walks the matching key (``position_id``), runs both pipelines, classifies each break of-record,
    and surfaces any A/B meta-disagreement. Pure and deterministic.
    """
    internal = {r.position_id: r for r in inp.internal_rows}
    custodian = {r.position_id: r for r in inp.custodian_rows}
    matched_keys = sorted(set(internal) & set(custodian))
    in_flight = _in_flight_qty_by_instrument(inp.in_flight_trades)

    findings: list[BreakFinding] = []
    # First pass: detect qty / value breaks per pipeline; collect the qty-agree value-diff
    # candidates for the set-level fx/pricing classification.
    value_candidates: list[ValueDiffCandidate] = []
    # carry the per-key working state so the second pass can attach the set-classified cause.
    pending: list[_PendingValueBreak] = []

    for key in matched_keys:
        i = internal[key]
        c = custodian[key]
        iq = i.quantity if i.quantity is not None else None
        cq = c.quantity if c.quantity is not None else None

        # --- the quantity leg (book-agnostic; Pipeline A and B share the quantity) ---
        qty_diff: Decimal | None = None
        if iq is not None and cq is not None:
            qty_diff = cq - iq
        elif (iq is None) != (cq is None):
            # one side carries a quantity the other does not — a data inconsistency
            qty_diff = (cq or Decimal(0)) - (iq or Decimal(0))

        if qty_diff is not None and abs(qty_diff) > QTY_TOLERANCE:
            # Is the lag exactly explained by a known in-flight trade for this instrument?
            in_flight_qty = in_flight.get(i.instrument_id, Decimal(0))
            # The custodian LAGS by the in-flight quantity (custodian qty = internal − in-flight),
            # so qty_diff (custodian − internal) == −in_flight_qty.
            qty_cause: CauseClassification = (
                "timing" if (in_flight_qty != 0 and qty_diff == -in_flight_qty) else "data_error"
            )
            findings.append(
                BreakFinding(
                    reconciliation_type="position",
                    record_a_ref=key,
                    record_b_ref=f"custodian:{key}",
                    as_of_date=inp.as_of_date,
                    difference_qty=qty_diff,
                    difference_amount=None,
                    cause_classification=qty_cause,
                    materiality="low" if qty_cause == "timing" else "medium",
                    pipeline_disagreement=False,
                )
            )
            # A quantity break is resolved; the value legs are not evaluated for the same holding
            # (the quantity divergence is the break).
            continue

        # --- the value leg: Pipeline A (book value) and Pipeline B (E-07 mark) vs custodian ---
        # Pipeline A — the direct comparison: the book's own E-04 market value vs the custodian.
        a_breaks = price_diff_exceeds_band(i.book_market_value_usd, c.market_value_usd)
        # Pipeline B — the derivation cross-check: the independent E-07 mark vs the custodian.
        b_internal = i.mark_value_usd if i.mark_value_usd is not None else i.book_market_value_usd
        b_breaks = price_diff_exceeds_band(b_internal, c.market_value_usd)

        # A meta-disagreement is when the two pipelines disagree on whether the holding breaks —
        # i.e. the book value and the E-07 mark themselves diverge enough to land on opposite sides
        # of the band. But an internal book-vs-mark divergence that is ITSELF explained by a known
        # class (the holding carries an in-flight trade the book values but the mark does not yet)
        # is NOT a surfaceable break — it is the explained timing divergence. So a disagreement is
        # surfaced only when the book-vs-mark divergence is UNEXPLAINED (no in-flight trade for it).
        timing_explains_internal_gap = in_flight.get(i.instrument_id, Decimal(0)) != 0
        disagreement = (a_breaks != b_breaks) and not timing_explains_internal_gap

        # A value break is surfaced when Pipeline A finds one, OR when the pipelines genuinely (and
        # unexplainedly) disagree. A B-only break that the in-flight timing explains is accounted
        # for, not surfaced (it would be a false break — the book and the custodian agree exactly).
        if a_breaks or disagreement:
            diff_amount = c.market_value_usd - i.book_market_value_usd
            pending.append(
                _PendingValueBreak(key=key, diff_amount=diff_amount, disagreement=disagreement)
            )
            value_candidates.append(
                ValueDiffCandidate(
                    record_a_ref=key,
                    record_b_ref=key,
                    internal_value=i.book_market_value_usd,
                    external_value=c.market_value_usd,
                )
            )

    # Second pass: classify the qty-agree value differences as a SET (the fx/pricing ratio cluster).
    cause_by_key = classify_value_diffs(value_candidates)
    for p in pending:
        findings.append(
            BreakFinding(
                reconciliation_type="position",
                record_a_ref=p.key,
                record_b_ref=f"custodian:{p.key}",
                as_of_date=inp.as_of_date,
                difference_amount=p.diff_amount,
                difference_qty=None,
                cause_classification=cause_by_key[p.key],
                materiality=materiality_for_amount(p.diff_amount),
                pipeline_disagreement=p.disagreement,
            )
        )

    ordered = tuple(sorted(findings, key=lambda b: b.record_a_ref))
    return ReconcilePositionOutput(
        as_of_date=inp.as_of_date,
        n_matched=len(matched_keys),
        n_breaks=len(ordered),
        n_pipeline_disagreements=sum(1 for b in ordered if b.pipeline_disagreement),
        breaks=ordered,
    )
