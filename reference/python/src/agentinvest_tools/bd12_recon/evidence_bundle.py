"""The deterministic evidence-bundle assembler for an ``unexplained`` break.

The propose-only LLM classifier (``proposer.py``) never sees a break in isolation: it sees the break
plus a deterministically-assembled **observable-evidence bundle** — the two records, the diffs, the
value ratio + its cluster context, and the pending in-flight activity. This module assembles that
bundle from the SAME observable evidence the deterministic engine classifies from, and NOTHING ELSE.

THE LABEL IS A FORBIDDEN INPUT (the load-bearing trust property). The custodian feed carries a
``break_note`` answer-key column and the seeds carry a ``break_labels`` manifest
(``stg_break_labels``)
— BOTH are the oracle (the score key), NOT engine inputs. The bundle assembler reads
ONLY
the neutral observable evidence (``comparator_feed_data`` + ``book_of_record_data``, neither of
which
projects ``break_note``); it NEVER reads ``stg_break_labels`` and NEVER reads ``break_note``. This
is
asserted STRUCTURALLY — the module imports neither the labels reader nor any labels table — AND by
test (``test_bundle_never_touches_the_oracle_label``). A bundle that carried the label would let the
LLM (and any rule derived from its rationale) read the answer key — an oracle-corruption defect at
the proposal layer. The assembler refuses it by construction.

WHY A BUNDLE (the deterministic spine). The deterministic spine keeps the LLM out of the
knowledge-claim path: the of-record ``cause_classification`` is the deterministic rule's value
(``unexplained`` for the residue). The LLM only PROPOSES over the residue, and its proposal is an
append-only annotation, never of-record. The bundle is the deterministic, replayable evidence the
proposal is grounded in — so a regulator can replay "what did the model see?" exactly: the bundle
is a pure function of the observable feed (no label, no clock, no RNG), and its ``snapshot_ref``
is a content hash a reviewer can recompute.

SYNTHETIC, FINDINGS-ONLY. The bundle is assembled over the synthetic feed; it is the
evidence for a PROPOSAL (never an of-record action), never a production reconciliation.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from agentinvest_tools.bd12_recon.break_finding import BreakFinding


class EvidenceBundle(BaseModel):
    """The observable-evidence bundle for one ``unexplained`` break — the proposal's grounding.

    Column-faithful to the NEUTRAL observable evidence only: the break's own diffs, the ratio +
    how many holdings in the run share it (the cluster context), the in-flight quantity for the
    instrument (the timing-explanation evidence), and a content-hash ``snapshot_ref`` a reviewer can
    recompute. NO ``break_note``, NO oracle label, NO true cause — the label is a forbidden input.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    break_id: str = Field(description="The engine break id this bundle is assembled for.")
    reconciliation_type: str = Field(description="position / cash / transaction / ibor_abor.")
    record_a_ref: str = Field(description="The internal-book record (the A-side).")
    record_b_ref: str = Field(
        description="The counter-record (the outside-data / second-book side)."
    )
    difference_amount: Decimal | None = Field(
        default=None, description="The monetary difference (external − internal), where applicable."
    )
    difference_qty: Decimal | None = Field(
        default=None, description="The quantity difference (external − internal), where applicable."
    )
    value_ratio: Decimal | None = Field(
        default=None,
        description="external/internal value ratio (6dp) — the fx/pricing observable; None if N/A.",
    )
    ratio_cluster_size: int = Field(
        default=0,
        description="How many value-break holdings in the run SHARE this exact ratio (≥2 = a "
        "systematic translation cluster; 1 = a lone holding).",
    )
    ratio_direction: str = Field(
        default="n/a",
        description="'above' (custodian > book, ratio > 1) / 'below' (< 1) / 'equal' / 'n/a'.",
    )
    in_flight_qty: Decimal | None = Field(
        default=None,
        description="The in-flight (TD/SD) quantity for this break's instrument (timing evidence).",
    )
    of_record_cause: str = Field(
        description="The DETERMINISTIC of-record cause (always 'unexplained' for a residue break — "
        "the proposal never changes it; the spine holds).",
    )
    snapshot_ref: str = Field(
        description="A content hash of the observable evidence — a reviewer recomputes it to" 
            "replay "
        "exactly what the model saw (no label is in the hash).",
    )


