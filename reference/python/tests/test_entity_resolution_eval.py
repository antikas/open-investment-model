"""The resolution eval — ZERO mis-merge, ZERO missed-merge among auto-resolved (OIM-199, the floor).

Scores the deterministic three-tier cascade against the SEED-LOADED labelled oracle
(``entity_resolution_labels.json`` — the SSOT, so the eval tracks the seed and cannot drift to a
stale hard-coded N). The cardinal properties this cycle must hold:

1. **ZERO mis-merges** — no source record the oracle says is entity X (or NEW / AMBIGUOUS) is
   resolved by the cascade to a DIFFERENT true entity. A mis-merge silently corrupts the golden
   master; it is the line that must hold. (precision over the auto-resolved set == 1.0)
2. **ZERO missed-merges among the auto-resolved set** — every record the oracle marks ``resolved``
   (tiers 1–2) is resolved by the cascade to its TRUE entity. (recall over the resolvable set = 1.0)
3. **The genuinely-ambiguous are QUARANTINED** — every oracle ``ambiguous`` record lands in the
   cascade's review queue (decision == review), never force-merged. A quarantine is a SUCCESS.
4. **Coverage** — all four difficulty tiers present (>= 2 each); the hard no-ID private case + the
   genuinely-ambiguous no-merge case both exercised.

The oracle is loaded ONLY by the eval (the score key); the cascade resolves from the feed's
observable evidence (the masters reconstructed from the E-01 / E-13 / E-14 seeds + the feed from
``raw_entity_resolution_feed.csv``) — never from the labels (the answer-key discipline). The eval is
NOT store-gated: it reads the seed CSVs directly and runs the PURE cascade, so it runs in CI without
a provisioned canonical store.
"""

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

from agentinvest_tools.entity_resolution import (
    FeedRecord,
    MasterEntity,
    ResolutionResult,
    normalise_name,
)
from agentinvest_tools.entity_resolution_service import run_resolution

_SEEDS = Path(__file__).resolve().parents[2] / "dbt" / "seeds"


def _opt(v: str | None) -> str | None:
    if v is None:
        return None
    s = v.strip()
    return s or None


def _load_masters() -> tuple[MasterEntity, ...]:
    """Reconstruct the E-01 masters + their E-13/E-14 resolution surfaces from the seed CSVs.

    Mirrors ``agentinvest_demo.entity_resolution_data.read_master_entities`` but over the raw seed
    files (no canonical store needed), so the eval runs in CI unGated. The alias / external-id sets
    are the UNION of the in-record arrays + the E-13 / E-14 entity-side rows.
    """
    e13: dict[str, list[str]] = {}
    with (_SEEDS / "raw_e13_entity_alias.csv").open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["subject_type"] == "legal_entity":
                e13.setdefault(row["subject_id"], []).append(row["alias_name"])
    e14: dict[str, list[str]] = {}
    with (_SEEDS / "raw_e14_external_identifier.csv").open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["subject_type"] == "legal_entity":
                e14.setdefault(row["subject_id"], []).append(row["external_id"])

    masters: list[MasterEntity] = []
    with (_SEEDS / "raw_e01_legal_entity.csv").open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            eid = row["entity_id"]
            known = [a.strip() for a in (row.get("known_aliases") or "").split(";") if a.strip()]
            ext_map = []
            raw_ext = row.get("external_ids") or ""
            if raw_ext.strip():
                try:
                    parsed = json.loads(raw_ext)
                    if isinstance(parsed, dict):
                        ext_map = [str(v) for v in parsed.values() if v]
                except json.JSONDecodeError:
                    pass
            aliases = sorted({*known, *e13.get(eid, [])})
            ext = sorted({*ext_map, *e14.get(eid, [])})
            masters.append(
                MasterEntity(
                    entity_id=eid,
                    entity_name=row["entity_name"],
                    lei=_opt(row.get("lei")),
                    domicile=_opt(row.get("domicile")),
                    parent_entity_id=_opt(row.get("parent_entity_id")),
                    aliases=tuple(aliases),
                    external_ids=tuple(ext),
                )
            )
    return tuple(masters)


