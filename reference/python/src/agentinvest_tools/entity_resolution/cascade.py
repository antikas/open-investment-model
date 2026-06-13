"""The deterministic three-tier entity-resolution cascade.

The of-record resolve path: given an inbound legal-entity feed record and the standing E-01 / E-13 /
E-14 reference data, decide — deterministically and explainably — whether the record is an existing
golden record (and which), a net-new entity, or a case for the steward review queue. Plus the
golden-record survivorship that builds the canonical record per resolved cluster.

THE THREE TIERS (the model's ``## Resolution`` cascade, made runnable):

- **Tier-1 — exact external-identifier match.** The inbound record carries an external id (LEI /
  registry id / private CUSIP). It matches an E-01 master iff that id is the master's LEI (E-01.lei)
  OR an E-14 External Identifier row for the master. Exact, high-confidence, score 1.0.
- **Tier-2 — deterministic name / alias match.** No usable inbound id. The record's
  ``normalise_name`` key (case / whitespace / suffix / diacritic-normalised — see ``normaliser.py``)
  matches a master iff it byte-equals the master's normalised canonical name OR the normalised form
  of one of the master's aliases (the union of E-13 Entity Alias + the E-01 ``known_aliases``
  read-cache). Metadata (domicile) is a CORROBORATION GATE, not a fuzzy score: a name-key match with
  a CONFLICTING declared domicile does NOT auto-merge — it falls to Tier-3 (the genuinely-ambiguous
  guard). Score 0.9 (declared deterministic threshold; a name+alias exact-key match at or above it
  resolves).
- **Tier-3 — steward review queue.** Everything the deterministic tiers cannot resolve to exactly
  one master: a no-id record whose normalised name matches NO master (net-new), or whose name-key
  collides with another record / a master under CONFLICTING metadata (genuinely ambiguous). NEVER
  auto-merged — quarantined for a human. A quarantine is a SUCCESS, not a miss: forcing it would be
  the cardinal mis-merge.

THE DETERMINISTIC SPINE (the load-bearing invariant). Every decision is a pure function of the
record + the reference data — NO LLM, no learned scorer, no fuzzy edit-distance. The of-record match
bar is EXACTNESS after a declared, auditable normalisation. The probabilistic / LLM-proposer tier (a
model proposing a candidate for review) is deliberately out of scope here: this module imports
NONE of it, and the module-graph spine assertion (``test_entity_resolution_cascade``) proves the
resolve path's transitive import closure contains no model/proposer/anthropic module.

THE MATCHER NEVER READS THE ANSWER KEY. The cascade resolves from the feed record's OBSERVABLE
evidence (name / lei / domicile / parent hint / external id) only — never from
``entity_resolution_labels`` (the oracle). The label-independence is proven structurally
(``resolve_record`` takes a feed record + reference data; it has no label parameter) and
behaviourally (the eval shuffles / perturbs the oracle and the cascade's decisions do not change).

SYNTHETIC, DETERMINISTIC. The cascade runs over a synthetic resolution oracle; a green
resolution proves the deterministic cascade + golden-record survivorship + the review-queue
quarantine, NOT a production entity-resolution run against live custodian/administrator feeds.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Literal

from agentinvest_tools.entity_resolution.normaliser import normalise_name

# The declared, deterministic Tier-2 threshold. A name/alias EXACT-normalised-key match scores 0.9
# (>= threshold -> resolve); a conflicting-domicile name-key collision scores below it -> review.
# It is a DECLARED constant, not a learned/tuned parameter — the cascade is deterministic.
TIER2_THRESHOLD = Decimal("0.9")
_TIER1_SCORE = Decimal("1.0")
_TIER2_SCORE = Decimal("0.9")
_REVIEW_SCORE = Decimal("0.0")

ResolutionTier = Literal["tier_1_exact_id", "tier_2_name_alias", "tier_3_review"]
ResolutionDecision = Literal["resolved", "new", "review"]


@dataclass(frozen=True)
class FeedRecord:
    """One inbound legal-entity feed record — the cascade input (observable evidence only).

    No label field, by construction: the cascade resolves from observable evidence
    (name / lei / domicile / parent hint / external id), never from the oracle.
    """

    source_record_id: str
    source_system: str
    raw_name: str
    raw_lei: str | None
    raw_domicile: str | None
    raw_parent_hint: str | None
    raw_external_id: str | None
    raw_id_type: str | None
    received_at: date


@dataclass(frozen=True)
class MasterEntity:
    """One standing E-01 master + its resolution surfaces (E-13 aliases + E-14 external ids).

    ``aliases`` is the UNION of E-13 Entity Alias names + the E-01 ``known_aliases`` read-cache (the
    model declares E-13 canonical and ``known_aliases`` a denormalised read-cache derivable from it;
    the cascade reads the union so an alias present in EITHER surface resolves). ``external_ids`` is
    the union of the E-01 ``lei`` attribute + every E-14 External Identifier value for the master.
    """

    entity_id: str
    entity_name: str
    lei: str | None
    domicile: str | None
    parent_entity_id: str | None
    aliases: tuple[str, ...]
    external_ids: tuple[str, ...]


@dataclass(frozen=True)
class ResolutionResult:
    """The cascade's per-record decision — explainable (tier + signal + score)."""

    source_record_id: str
    decision: ResolutionDecision
    tier: ResolutionTier
    matched_entity_id: str | None
    score: Decimal
    signal: str  # the human-readable explanation of WHICH evidence fired


