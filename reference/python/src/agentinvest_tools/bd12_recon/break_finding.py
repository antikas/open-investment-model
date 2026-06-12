"""The E-24-shaped break finding + the deterministic of-record cause-classifier (OIM-162 cycle-1).

The shared contract the four SD-12.10 reconcile tools emit: a typed, E-24-shaped **break finding**
(the in-flight value, before it is persisted as an immutable E-24 break event) plus the
**deterministic, of-record cause-classifier** — rules over neutral observable evidence that assign
``cause_classification`` (E-24's vocabulary), leaving any break the rules cannot reach
``unexplained``.

THE DETERMINISTIC SPINE (the load-bearing design point). The cause-classification is the **of-record
classification** — a pure function of observable evidence, NO LLM (the propose-only LLM over the
``unexplained`` residue is OIM-162 cycle-2, not this cycle). A break the rules cannot reach is
``unexplained`` — the of-record value — never force-fit and never guessed (Kleppmann/Helland: derive
the classification as a view over the feed; the deterministic spine keeps the LLM out of the
knowledge-claim path). The rules are exhaustively unit-testable precisely because they are
deterministic.

THE CLASSIFIER DOES NOT READ THE ANSWER KEY. The custodian feed carries a ``break_note`` column
(``fx_break`` / ``price_break`` / ...), but that is the OIM-160 injected label — using it would be
reading the oracle, not classifying. The classifier therefore derives the cause from NEUTRAL
observable evidence only:

- ``timing``           — the quantity difference is exactly explained by a known in-flight E-05
trade
                         (TD-booked internally, not yet SD-settled by the custodian — read via the
                         OIM-161 pending-activity tool). A TD/SD timing divergence, not a hard
                         break.
- ``data_error``       — a quantity difference NOT explained by any in-flight trade (a genuine share
                         miscount), or a cash balance disagreement.
- ``fx``               — quantity agrees, market value differs beyond the bp band, AND the
                         value-ratio (external / internal) is SHARED across two or more holdings —
                         a SYSTEMATIC translation factor (the same FX rate applied to several
                         USD-translated holdings), the of-record signature of an FX-rate difference.
- ``pricing``          — quantity agrees, market value differs beyond the bp band, with an
                         IDIOSYNCRATIC per-holding ratio (a single holding mismarked) — a mark
                         difference, not a systematic translation.
- ``missing_transaction`` — a transaction present on one side of the match only.
- ``fees``             — a fee/charge difference (no fee-class break is injected in OIM-160; the
                         rule is for completeness, firing on a genuine fee-line divergence only).
- ``unexplained``      — no rule fires. The of-record residue (cycle-2's propose-only LLM input).

The ``fx`` vs ``pricing`` split needs the WHOLE position-break population (the ratio-cluster is a
property of the set, not one row), so the position reconcile classifies AFTER it has gathered every
qty-agree value difference — the classifier takes the candidate set and resolves the systematic-vs-
idiosyncratic split in one pass.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# E-24's cause_classification vocabulary (model/entities/core/E-24-reconciliation-break.md).
CauseClassification = Literal[
    "timing", "pricing", "missing_transaction", "data_error", "fx", "fees", "unexplained"
]
# E-24's reconciliation_type vocabulary.
ReconciliationType = Literal[
    "position", "cash", "transaction", "ibor_abor", "custodian", "counterparty"
]
Materiality = Literal["low", "medium", "high"]

# The reconcile tolerances (D5, the coordinator's brief-time proposal — confirmed in the report,
# not silently changed). Position quantity matches TO THE SHARE (exact); cash matches TO THE CENT
# (exact); a valuation/price difference within a 1 bp band CLEARS, beyond it raises a pricing/fx
# break. These are the declared per-surface tolerances the engine reconciles to.
PRICE_TOLERANCE_BPS = Decimal("1")  # 1 basis point — within clears, beyond is a value break.
QTY_TOLERANCE = Decimal("0")  # to the share — any nonzero residual qty diff (beyond timing) breaks.
CASH_TOLERANCE = Decimal("0.01")  # to the cent.


class BreakFinding(BaseModel):
    """One E-24-shaped reconciliation break finding — the in-flight value before persistence.

    Column-faithful to the subset of the E-24 attribute schema a freshly-identified break carries
    at ``status = open`` (model/entities/core/E-24-reconciliation-break.md). The resolution
    fields E-24 also carries (``resolved_date`` / ``resolution_note`` / ``correcting_entry_ref``)
    are NOT part of a freshly-identified finding — they are written only when a break is resolved,
    which is OIM-163 (behind the breach gate), never this cycle. This finding is what the four
    reconcile tools emit and what the append-only store persists as an immutable ``open`` event.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    reconciliation_type: ReconciliationType = Field(
        description="What was reconciled — position / cash / transaction / ibor_abor."
    )
    record_a_ref: str = Field(description="The OpenIM-side record (the internal book record).")
    record_b_ref: str = Field(description="The counter-record it disagreed with (outside data).")
    as_of_date: date = Field(description="The date the two records are compared as of.")
    difference_amount: Decimal | None = Field(
        default=None, description="The monetary difference (external − internal), where applicable."
    )
    difference_qty: Decimal | None = Field(
        default=None, description="The quantity difference (external − internal), where applicable."
    )
    cause_classification: CauseClassification = Field(
        description="The deterministic of-record root cause, or 'unexplained' on a rule-miss."
    )
    materiality: Materiality = Field(description="low / medium / high.")
    pipeline_disagreement: bool = Field(
        default=False,
        description="True when the dual-independent-pipeline cross-check disagreed on this record "
        "— the disagreement is SURFACED as a break, never silently reconciled.",
    )