def _load_feed() -> tuple[FeedRecord, ...]:
    feed: list[FeedRecord] = []
    with (_SEEDS / "raw_entity_resolution_feed.csv").open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            feed.append(
                FeedRecord(
                    source_record_id=row["source_record_id"],
                    source_system=row["source_system"],
                    raw_name=row["raw_name"],
                    raw_lei=_opt(row.get("raw_lei")),
                    raw_domicile=_opt(row.get("raw_domicile")),
                    raw_parent_hint=_opt(row.get("raw_parent_hint")),
                    raw_external_id=_opt(row.get("raw_external_id")),
                    raw_id_type=_opt(row.get("raw_id_type")),
                    received_at=date.fromisoformat(row["received_at"]),
                )
            )
    return tuple(feed)


def _load_oracle() -> dict[str, dict[str, str | None]]:
    """Load the labelled oracle from the JSON SSOT — source_record_id -> {true_entity_id, outcome,
    tier}."""
    data = json.loads((_SEEDS / "entity_resolution_labels.json").read_text(encoding="utf-8"))
    return {
        lab["source_record_id"]: {
            "true_entity_id": lab["true_entity_id"],
            "resolution_outcome": lab["resolution_outcome"],
            "difficulty_tier": lab["difficulty_tier"],
        }
        for lab in data["labels"]
    }


def _resolve() -> tuple[dict[str, ResolutionResult], dict[str, dict[str, str | None]]]:
    masters = _load_masters()
    feed = _load_feed()
    run = run_resolution(masters, feed, "2026-01-31")
    by_src = {r.source_record_id: r for r in run.results}
    oracle = _load_oracle()
    return by_src, oracle


# --- (4) coverage: all four tiers, >= 2 each, the hard + ambiguous cases present ------------------


def test_oracle_covers_all_four_difficulty_tiers() -> None:
    oracle = _load_oracle()
    from collections import Counter

    tiers = Counter(o["difficulty_tier"] for o in oracle.values())
    for tier in ("exact_lei", "alias_match", "name_variant_no_id", "ambiguous"):
        assert tiers[tier] >= 2, f"tier {tier} must have >= 2 instances; got {tiers[tier]}"
    # the genuinely-ambiguous no-merge case (an `ambiguous` OUTCOME, not just the tier) is present
    ambiguous_outcomes = [
        s for s, o in oracle.items() if o["resolution_outcome"] == "ambiguous"
    ]
    assert len(ambiguous_outcomes) >= 2, "need >= 2 genuinely-ambiguous (must-not-merge) cases"


# --- (1) ZERO mis-merges — the cardinal floor -----------------------------------------------------


def test_zero_mis_merges_the_cardinal_floor() -> None:
    """No record is resolved by the cascade to an entity OTHER than its oracle truth. precision ==
    1.0.

    A mis-merge = the cascade resolves a record to entity X while the oracle's truth for it is a
    DIFFERENT entity (or NEW / AMBIGUOUS). This is the line that must hold — a mis-merge silently
    corrupts the golden master. Zero, on the whole oracle.
    """
    by_src, oracle = _resolve()
    mis_merges = []
    for src, res in by_src.items():
        truth = oracle[src]["true_entity_id"]
        if res.decision == "resolved" and res.matched_entity_id != truth:
            mis_merges.append((src, res.matched_entity_id, truth))
    assert mis_merges == [], f"MIS-MERGES (the cardinal sin) must be ZERO — found: {mis_merges}"


# --- (2) ZERO missed-merges among the auto-resolved (resolvable) set — recall == 1.0 --------------


def test_zero_missed_merges_among_the_resolvable_set() -> None:
    """Every oracle `resolved` record is resolved by the cascade to its TRUE entity. recall == 1.0.

    A missed-merge among the AUTO-RESOLVED set = an oracle `resolved` (tier 1–2) record the cascade
    failed to resolve to its true entity (left new/review or matched wrong). The cascade is designed
    to catch tiers 1–2; every one must be caught. (A genuine evidence-insufficient quarantine of a
    resolvable pair would be a recall gap to SURFACE — there is none on this oracle.)
    """
    by_src, oracle = _resolve()
    missed = []
    for src, o in oracle.items():
        if o["resolution_outcome"] != "resolved":
            continue
        res = by_src[src]
        if not (res.decision == "resolved" and res.matched_entity_id == o["true_entity_id"]):
            missed.append((src, res.decision, res.matched_entity_id, o["true_entity_id"]))
    assert missed == [], f"MISSED-MERGES among the auto-resolved set must be ZERO — found: {missed}"


