"""The E-24-shaped break finding + the deterministic of-record cause-classifier.

The shared contract the four SD-12.10 reconcile tools emit: a typed, E-24-shaped **break finding**
(the in-flight value, before it is persisted as an immutable E-24 break event) plus the
**deterministic, of-record cause-classifier** — rules over neutral observable evidence that assign
``cause_classification`` (E-24's vocabulary), leaving any break the rules cannot reach
``unexplained``.

THE DETERMINISTIC SPINE (the load-bearing design point). The cause-classification is the **of-record
classification** — a pure function of observable evidence, NO LLM (the propose-only LLM operates over
the ``unexplained`` residue, downstream of this classifier). A break the rules cannot reach is
``unexplained`` — the of-record value — never force-fit and never guessed (Kleppmann/Helland: derive
the classification as a view over the feed; the deterministic spine keeps the LLM out of the
knowledge-claim path). The rules are exhaustively unit-testable precisely because they are
deterministic.

THE CLASSIFIER DOES NOT READ THE ANSWER KEY. The custodian feed carries a ``break_note`` column
(``fx_break`` / ``price_break`` / ...), but that is the injected label — using it would be
reading the oracle, not classifying. The classifier therefore derives the cause from NEUTRAL
observable evidence only:

- ``timing``           — the quantity difference is exactly explained by a known in-flight E-05
trade
                         (TD-booked internally, not yet SD-settled by the custodian — read via the
                         pending-activity tool). A TD/SD timing divergence, not a hard break.
- ``data_error``       — a quantity difference NOT explained by any in-flight trade (a genuine share
                         miscount), or a cash balance disagreement.
- ``fx``               — quantity agrees, market value differs beyond the bp band, the value-ratio
                         (external / internal) is < 1 (the custodian translates the value LOWER) AND
                         that ratio is SHARED across two or more holdings — the SYSTEMATIC downward
                         translation factor (the same FX rate applied to several USD-translated
                         holdings), the of-record signature of an FX-rate difference.
- ``pricing``          — quantity agrees, market value differs beyond the bp band, AND the custodian
                         value is ABOVE the internal book (ratio > 1) — an idiosyncratic mark
                         difference (the custodian marks higher), never the downward fx-translation
                         signature.
- ``missing_transaction`` — a transaction present on one side of the match only.
- ``fees``             — a fee/charge difference (the rule is for completeness, firing on a genuine
                         fee-line divergence only). It is a valid, currently instance-free cause.
- ``unexplained``      — no rule fires. The of-record residue (the propose-only LLM input). This
                         ALSO covers a LONE downward value difference (a single holding, ratio < 1,
                         unique): no cluster signal and no direction signal separates a
                         single-holding
                         fx from a single-holding pricing-below, so the rule STOPS GUESSING.

THE FX/PRICING SPLIT. The fx/pricing rule combines two label-independent observables: the
ratio-cluster signal (a ratio shared across ≥2 holdings) and the DIRECTION of the value difference.
A value the custodian marks ABOVE the book is ``pricing`` (an idiosyncratic mark difference, never
the downward fx-translation signature); a LONE downward value difference is ``unexplained`` (no
cluster or direction signal can separate a single-holding fx from a single-holding pricing-below).
A pricing break whose downward ratio coincides EXACTLY with a genuine fx cluster's ratio stays
misclassified ``fx`` — observably indistinguishable in this USD-only feed, carried + documented,
never force-fit. See ``classify_value_diffs``.

The ``fx`` vs ``pricing`` split needs the WHOLE position-break population (the ratio-cluster is a
property of the set, not one row), so the position reconcile classifies AFTER it has gathered every
qty-agree value difference — the classifier takes the candidate set and resolves the split in one
pass.
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

# The reconcile tolerances. Position quantity matches TO THE SHARE (exact); cash matches TO THE CENT
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
    are NOT part of a freshly-identified finding — they are written only when a break is resolved
    (behind the breach gate). This finding is what the four reconcile tools emit and what the
    append-only store persists as an immutable ``open`` event.
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

    The oracle labels the position/transaction breaks ``medium`` and the two timing breaks
    ``low``; this band reproduces that split from the observable magnitude alone (it is applied to
    value differences; the timing breaks carry no amount and are banded ``low`` by the position
    reconcile). The bands are declared and deterministic:
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
    """Split a set of qty-agree value differences into ``fx`` / ``pricing`` / ``unexplained``.

    THE OF-RECORD FX/PRICING RULE. The rule combines two label-independent observables — the
    ratio-cluster signal and the **direction** of the value difference — and demotes the cases no
    observable signal can reach to ``unexplained`` rather than guessing:

    - **direction > 1 (custodian value ABOVE the internal book) → ``pricing``.** A USD-value
      FX-translation difference moves a reported value when the custodian and the book disagree on
      the translation rate; in this feed the systematic translation signature is a SHARED DOWNWARD
      ratio (every genuine fx break translates the custodian value LOWER, ratio < 1). A value the
      custodian marks ABOVE the book is an idiosyncratic mark difference, never the downward
      translation signature → ``pricing``.
    - **direction < 1 AND the ratio is shared by ≥2 candidates → ``fx``.** The systematic downward
      translation factor — the genuine fx signature (a shared rate applied to several
      USD-translated holdings).
    - **direction < 1 AND the ratio is UNIQUE (a single holding) → ``unexplained``.** A lone
    downward
      value difference carries NO cluster signal AND NO direction signal that separates a single-
      holding fx from a single-holding pricing-below: the of-record rule STOPS GUESSING and lands
      ``unexplained``. The propose-only LLM (the residue) annotates it; no deterministic
      observable-evidence rule in this feed can honestly resolve it.
    - **direction == 1 (a zero-amount value difference) → falls through to the cluster rule**
      (``unique → pricing``; the POS-0019 by-construction A/B-disagreement pin, unperturbed).

    THE HONEST BOUNDARY (the residue this rule does NOT reach). A pricing break whose downward ratio
    COINCIDES EXACTLY with a genuine fx cluster's ratio is observably indistinguishable from a
    member of that cluster — it clusters as ``fx`` and stays misclassified. No label-independent
    rule in this USD-only synthetic feed can separate them (the only discriminator is the
    ``break_note``
    answer key, which the engine must never read). This residual misclassification is carried,
    documented, NOT force-fit.

    Derived PURELY from the observable values (the external/internal ratio + its direction + the
    cluster membership) — NEVER from the custodian's ``break_note`` label. Proven label-independent
    by test (``test_bd12_recon_proposer``). Returns ``{record_a_ref: cause}`` for each candidate.
    """
    ratios: dict[str, Decimal | None] = {
        c.record_a_ref: _value_ratio(c.internal_value, c.external_value) for c in candidates
    }
    ratio_counts = Counter(r for r in ratios.values() if r is not None)
    out: dict[str, CauseClassification] = {}
    for c in candidates:
        ratio = ratios[c.record_a_ref]
        if ratio is None:
            # A zero internal value (an undefined ratio) carries no fx/pricing signal — leave it to
            # the residue; the of-record rule does not guess.
            out[c.record_a_ref] = "unexplained"
        elif ratio > 1:
            # The custodian marks ABOVE the book — an idiosyncratic mark difference, not the
            # systematic DOWNWARD fx-translation signature → pricing (the narrowed rule).
            out[c.record_a_ref] = "pricing"
        elif ratio < 1:
            # A downward value difference: the systematic fx signature IFF the ratio is shared by ≥2
            # holdings; a LONE downward holding has no cluster + no direction signal → unexplained
            # (the rule stops guessing rather than misclassify a single-holding difference).
            out[c.record_a_ref] = "fx" if ratio_counts[ratio] >= 2 else "unexplained"
        else:
            # ratio == 1 (a zero-amount value difference, e.g. the POS-0019 A/B-disagreement pin):
            # the cluster rule (shared → fx; unique → pricing) is unperturbed.
            out[c.record_a_ref] = "fx" if ratio_counts[ratio] >= 2 else "pricing"
    return out