@dataclass(frozen=True)
class ValueDiffCandidate:
    """A qty-agree market-value difference awaiting the fx/pricing split (the set-level classifier).

    The fx-vs-pricing distinction is a property of the WHOLE candidate set (a systematic translation
    ratio is shared across holdings; an idiosyncratic mark difference is not), so the position
    reconcile collects every qty-agree value difference as a candidate, then classifies the set.
    """

    record_a_ref: str
    record_b_ref: str
    internal_value: Decimal
    external_value: Decimal


def materiality_for_amount(amount: Decimal | None) -> Materiality:
    """Deterministic materiality band by absolute monetary difference (the engine's declared band).

    The OIM-160 oracle labels the position/transaction breaks ``medium`` and the two timing breaks
    ``low``; this band reproduces that split from the observable magnitude alone (it is applied to
    value differences; the timing breaks carry no amount and are banded ``low`` by the position
    reconcile). The bands are declared, deterministic, and documented in the cycle report:
    ``|amount| < 100,000`` → ``low``; ``< 1,000,000`` → ``medium``; otherwise ``high``.
    """
    if amount is None:
        return "low"
    mag = abs(amount)
    if mag < Decimal("100000"):
        return "low"
    if mag < Decimal("1000000"):
        return "medium"
    return "high"


def price_diff_exceeds_band(internal_value: Decimal, external_value: Decimal) -> bool:
    """True iff the relative value difference exceeds the 1 bp price-tolerance band.

    Within the band clears (a rounding/observable-mark wobble); beyond raises a value break. Guards
    a zero internal value (any nonzero external value beyond it is a break).
    """
    if internal_value == 0:
        return external_value != 0
    rel_bps = abs(external_value - internal_value) / abs(internal_value) * Decimal("10000")
    return rel_bps > PRICE_TOLERANCE_BPS


def _value_ratio(internal_value: Decimal, external_value: Decimal) -> Decimal | None:
    """The external/internal value ratio, rounded to 6dp (the FX-cluster key); None if undefined."""
    if internal_value == 0:
        return None
    return (external_value / internal_value).quantize(Decimal("0.000001"))


def classify_value_diffs(candidates: list[ValueDiffCandidate]) -> dict[str, CauseClassification]:
    """Split a set of qty-agree value differences into ``fx`` vs ``pricing`` by the ratio cluster.

    THE OF-RECORD FX SIGNATURE (the deterministic rule). An FX-translation difference is
    SYSTEMATIC: the same FX rate applies to every holding the custodian USD-translates, so two or
    more holdings share an identical external/internal value ratio. A pricing difference is
    IDIOSYNCRATIC: one holding is mismarked, so its ratio is its own. The rule: a value difference
    whose ratio is shared by ≥2 candidates is ``fx``; a value difference with a unique ratio is
    ``pricing``. Derived purely from the observable values — NOT from the custodian's ``break_note``
    label. Returns ``{record_a_ref: cause}`` for each candidate.
    """
    ratios: dict[str, Decimal | None] = {
        c.record_a_ref: _value_ratio(c.internal_value, c.external_value) for c in candidates
    }
    ratio_counts = Counter(r for r in ratios.values() if r is not None)
    out: dict[str, CauseClassification] = {}
    for c in candidates:
        ratio = ratios[c.record_a_ref]
        # A ratio shared by ≥2 holdings is a systematic translation factor → fx; otherwise pricing.
        if ratio is not None and ratio_counts[ratio] >= 2:
            out[c.record_a_ref] = "fx"
        else:
            out[c.record_a_ref] = "pricing"
    return out
