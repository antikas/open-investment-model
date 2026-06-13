"""The entityResolution model-free service — registration + dispatch shape.

Proves the SD-13.2 resolution service is wired correctly and additively:

1. the three SOs (resolve_batch · get_golden_record · list_review_queue) are registered with typed
   I/O schemas;
2. the orchestrator tool catalogue aggregates them ADDITIVELY (bd09 / bd12 / bd12Recon descriptors
   unperturbed; the entityResolution tools appended);
3. the MCP SO->service prefix router maps SO-13.2- to entityResolution, and the existing prefixes
   (SO-09- / SO-12.10- / SO-12.) are unperturbed;
4. the pure resolution run produces golden rows for the resolved + review items for the ambiguous,
   keyed by the internal entity_id — the dispatch shape, exercised without the Restate runtime.

These are pure / in-process tests — no Restate ingress, no canonical store. The end-to-end ingress
round-trip (mirrored-aware ``pnpm dev:restate``) is proven separately.
"""

from __future__ import annotations

from datetime import date

from agentinvest_tools.entity_resolution import FeedRecord, MasterEntity
from agentinvest_tools.entity_resolution_service import (
    _REGISTRY,
    ENTITY_RESOLUTION_SERVICE_NAME,
    GOLDEN_SO_ID,
    RESOLVE_SO_ID,
    REVIEW_SO_ID,
    run_resolution,
)


def test_three_sos_are_registered_with_typed_schemas() -> None:
    assert set(_REGISTRY) == {RESOLVE_SO_ID, GOLDEN_SO_ID, REVIEW_SO_ID}
    for spec in _REGISTRY.values():
        schema = spec.input_model.model_json_schema()
        assert schema["type"] == "object"
        assert spec.output_model.model_json_schema()["type"] == "object"
    assert _REGISTRY[RESOLVE_SO_ID].name == "resolve_batch"
    assert _REGISTRY[GOLDEN_SO_ID].name == "get_golden_record"
    assert _REGISTRY[REVIEW_SO_ID].name == "list_review_queue"
    assert ENTITY_RESOLUTION_SERVICE_NAME == "entityResolution"


def test_tool_catalogue_appends_entity_resolution_additively() -> None:
    """The aggregate catalogue ends with the three SD-13.2 tools; bd09 leads unperturbed."""
    from agentinvest_orchestrator.tool_catalogue import (
        load_tool_catalogue_from_bd09,
        load_tool_catalogue_from_entity_resolution,
        load_tool_catalogue_from_services,
    )

    bd09 = load_tool_catalogue_from_bd09("any")
    er = load_tool_catalogue_from_entity_resolution("any")
    agg = load_tool_catalogue_from_services("any")
    # bd09 leads byte-for-byte (the NAV path is unperturbed)
    assert agg[: len(bd09)] == bd09
    # the entity-resolution tools are the tail, appended
    assert agg[-len(er):] == er
    er_so_ids = {d.so_id for d in er}
    assert er_so_ids == {RESOLVE_SO_ID, GOLDEN_SO_ID, REVIEW_SO_ID}


def test_mcp_prefix_router_maps_sd132_to_entity_resolution_unperturbed() -> None:
    """SO-13.2- routes to entityResolution; the existing prefixes are unchanged + correctly
    ordered."""
    from agentinvest_tools.mcp_server import _owning_service

    assert _owning_service("SO-13.2-01") == "entityResolution"
    assert _owning_service("SO-13.2-02") == "entityResolution"
    # the existing prefixes are unperturbed (SO-12.10- still beats SO-12.)
    assert _owning_service("SO-09-01") == "bd09"
    assert _owning_service("SO-12.10-01") == "bd12Recon"
    assert _owning_service("SO-12.1-01") == "bd12"
    assert _owning_service("SO-99-99") is None


def _feed(src: str, name: str, **kw: object) -> FeedRecord:
    return FeedRecord(
        source_record_id=src,
        source_system=str(kw.get("system", "custodian")),
        raw_name=name,
        raw_lei=kw.get("lei"),  # type: ignore[arg-type]
        raw_domicile=kw.get("domicile"),  # type: ignore[arg-type]
        raw_parent_hint=None,
        raw_external_id=kw.get("ext"),  # type: ignore[arg-type]
        raw_id_type=None,
        received_at=date(2026, 1, 15),
    )


def test_run_resolution_shape_golden_for_resolved_review_for_ambiguous() -> None:
    """The pure run: a resolved record -> a golden row keyed by entity_id; an ambiguous ->
    review."""
    master = MasterEntity("LE-0004", "Private Equity GP LE-0004 Ltd", None, "KY", "LE-0001", (), ())
    gp = "Private Equity GP LE-0004 Ltd"
    feed = (
        _feed("ERF-8", gp, domicile="KY", system="internal_onboarding"),
        _feed("ERF-X", gp, domicile="SG", system="administrator"),
    )
    run = run_resolution((master,), feed, "2026-01-31")
    decisions = {r.source_record_id: r.decision for r in run.results}
    assert decisions["ERF-8"] == "resolved"
    assert decisions["ERF-X"] == "review"  # conflicting domicile -> quarantined, never merged
    # one golden row for the resolved cluster, keyed by the internal entity_id
    assert len(run.golden_rows) == 1
    assert run.golden_rows[0].entity_id == "LE-0004"
    # one review item for the quarantined record
    assert len(run.review_items) == 1
    assert run.review_items[0].source_record_id == "ERF-X"
    assert run.review_items[0].tier == "tier_3_review"