def _norm_id(value: str | None) -> str | None:
    """Normalise an external-id string for exact comparison — trim + uppercase; empty -> None."""
    if value is None:
        return None
    v = value.strip().upper()
    return v or None


def _build_id_index(masters: tuple[MasterEntity, ...]) -> dict[str, str]:
    """Map every normalised external id -> entity_id (E-01.lei + every E-14 id). First-writer wins.

    A collision (two masters claiming the same external id) is a reference-data integrity problem,
    not a resolution problem; the index keeps the first and the cascade resolves to it
    deterministically.
    """
    index: dict[str, str] = {}
    for m in masters:
        for raw in (m.lei, *m.external_ids):
            nid = _norm_id(raw)
            if nid is not None and nid not in index:
                index[nid] = m.entity_id
    return index


def _build_name_index(masters: tuple[MasterEntity, ...]) -> dict[str, list[str]]:
    """Map every normalised name/alias key -> the entity_ids carrying it (the Tier-2 key index).

    A key maps to a LIST because two distinct masters CAN share a normalised name (a genuine
    collision); the cascade treats a multi-master key as ambiguous and quarantines it (never picks
    one). The key is built from the master canonical name + every alias, all run through
    ``normalise_name``.
    """
    index: dict[str, list[str]] = {}
    for m in masters:
        keys = {normalise_name(m.entity_name)}
        keys |= {normalise_name(a) for a in m.aliases}
        for key in keys:
            if not key:
                continue
            index.setdefault(key, [])
            if m.entity_id not in index[key]:
                index[key].append(m.entity_id)
    return index


def resolve_record(
    record: FeedRecord,
    masters: tuple[MasterEntity, ...],
    *,
    id_index: dict[str, str] | None = None,
    name_index: dict[str, list[str]] | None = None,
) -> ResolutionResult:
    """Resolve ONE feed record through the deterministic three-tier cascade — pure, explainable.

    Tier-1 (exact external id) -> Tier-2 (deterministic name/alias key + domicile corroboration) ->
    Tier-3 (review). Returns the decision with the tier, the matched entity (if any), the score and
    a
    human-readable signal. NO label is consulted — the only inputs are the record + the reference
    data (the answer-key discipline, enforced by the signature).

    The indices are derivable from ``masters``; they are accepted as optional args so a batch builds
    them ONCE (O(masters)) and resolves each record O(1), without changing the per-record decision.
    """
    idx_id = id_index if id_index is not None else _build_id_index(masters)
    idx_name = name_index if name_index is not None else _build_name_index(masters)
    by_id = {m.entity_id: m for m in masters}

    # --- Tier-1: exact external-identifier match -------------------------------------------------
    inbound_id = _norm_id(record.raw_external_id) or _norm_id(record.raw_lei)
    if inbound_id is not None:
        hit = idx_id.get(inbound_id)
        if hit is not None:
            return ResolutionResult(
                source_record_id=record.source_record_id,
                decision="resolved",
                tier="tier_1_exact_id",
                matched_entity_id=hit,
                score=_TIER1_SCORE,
                signal=f"exact external-id match ({inbound_id}) to {hit}",
            )
        # An inbound id that matches NO master is a net-new entity carrying its own id — it cannot
        # be
        # name-matched to a different master (its id is authoritative + unmatched). Net-new.
        return ResolutionResult(
            source_record_id=record.source_record_id,
            decision="new",
            tier="tier_1_exact_id",
            matched_entity_id=None,
            score=_REVIEW_SCORE,
            signal=f"inbound external-id ({inbound_id}) matches no master — net-new",
        )

    # --- Tier-2: deterministic name / alias key + domicile corroboration -------------------------
    key = normalise_name(record.raw_name)
    candidates = idx_name.get(key, []) if key else []

    if len(candidates) == 1:
        cand = by_id[candidates[0]]
        # Domicile corroboration GATE (deterministic, not a fuzzy score): a name-key match with a
        # declared CONFLICTING domicile does NOT auto-merge — it is genuinely ambiguous (the same
        # name under a different jurisdiction may be a different entity). Quarantine to review. A
        # null on either side is NOT a conflict (absence of evidence, not evidence of difference).
        if _domicile_conflicts(record.raw_domicile, cand.domicile):
            return ResolutionResult(
                source_record_id=record.source_record_id,
                decision="review",
                tier="tier_3_review",
                matched_entity_id=None,
                score=_REVIEW_SCORE,
                signal=(
                    f"name-key '{key}' matches {cand.entity_id} but domicile conflicts "
                    f"({record.raw_domicile} vs {cand.domicile}) — quarantined, not merged"
                ),
            )
        return ResolutionResult(
            source_record_id=record.source_record_id,
            decision="resolved",
            tier="tier_2_name_alias",
            matched_entity_id=cand.entity_id,
            score=_TIER2_SCORE,
            signal=f"deterministic name/alias key '{key}' -> {cand.entity_id}",
        )

    if len(candidates) > 1:
        # The normalised key collides across two or more DISTINCT masters — genuinely ambiguous, the
        # cardinal mis-merge trap. NEVER pick one. Quarantine.
        return ResolutionResult(
            source_record_id=record.source_record_id,
            decision="review",
            tier="tier_3_review",
            matched_entity_id=None,
            score=_REVIEW_SCORE,
            signal=f"name-key '{key}' collides across masters {candidates} — quarantined",
        )

    # No id, no name-key master match: net-new. This is the honest "I have not seen this entity"
    # outcome — it joins the review/new flow (a steward confirms net-new vs a missed master).
    return ResolutionResult(
        source_record_id=record.source_record_id,
        decision="new",
        tier="tier_2_name_alias",
        matched_entity_id=None,
        score=_REVIEW_SCORE,
        signal=f"no external-id and name-key '{key}' matches no master — net-new",
    )


