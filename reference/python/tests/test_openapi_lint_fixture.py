"""The committed captured-fixture OpenAPI spec is the genuine Restate emitter shape.

OIM-141: ``scripts/openapi-lint.mjs`` lints ``python/tests/fixtures/bd09-openapi.captured.json``
as the deterministic, server-free CI gate. That fixture is the NORMALISED live bd09 spec captured
from the real Restate service — NOT a hand-trimmed spec that could hide a defect the live spec has.
These tests lock that property: the committed fixture must stay a genuine OpenAPI 3.1 document, must
carry the bd09 handler surface + the typed ``execute_soRequest`` envelope, and must be free of the
``externalDocs.description: null`` emitter quirk (i.e. already normalised, the exact shape the lint
sees). If a future change trims the fixture to dodge a Spectral finding, one of these fails — the
lint cannot be gamed by a doctored fixture.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentinvest_tools.openapi_surface import (
    assert_bd09_surface,
    is_openapi_31,
    validate_openapi_spec,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "bd09-openapi.captured.json"


def _load() -> dict[str, Any]:
    return json.loads(_FIXTURE.read_text())  # type: ignore[no-any-return]


def test_captured_fixture_file_exists() -> None:
    assert _FIXTURE.is_file(), f"the lint gate's CI target is missing: {_FIXTURE}"


def test_captured_fixture_is_valid_openapi_31() -> None:
    spec = _load()
    assert validate_openapi_spec(spec) == "3.1.0"
    assert is_openapi_31(spec)


def test_captured_fixture_carries_the_bd09_surface_and_typed_envelope() -> None:
    """The fixture is the REAL bd09 surface — both handler paths + the typed envelope present."""
    spec = _load()
    summary = assert_bd09_surface(spec)
    assert "/bd09/execute_so" in summary["handler_paths"]
    assert "/bd09/list_capabilities" in summary["handler_paths"]
    assert summary["request_schema_typed"] is True


def test_captured_fixture_is_already_normalised() -> None:
    """No ``externalDocs.description: null`` survives — the fixture is the normalised shape linted.

    The lint runs on the normalised spec (the surface strips the emitter quirk before serving). The
    committed fixture must be in that same normalised state, so the CI lint target matches what a
    consumer actually fetches from ``/openapi.json``.
    """
    spec = _load()

    def _has_null_externaldocs_description(obj: Any) -> bool:
        if isinstance(obj, dict):
            ed = obj.get("externalDocs")
            if isinstance(ed, dict) and "description" in ed and ed["description"] is None:
                return True
            return any(_has_null_externaldocs_description(v) for v in obj.values())
        if isinstance(obj, list):
            return any(_has_null_externaldocs_description(v) for v in obj)
        return False

    assert not _has_null_externaldocs_description(spec), (
        "the captured fixture still carries the externalDocs null quirk — it is NOT normalised"
    )


def test_captured_fixture_is_the_full_restate_surface_not_trimmed() -> None:
    """The fixture is the FULL Restate emitter surface (the invoke patterns + the error schema).

    A guard against a hand-trimmed fixture: the genuine Restate auto-gen carries the /send +
    /restate/invocation/* invoke paths and the RestateError error schema beside the two handler
    paths. If those are gone, the fixture has been doctored down to a minimal hand-written spec —
    exactly what the SSOT discipline forbids (the surface tracks the handlers; the lint must see the
    whole emitted surface, not a curated subset).
    """
    spec = _load()
    paths = set(spec.get("paths", {}))
    assert "/bd09/execute_so/send" in paths, "missing the Restate /send invoke path (trimmed?)"
    assert any(p.startswith("/restate/invocation/") for p in paths), (
        "missing the Restate /restate/invocation/* invoke paths (trimmed?)"
    )
    schemas = spec.get("components", {}).get("schemas", {})
    assert "RestateError" in schemas, "missing the Restate generic-error schema (trimmed?)"
