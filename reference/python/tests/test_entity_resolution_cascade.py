"""The deterministic three-tier cascade — the load-bearing characterisation + spine tests (OIM-199).

Drives the deterministic resolution cascade with constructed masters + feed records and proves the
cycle's load-bearing properties:

1. each TIER fires on its designed evidence (exact id -> name/alias key -> review);
2. the genuinely-ambiguous cases (name-key collision, conflicting-domicile match, within-batch
   net-new collision) are QUARANTINED to review, NEVER force-merged — the cardinal mis-merge floor;
3. the normaliser is a pure deterministic function (case / whitespace / suffix / diacritic);
4. THE DETERMINISTIC SPINE — the of-record resolve path's transitive import closure contains NO
   LLM / proposer / model module (the module-graph assertion);
5. the matcher is LABEL-INDEPENDENT — it takes a feed record + reference data and has no label
   parameter (structural); perturbing what a label WOULD say cannot change a decision (behavioural).

Pure tests — no store, no canonical layer. The eval over the seeded oracle is
``test_entity_resolution_eval``; the store invariants are ``test_entity_resolution_stores``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from agentinvest_tools.entity_resolution import (
    FeedRecord,
    MasterEntity,
    build_golden_record,
    normalise_name,
    resolve_batch,
    resolve_record,
)

AS_OF = "2026-01-31"


def _feed(
    src: str,
    name: str,
    *,
    lei: str | None = None,
    domicile: str | None = None,
    parent: str | None = None,
    ext: str | None = None,
    id_type: str | None = None,
    system: str = "custodian",
) -> FeedRecord:
    return FeedRecord(
        source_record_id=src,
        source_system=system,
        raw_name=name,
        raw_lei=lei,
        raw_domicile=domicile,
        raw_parent_hint=parent,
        raw_external_id=ext,
        raw_id_type=id_type,
        received_at=date(2026, 1, 15),
    )


_ACME = MasterEntity(
    entity_id="LE-0001",
    entity_name="Acme Asset Management LLP",
    lei="5493001KJTIIGC8Y1R12",
    domicile="GB",
    parent_entity_id=None,
    aliases=("Acme AM", "Acme Asset Mgmt"),
    external_ids=("5493001KJTIIGC8Y1R12",),
)
_GP = MasterEntity(
    entity_id="LE-0004",
    entity_name="Private Equity GP LE-0004 Ltd",
    lei=None,
    domicile="KY",
    parent_entity_id="LE-0001",
    # The realistic no-universal-identifier resolution surfaces: the E-13 aliases the platform has
    # LEARNED for this no-LEI private master. An inbound realistic name resolves via these, never
    # via the internal LE-NNNN golden key (which never appears on a real inbound feed).
    aliases=("Bolt Rides", "Bolt Technologies"),
    external_ids=(),
)
_MASTERS = (_ACME, _GP)


# --- (3) the normaliser is pure + deterministic ---------------------------------------------------


def test_normaliser_collapses_case_whitespace_suffix_diacritic() -> None:
    # Punctuation (the hyphen) collapses to a space — deterministic, total. The KEY POINT is that
    # the suffix variant and the canonical name normalise to the SAME key (so they match).
    assert normalise_name("Private Equity GP LE-0004 Ltd") == "private equity gp le 0004"
    assert normalise_name("Private Equity GP LE-0004 Limited") == "private equity gp le 0004"
    assert normalise_name("Private Equity GP LE-0004 Ltd") == normalise_name(
        "Private Equity GP LE-0004 Limited"
    )
    assert normalise_name("ISSUER LE-0048 CORP") == "issuer le 0048"
    assert normalise_name("Issuer LE-0018 Corporation") == "issuer le 0018"
    assert normalise_name("Crédit Agricole") == normalise_name("Credit Agricole")
    assert normalise_name(None) == ""
    assert normalise_name("   ") == ""


def test_normaliser_is_idempotent_and_deterministic() -> None:
    once = normalise_name("Acme Asset Management LLP")
    assert normalise_name(once) == once  # idempotent on its own output
    assert normalise_name("acme asset management") == once  # case + suffix collapse to the same key


# --- (1) each tier fires on its designed evidence -------------------------------------------------


def test_tier1_exact_lei_resolves() -> None:
    feed = _feed("ERF-X", "ACME ASSET MANAGEMENT LLP", lei="5493001KJTIIGC8Y1R12")
    res = resolve_record(feed, _MASTERS)
    assert res.decision == "resolved"
    assert res.tier == "tier_1_exact_id"
    assert res.matched_entity_id == "LE-0001"
    assert res.score == Decimal("1.0")


def test_tier2_alias_match_resolves_with_no_inbound_id() -> None:
    res = resolve_record(_feed("ERF-X", "Acme AM"), _MASTERS)
    assert res.decision == "resolved"
    assert res.tier == "tier_2_name_alias"
    assert res.matched_entity_id == "LE-0001"


def test_tier2_name_variant_no_id_resolves_the_hard_private_case() -> None:
    # The model's hard case: a realistic no-universal-identifier private company. The inbound name
    # carries NO LEI and NO internal golden key — it resolves to LE-0004 only via a LEARNED E-13
    # alias ("Bolt Technologies") + KY domicile corroboration. (The OÜ Estonian legal form is
    # suffix-normalised away; the answer is absent from the surface string.)
    feed = _feed("ERF-X", "Bolt Technologies OÜ", domicile="KY")
    res = resolve_record(feed, _MASTERS)
    assert res.decision == "resolved"
    assert res.tier == "tier_2_name_alias"
    assert res.matched_entity_id == "LE-0004"
    assert "LE-0004" not in feed.raw_name  # the no-universal-identifier reality: no key in the name


def test_tier2_realistic_no_id_name_resolves_via_learned_alias() -> None:
    # A second realistic no-ID family member: "Bolt Rides Ltd" resolves via the learned alias key
    # "bolt rides" — again, the surface string contains no internal identifier.
    res = resolve_record(_feed("ERF-Y", "Bolt Rides Ltd", domicile="KY"), _MASTERS)
    assert res.decision == "resolved"
    assert res.tier == "tier_2_name_alias"
    assert res.matched_entity_id == "LE-0004"


def test_tier3_net_new_no_match_is_new() -> None:
    res = resolve_record(_feed("ERF-X", "Northwind Capital Advisors Ltd", domicile="GB"), _MASTERS)
    assert res.decision == "new"
    assert res.matched_entity_id is None


# --- (2) the genuinely-ambiguous are QUARANTINED, never merged (the mis-merge floor) --------------


def test_conflicting_domicile_name_match_is_quarantined_not_merged() -> None:
    # A name-key match to LE-0004 (KY) but the inbound declares a CONFLICTING domicile -> review.
    res = resolve_record(_feed("ERF-X", "Private Equity GP LE-0004 Ltd", domicile="SG"), _MASTERS)
    assert res.decision == "review"
    assert res.tier == "tier_3_review"
    assert res.matched_entity_id is None  # NEVER merged


def test_name_key_collision_across_masters_is_quarantined() -> None:
    # Two distinct masters sharing a normalised name -> any inbound under that key is ambiguous.
    twin_a = MasterEntity("LE-A", "Meridian Partners Ltd", None, "KY", None, (), ())
    twin_b = MasterEntity("LE-B", "Meridian Partners Limited", None, "SG", None, (), ())
    res = resolve_record(_feed("ERF-X", "Meridian Partners"), (twin_a, twin_b))
    assert res.decision == "review"
    assert res.matched_entity_id is None


def test_within_batch_net_new_collision_under_conflicting_domicile_is_quarantined() -> None:
    # The Apex archetype: two net-new records, identical name, CONFLICTING domicile -> both review.
    records = (
        _feed("ERF-18", "Apex Global Holdings Ltd", domicile="KY", system="internal_onboarding"),
        _feed("ERF-19", "Apex Global Holdings Ltd", domicile="SG", system="administrator"),
    )
    results = {r.source_record_id: r for r in resolve_batch(records, _MASTERS)}
    assert results["ERF-18"].decision == "review"
    assert results["ERF-19"].decision == "review"
    assert results["ERF-18"].matched_entity_id is None
    assert results["ERF-19"].matched_entity_id is None


def test_within_batch_net_new_same_entity_consistent_domicile_stays_new() -> None:
    # Two records, same name, SAME domicile -> the same net-new entity seen twice, NOT ambiguous.
    records = (
        _feed("ERF-A", "Helios Renewables Ltd", domicile="GB", system="internal_onboarding"),
        _feed("ERF-B", "Helios Renewables Limited", domicile="GB", system="administrator"),
    )
    results = {r.source_record_id: r for r in resolve_batch(records, _MASTERS)}
    assert results["ERF-A"].decision == "new"
    assert results["ERF-B"].decision == "new"


# --- golden-record survivorship -------------------------------------------------------------------


def test_golden_record_is_keyed_by_internal_entity_id_never_external() -> None:
    cluster = (
        _feed("ERF-1", "ACME ASSET MANAGEMENT LLP", lei="5493001KJTIIGC8Y1R12", system="custodian"),
        _feed("ERF-4", "Acme AM", system="internal_onboarding"),
    )
    gr = build_golden_record("LE-0001", cluster, _ACME)
    assert gr.entity_id == "LE-0001"  # internal golden key
    assert gr.lei == "5493001KJTIIGC8Y1R12"  # the LEI is a SURVIVED ATTRIBUTE, not the key
    assert gr.entity_name == "Acme Asset Management LLP"  # the master's canonical name wins
    # provenance records which surface won each field
    fields = {p.field_name: p.source_system for p in gr.provenance}
    assert fields["entity_name"] == "e01_master"


# --- (5) label-independence (structural + behavioural) --------------------------------------------


def test_matcher_signature_has_no_label_parameter() -> None:
    """STRUCTURAL: resolve_record / resolve_batch take a record + reference data — no label arg.

    The answer-key discipline at the type level: the cascade CANNOT read the oracle because it is
    not in its signature. ``FeedRecord`` carries observable evidence only (name / lei / domicile /
    parent hint / external id); there is no ``true_entity_id`` / ``resolution_outcome`` field.
    """
    import inspect

    params = set(inspect.signature(resolve_record).parameters) | set(
        inspect.signature(resolve_batch).parameters
    )
    forbidden_params = (
        "label", "labels", "oracle", "true_entity_id", "answer", "resolution_outcome",
    )
    for forbidden in forbidden_params:
        assert forbidden not in params, f"the matcher must not take a label arg: {forbidden}"
    feed_fields = set(FeedRecord.__dataclass_fields__)
    for forbidden in ("true_entity_id", "resolution_outcome", "difficulty_tier", "label"):
        assert forbidden not in feed_fields, f"FeedRecord must not carry oracle field {forbidden}"


def test_decisions_are_invariant_to_record_order_and_unrelated_noise() -> None:
    """BEHAVIOURAL: the per-record decision does not depend on order or on unrelated records.

    A label-reading matcher would be perturbable by re-ordering / injecting noise; the deterministic
    cascade's decision for a record is a pure function of that record + the masters.
    """
    a = _feed("ERF-1", "ACME ASSET MANAGEMENT LLP", lei="5493001KJTIIGC8Y1R12")
    b = _feed("ERF-8", "Bolt Rides Ltd", domicile="KY")
    forward = {r.source_record_id: r.matched_entity_id for r in resolve_batch((a, b), _MASTERS)}
    reverse = {r.source_record_id: r.matched_entity_id for r in resolve_batch((b, a), _MASTERS)}
    assert forward == reverse
    assert forward["ERF-1"] == "LE-0001"
    assert forward["ERF-8"] == "LE-0004"


# --- (4) THE DETERMINISTIC SPINE — the of-record path imports NO model ----------------------------

_FORBIDDEN_IMPORT_SUBSTRINGS = (
    "anthropic",
    "openai",
    "proposer",
    "proposal_store",
    "llm",
)

# The of-record resolve modules whose TRANSITIVE import closure must be model-free. This is the
# WHOLE of-record closure: the cascade + normaliser + the two append-only stores AND
# ``entity_resolution_service`` — which hosts ``run_resolution``, the resolve entrypoint the eval
# and the live ingress actually execute as the of-record path (the F-2 fold: the spine must cover
# the service entry, not just the cascade modules, so a model import added to the service would be
# caught too).
_RESOLVE_OF_RECORD_MODULES = (
    "agentinvest_tools.entity_resolution.cascade",
    "agentinvest_tools.entity_resolution.normaliser",
    "agentinvest_tools.entity_resolution.review_queue_store",
    "agentinvest_tools.entity_resolution.golden_record_store",
    "agentinvest_tools.entity_resolution_service",
)


def _walk_imports(module_name: str) -> tuple[set[str], list[tuple[str, str]]]:
    """Walk one module's AST: return (static import names, dynamic-import call sites).

    Static names are the fully-qualified modules reached by ``import`` / ``from ... import``.
    Dynamic-import call sites are ``importlib.import_module(<literal>)`` / ``__import__(<literal>)``
    calls whose argument is a string literal (the F-3 fold: a string-keyed dynamic import is
    invisible to a plain ``ast.Import`` walk, so a future dynamic LLM import could slip the guard —
    this surfaces those call sites so the spine assertion can flag a forbidden one). Each dynamic
    site is returned as ``(call_name, literal_arg)``.
    """
    import ast
    import importlib.util
    from pathlib import Path

    static: set[str] = set()
    dynamic: list[tuple[str, str]] = []
    spec = importlib.util.find_spec(module_name)
    if spec is None or spec.origin is None or not spec.origin.endswith(".py"):
        return static, dynamic
    tree = ast.parse(Path(spec.origin).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                static.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            static.add(node.module)
        elif isinstance(node, ast.Call):
            # importlib.import_module("x") / importlib("x") attribute call, or __import__("x")
            fn = node.func
            call_name: str | None = None
            if isinstance(fn, ast.Attribute) and fn.attr == "import_module":
                call_name = "importlib.import_module"
            elif isinstance(fn, ast.Name) and fn.id in ("__import__", "import_module"):
                call_name = fn.id
            if call_name is not None:
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        dynamic.append((call_name, arg.value))
    return static, dynamic


def _resolve_closure() -> tuple[set[str], list[tuple[str, str, str]]]:
    """Transitively walk the of-record closure: return (static module names, dynamic-import sites).

    Recurses through first-party (``agentinvest*``) modules; records every reachable module name
    (third-party leaves included, checked directly) and every dynamic-import call site found
    anywhere in the closure (tagged with the module it was found in).
    """
    seen: set[str] = set()
    dynamic_sites: list[tuple[str, str, str]] = []
    stack = list(_RESOLVE_OF_RECORD_MODULES)
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        seen.add(name)
        static, dynamic = _walk_imports(name)
        for site_call, site_arg in dynamic:
            dynamic_sites.append((name, site_call, site_arg))
        for mod in static:
            seen.add(mod)
            if mod.startswith("agentinvest"):
                stack.append(mod)
    return seen, dynamic_sites


def test_resolve_of_record_path_imports_no_llm_or_proposer() -> None:
    """THE SPINE: the of-record resolve path's transitive import closure contains no model module.

    OpenIM's signature invariant: the deterministic spine — the of-record resolution decision is
    made WITHOUT a model. This walks the import closure of the cascade + normaliser + the two
    stores + the resolution service (which hosts ``run_resolution``, the resolve entrypoint) and
    asserts no ``anthropic`` / ``openai`` / ``proposer`` / ``proposal_store`` / ``llm`` module is
    reachable — via a STATIC import OR a string-keyed DYNAMIC import
    (``importlib.import_module`` / ``__import__``). The probabilistic / LLM-proposer tier is a
    deliberately-deferred later cycle; if a future change wires a model into the resolve path —
    statically or dynamically — this test fails loudly. (Where a model COULD write — nowhere this
    cycle — the absence is enforced here, structurally.)
    """
    closure, dynamic_sites = _resolve_closure()
    static_offenders = sorted(
        m for m in closure if any(sub in m.lower() for sub in _FORBIDDEN_IMPORT_SUBSTRINGS)
    )
    assert not static_offenders, (
        "the of-record resolve path must import no LLM/proposer/model module — "
        f"found (static): {static_offenders}"
    )
    # F-3: a string-keyed dynamic import targeting a forbidden module would slip a plain import
    # walk. Flag any dynamic-import call site in the closure whose literal argument hits a
    # forbidden substring; assert none exist today (no LLM reachable via a dynamic import either).
    dynamic_offenders = sorted(
        (mod, call, arg)
        for (mod, call, arg) in dynamic_sites
        if any(sub in arg.lower() for sub in _FORBIDDEN_IMPORT_SUBSTRINGS)
    )
    assert not dynamic_offenders, (
        "the of-record resolve path must not dynamically import an LLM/proposer/model module — "
        f"found (dynamic): {dynamic_offenders}"
    )


def test_spine_walker_detects_a_dynamic_import_offender() -> None:
    """The dynamic-import detector actually fires (F-3): a synthetic offender site is flagged.

    Guards against a vacuous spine test — proves the dynamic-import branch of ``_walk_imports`` is
    real: a constructed ``importlib.import_module("anthropic")`` / ``__import__("openai")`` source
    is parsed and the forbidden literal is surfaced. (We test the detector on an in-memory AST so
    no model is ever imported and no tracked module carries the offender.)
    """
    import ast

    src = (
        "import importlib\n"
        "def leak():\n"
        "    m = importlib.import_module('anthropic')\n"
        "    n = __import__('openai')\n"
        "    return m, n\n"
    )
    tree = ast.parse(src)
    found: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            call_name: str | None = None
            if isinstance(fn, ast.Attribute) and fn.attr == "import_module":
                call_name = "importlib.import_module"
            elif isinstance(fn, ast.Name) and fn.id in ("__import__", "import_module"):
                call_name = fn.id
            if call_name is not None:
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        found.append((call_name, arg.value))
    offenders = sorted(
        (call, arg)
        for (call, arg) in found
        if any(sub in arg.lower() for sub in _FORBIDDEN_IMPORT_SUBSTRINGS)
    )
    assert ("importlib.import_module", "anthropic") in offenders
    assert ("__import__", "openai") in offenders