@dataclass(frozen=True)
class _ValueContext:
    """The run-level value-ratio cluster context (assembled once, shared across bundles)."""

    cluster_sizes: dict[Decimal, int]


def _value_ratio(internal: Decimal, external: Decimal) -> Decimal | None:
    if internal == 0:
        return None
    return (external / internal).quantize(Decimal("0.000001"))


def _ratio_direction(ratio: Decimal | None) -> str:
    if ratio is None:
        return "n/a"
    if ratio > 1:
        return "above"
    if ratio < 1:
        return "below"
    return "equal"


def assemble_value_context(
    findings: list[BreakFinding],
    internal_by_ref: dict[str, Decimal],
    external_by_ref: dict[str, Decimal],
) -> _ValueContext:
    """Compute the run-level ratio-cluster sizes from the value-bearing breaks — observable only.

    The cluster size of a ratio is how many value breaks in the run share it (the systematic-vs-
    idiosyncratic signal the fx/pricing rule uses). Computed from the internal/external values that
    the engine already read (NOT from any label). Funds with no value diff (qty/cash/txn breaks) do
    not contribute a ratio.
    """
    ratios: list[Decimal] = []
    for f in findings:
        iv = internal_by_ref.get(f.record_a_ref)
        ev = external_by_ref.get(f.record_a_ref)
        if iv is None or ev is None:
            continue
        r = _value_ratio(iv, ev)
        if r is not None:
            ratios.append(r)
    return _ValueContext(cluster_sizes=dict(Counter(ratios)))


def assemble_bundle(
    finding: BreakFinding,
    break_id: str,
    *,
    internal_value: Decimal | None = None,
    external_value: Decimal | None = None,
    in_flight_qty: Decimal | None = None,
    value_context: _ValueContext | None = None,
) -> EvidenceBundle:
    """Assemble the observable-evidence bundle for one ``unexplained`` break — the label forbidden.

    Pure: a function of the finding + the observable values + the in-flight quantity + the run-level
    cluster context. It reads NO label, NO ``break_note``, NO ``stg_break_labels`` — the assembler
    imports none of them (structural). ``of_record_cause`` is carried straight from the finding (the
    deterministic value, always 'unexplained' for a residue break — the spine: the proposal never
    changes it). ``snapshot_ref`` is a content hash over the observable evidence (no label in it).
    """
    ratio = (
        _value_ratio(internal_value, external_value)
        if internal_value is not None and external_value is not None
        else None
    )
    cluster_size = 0
    if ratio is not None and value_context is not None:
        cluster_size = value_context.cluster_sizes.get(ratio, 1)
    # The content hash is over the OBSERVABLE evidence only — never the label. A reviewer recomputes
    # it from the same neutral fields to replay "what did the model see?".
    payload = {
        "break_id": break_id,
        "reconciliation_type": finding.reconciliation_type,
        "record_a_ref": finding.record_a_ref,
        "record_b_ref": finding.record_b_ref,
        "difference_amount": None if finding.difference_amount is None
        else str(finding.difference_amount),
        "difference_qty": None if finding.difference_qty is None else str(finding.difference_qty),
        "value_ratio": None if ratio is None else str(ratio),
        "ratio_cluster_size": cluster_size,
        "ratio_direction": _ratio_direction(ratio),
        "in_flight_qty": None if in_flight_qty is None else str(in_flight_qty),
        "of_record_cause": finding.cause_classification,
    }
    snapshot_ref = "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:16]
    return EvidenceBundle(
        break_id=break_id,
        reconciliation_type=finding.reconciliation_type,
        record_a_ref=finding.record_a_ref,
        record_b_ref=finding.record_b_ref,
        difference_amount=finding.difference_amount,
        difference_qty=finding.difference_qty,
        value_ratio=ratio,
        ratio_cluster_size=cluster_size,
        ratio_direction=_ratio_direction(ratio),
        in_flight_qty=in_flight_qty,
        of_record_cause=finding.cause_classification,
        snapshot_ref=snapshot_ref,
    )