def _domicile_conflicts(a: str | None, b: str | None) -> bool:
    """Two domiciles CONFLICT iff both are present and differ (case-insensitively). Null !=
    conflict."""
    if a is None or b is None:
        return False
    sa, sb = a.strip().upper(), b.strip().upper()
    if not sa or not sb:
        return False
    return sa != sb


# ============================ within-batch ambiguity (the net-new collision guard) ================
# A subtlety the model's hard case requires: two inbound records can name the SAME (net-new) entity,
# OR name DIFFERENT entities under an identical name with conflicting metadata. Neither matches an
# existing master, so the per-record cascade lands both at `new`. The BATCH pass below detects a
# normalised-name collision AMONG the net-new records and, where the metadata CONFLICTS, demotes the
# colliding records to `review` (the genuinely-ambiguous quarantine) rather than letting a
# downstream
# clusterer silently merge two distinct entities under one new golden key. This is the within-batch
# mis-merge guard — still deterministic, still no model.


def resolve_batch(
    records: tuple[FeedRecord, ...],
    masters: tuple[MasterEntity, ...],
) -> tuple[ResolutionResult, ...]:
    """Resolve a batch of feed records — the per-record cascade + the within-batch ambiguity guard.

    Builds the master indices once, resolves each record, then runs the within-batch net-new
    collision guard: where two or more ``new`` records share a normalised name-key under CONFLICTING
    declared metadata (domicile), they are demoted to ``review`` (genuinely ambiguous — never merged
    into one new golden cluster). Records sharing a name-key with CONSISTENT metadata stay ``new``
    (they are the same net-new entity seen twice — a legitimate new cluster). Pure + deterministic;
    no label consulted.
    """
    id_index = _build_id_index(masters)
    name_index = _build_name_index(masters)
    results = [
        resolve_record(r, masters, id_index=id_index, name_index=name_index) for r in records
    ]
    by_src = {r.source_record_id: r for r in records}

    # Group the `new` records by their normalised name-key.
    new_groups: dict[str, list[ResolutionResult]] = {}
    for res in results:
        if res.decision == "new":
            key = normalise_name(by_src[res.source_record_id].raw_name)
            if key:
                new_groups.setdefault(key, []).append(res)

    demote: set[str] = set()
    for group in new_groups.values():
        if len(group) < 2:
            continue
        domiciles = {
            (by_src[g.source_record_id].raw_domicile or "").strip().upper() for g in group
        }
        # Drop the unknown ("") — absence is not a conflict. A conflict iff >= 2 distinct KNOWN
        # domiciles among the colliding net-new records.
        known = {d for d in domiciles if d}
        if len(known) >= 2:
            demote.update(g.source_record_id for g in group)

    if not demote:
        return tuple(results)

    out: list[ResolutionResult] = []
    for res in results:
        if res.source_record_id in demote:
            key = normalise_name(by_src[res.source_record_id].raw_name)
            out.append(
                ResolutionResult(
                    source_record_id=res.source_record_id,
                    decision="review",
                    tier="tier_3_review",
                    matched_entity_id=None,
                    score=_REVIEW_SCORE,
                    signal=(
                        f"net-new name-key '{key}' collides under conflicting domiciles within the "
                        f"batch — genuinely ambiguous, quarantined (never merged)"
                    ),
                )
            )
        else:
            out.append(res)
    return tuple(out)