# --- (3) the genuinely-ambiguous are quarantined to review, never force-merged --------------------


def test_ambiguous_records_are_quarantined_not_force_merged() -> None:
    """Every oracle `ambiguous` record lands in the cascade's review queue (decision == review)."""
    by_src, oracle = _resolve()
    not_quarantined = []
    for src, o in oracle.items():
        if o["resolution_outcome"] != "ambiguous":
            continue
        res = by_src[src]
        if res.decision != "review":
            not_quarantined.append((src, res.decision, res.matched_entity_id))
    assert not_quarantined == [], (
        f"every genuinely-ambiguous record MUST be quarantined — leaked: {not_quarantined}"
    )


def test_net_new_records_are_not_resolved_to_a_master() -> None:
    """Every oracle `new` record is NOT resolved to an existing master (new or, if ambiguous,
    review)."""
    by_src, oracle = _resolve()
    wrong = []
    for src, o in oracle.items():
        if o["resolution_outcome"] != "new":
            continue
        res = by_src[src]
        if res.decision == "resolved":
            wrong.append((src, res.matched_entity_id))
    assert wrong == [], f"net-new records must not be merged into a master — found: {wrong}"


def test_precision_and_recall_are_perfect_on_the_oracle() -> None:
    """The headline scores: precision (no mis-merge) == 1.0, recall (no missed-merge) == 1.0.

    Computed over the auto-resolved set. The eval reports them; the cardinal bars (mis-merge == 0,
    missed-merge among auto-resolved == 0) are asserted individually above; this is the rolled-up
    confirmation.
    """
    by_src, oracle = _resolve()
    auto = [(s, r) for s, r in by_src.items() if r.decision == "resolved"]
    resolvable = [s for s, o in oracle.items() if o["resolution_outcome"] == "resolved"]

    true_positives = sum(
        1 for s, r in auto if r.matched_entity_id == oracle[s]["true_entity_id"]
    )
    precision = true_positives / len(auto) if auto else 1.0
    recall = true_positives / len(resolvable) if resolvable else 1.0
    assert precision == 1.0, f"precision (mis-merge floor) must be 1.0; got {precision}"
    assert recall == 1.0, f"recall over the resolvable set must be 1.0; got {recall}"


def test_normaliser_resolves_the_hard_no_id_private_case() -> None:
    """The model's hard case: a realistic no-universal-identifier private company resolves at T2.

    ERF-0009 ``Bolt Technologies OÜ`` is the hard no-ID case: a realistic private-company name
    carrying NO LEI and — critically — NO internal golden key in its surface string. It resolves to
    LE-0004 only because the E-13 alias machinery has LEARNED the name ``Bolt Technologies`` for
    that master (the model's alias-accumulation mechanism), and the KY domicile + parent hint
    corroborate. The answer (``LE-0004``) is recoverable ONLY via the alias + metadata, never read
    off the surface — that is the no-universal-identifier reality the tier now genuinely exercises.
    """
    by_src, oracle = _resolve()
    res = by_src["ERF-0009"]
    assert res.decision == "resolved"
    assert res.matched_entity_id == "LE-0004"
    assert res.tier == "tier_2_name_alias"
    # The differentiator under test: the inbound surface string carries NO internal golden key —
    # the resolver cannot read the answer off the name (the prior tautology this re-seed removes).
    assert "LE-0004" not in "Bolt Technologies OÜ"
    assert "le 0004" not in normalise_name("Bolt Technologies OÜ")
    # The normalised inbound key matches the learned E-13 alias key (not the master's canonical
    # name) — the alias does the work the no-universal-identifier case requires.
    assert normalise_name("Bolt Technologies OÜ") == normalise_name("Bolt Technologies")