# ============================ golden-record survivorship ==========================================


@dataclass(frozen=True)
class GoldenFieldProvenance:
    """Which source record won a golden-record field, and the value it contributed."""

    field_name: str
    value: str | None
    source_record_id: str
    source_system: str


@dataclass(frozen=True)
class GoldenRecord:
    """The canonical golden record for a resolved cluster — keyed by the INTERNAL entity_id.

    Keyed by the OpenIM-internal ``entity_id`` (E-01's golden-key discipline — NEVER an external
    id).
    Carries the survived canonical fields + per-field provenance (which source won each field).
    """

    entity_id: str
    entity_name: str | None
    lei: str | None
    domicile: str | None
    source_record_ids: tuple[str, ...]
    provenance: tuple[GoldenFieldProvenance, ...] = field(default_factory=tuple)


# The survivorship source-system priority — a declared, deterministic order (most-authoritative
# first). internal_onboarding is the firm's own curated capture; the administrator statement is
# next; the custodian feed last. A field is won by the highest-priority source that carries a
# non-empty value for it; ties broken by source_record_id (deterministic).
_SOURCE_PRIORITY: dict[str, int] = {
    "internal_onboarding": 0,
    "administrator": 1,
    "custodian": 2,
}


def _priority(record: FeedRecord) -> tuple[int, str]:
    return (_SOURCE_PRIORITY.get(record.source_system, 99), record.source_record_id)


def build_golden_record(
    entity_id: str,
    cluster: tuple[FeedRecord, ...],
    master: MasterEntity | None,
) -> GoldenRecord:
    """Build the golden record for a resolved cluster by deterministic survivorship.

    Each canonical field (entity_name / lei / domicile) is won by the highest-priority source record
    in the cluster carrying a non-empty value (ties broken by source_record_id). Where the cluster
    resolved to an EXISTING master, the master's own value is the baseline (a source only overrides
    it for a field the master leaves empty — the master is the most authoritative, being the curated
    golden record already). Per-field provenance records which source contributed each value.
    """
    ordered = sorted(cluster, key=_priority)

    def _survive(extract, master_value: str | None) -> GoldenFieldProvenance | None:  # type: ignore[no-untyped-def]
        for rec in ordered:
            value = extract(rec)
            if value is not None and str(value).strip():
                return GoldenFieldProvenance(
                    field_name="",
                    value=str(value),
                    source_record_id=rec.source_record_id,
                    source_system=rec.source_system,
                )
        if master_value is not None and str(master_value).strip():
            return GoldenFieldProvenance(
                field_name="",
                value=str(master_value),
                source_record_id=f"master:{entity_id}",
                source_system="e01_master",
            )
        return None

    m_name = master.entity_name if master is not None else None
    m_lei = master.lei if master is not None else None
    m_dom = master.domicile if master is not None else None

    # Where a master exists, its values are the baseline (most authoritative); a source only fills a
    # field the master leaves empty.
    name_p = (
        GoldenFieldProvenance("entity_name", m_name, f"master:{entity_id}", "e01_master")
        if (master is not None and m_name)
        else _survive(lambda r: r.raw_name, None)
    )
    lei_p = (
        GoldenFieldProvenance("lei", m_lei, f"master:{entity_id}", "e01_master")
        if (master is not None and m_lei)
        else _survive(lambda r: r.raw_lei, None)
    )
    dom_p = (
        GoldenFieldProvenance("domicile", m_dom, f"master:{entity_id}", "e01_master")
        if (master is not None and m_dom)
        else _survive(lambda r: r.raw_domicile, None)
    )

    provenance = tuple(
        GoldenFieldProvenance(fname, p.value, p.source_record_id, p.source_system)
        for fname, p in (("entity_name", name_p), ("lei", lei_p), ("domicile", dom_p))
        if p is not None
    )

    return GoldenRecord(
        entity_id=entity_id,
        entity_name=name_p.value if name_p else None,
        lei=lei_p.value if lei_p else None,
        domicile=dom_p.value if dom_p else None,
        source_record_ids=tuple(r.source_record_id for r in ordered),
        provenance=provenance,
    )
