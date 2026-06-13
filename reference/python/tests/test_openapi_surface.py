"""The OpenAPI surface — Restate's auto-generated bd09 spec, fetched + validated + exposed.

Two tiers:

- **unit** (always run, CI-safe): the validator + the bd09-surface assertion + the docs ASGI app
  run over a *captured* auto-generated spec fixture (the real shape Restate emits for bd09) — no
  live server needed. Proves the spec is genuine OpenAPI 3.1, the typed envelope is present, and the
  ``/docs`` + ``/openapi.json`` surface serves;
- **integration** (skipped unless the shared Restate admin is reachable AND bd09 is registered):
  fetches the *live* auto-generated spec from Restate and validates it 3.1 + asserts the surface.
  This is the same code the live evidence drives; the unit tier locks it for CI.

The spec is Restate-generated from the handler signatures — these tests confirm the helper fetches
and validates it, never that a hand-written spec passes (the SSOT discipline).
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from agentinvest_tools.openapi_surface import (
    ADMIN_URL,
    assert_bd09_surface,
    fetch_service_openapi,
    is_openapi_31,
    make_docs_app,
    normalise_emitter_quirks,
    validate_openapi_spec,
)

# A captured fixture of the real auto-generated bd09 OpenAPI 3.1 spec shape (Restate 1.6.2). The
# execute_soRequest schema is the *typed* envelope (object naming soId/args) that the Pydantic
# ExecuteSoInput produces — the envelope-typing carry-forward at the surface. Trimmed to
# the load-bearing parts; a genuine OpenAPI 3.1 document.
_CAPTURED_SPEC: dict[str, Any] = {
    "openapi": "3.1.0",
    "info": {"title": "bd09", "version": "1.0"},
    "paths": {
        "/bd09/execute_so": {
            "post": {
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/execute_soRequest"}
                        }
                    },
                    "required": False,
                },
                "responses": {
                    "200": {
                        "description": "ok",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/execute_soResponse"}
                            }
                        },
                    }
                },
            }
        },
        "/bd09/list_capabilities": {
            "post": {
                "responses": {
                    "200": {
                        "description": "ok",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/list_capabilitiesResponse"
                                }
                            }
                        },
                    }
                }
            }
        },
    },
    "components": {
        "schemas": {
            "execute_soRequest": {
                "type": "object",
                "properties": {
                    "soId": {"type": "string", "title": "Soid"},
                    "args": {"type": "object", "additionalProperties": True, "title": "Args"},
                },
                "required": ["soId"],
                "title": "ExecuteSoInput",
            },
            "execute_soResponse": {"type": "object", "additionalProperties": True},
            "list_capabilitiesResponse": {"type": "object", "additionalProperties": True},
        }
    },
}


# --- unit: validate + surface-assert the captured auto-gen spec --------------------------------


def test_captured_spec_validates_as_openapi_31() -> None:
    version = validate_openapi_spec(_CAPTURED_SPEC)
    assert version == "3.1.0"
    assert is_openapi_31(_CAPTURED_SPEC)


def test_captured_spec_has_the_bd09_surface_with_a_typed_envelope() -> None:
    summary = assert_bd09_surface(_CAPTURED_SPEC)
    assert "/bd09/execute_so" in summary["handler_paths"]
    assert "/bd09/list_capabilities" in summary["handler_paths"]
    # The envelope-typing carry-forward at the surface: the request schema is a typed object,
    # not the permissive {} an untyped TypedDict envelope produced.
    assert summary["request_schema_typed"] is True


def test_an_untyped_envelope_would_be_caught() -> None:
    """A permissive ({}-shaped) request schema is flagged not-typed — the regression closed."""
    schemas = dict(_CAPTURED_SPEC["components"]["schemas"])
    schemas["execute_soRequest"] = {}
    untyped = {**_CAPTURED_SPEC, "components": {"schemas": schemas}}
    summary = assert_bd09_surface(untyped)
    assert summary["request_schema_typed"] is False


@pytest.mark.anyio
async def test_docs_app_serves_openapi_json_and_swagger_ui(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The /docs + /openapi.json surface serves the auto-gen spec + the Swagger UI render."""
    import json as _json

    import agentinvest_tools.openapi_surface as mod

    # Patch fetch to return the captured spec (no live server in the unit tier).
    monkeypatch.setattr(mod, "fetch_service_openapi", lambda *a, **k: _CAPTURED_SPEC)

    captured: dict[str, Any] = {}

    async def send(message: dict[str, Any]) -> None:
        if message["type"] == "http.response.start":
            captured["status"] = message["status"]
        elif message["type"] == "http.response.body":
            captured["body"] = message["body"]

    async def receive() -> dict[str, Any]:  # pragma: no cover - not read by the app
        return {"type": "http.request"}

    app = make_docs_app()
    await app({"type": "http", "path": "/openapi.json"}, receive, send)
    assert captured["status"] == 200
    assert _json.loads(captured["body"])["openapi"] == "3.1.0"

    await app({"type": "http", "path": "/docs"}, receive, send)
    assert captured["status"] == 200
    assert b"swagger-ui" in captured["body"]
    # SRI is present on the CDN assets (no integrity-free external script).
    assert b"integrity=" in captured["body"]


# --- well-formed JSON error responses + the programmatic served check --------------------------


@pytest.mark.anyio
async def test_docs_app_unknown_path_is_a_structured_json_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unknown path returns a well-formed STRUCTURED JSON 404 (not bare text/plain).

    ``make_docs_app`` previously returned a bare ``text/plain`` "not found". A programmatic
    consumer (and the curl smoke) needs a machine-parseable error envelope —
    ``{"error": "not_found", "detail": "<path>"}`` with ``application/json`` and status 404.
    """
    import json as _json

    import agentinvest_tools.openapi_surface as mod

    monkeypatch.setattr(mod, "fetch_service_openapi", lambda *a, **k: _CAPTURED_SPEC)

    captured: dict[str, Any] = {}

    async def send(message: dict[str, Any]) -> None:
        if message["type"] == "http.response.start":
            captured["status"] = message["status"]
            captured["headers"] = dict(message["headers"])
        elif message["type"] == "http.response.body":
            captured["body"] = message["body"]

    async def receive() -> dict[str, Any]:  # pragma: no cover - not read by the app
        return {"type": "http.request"}

    app = make_docs_app()
    await app({"type": "http", "path": "/no-such-path"}, receive, send)

    assert captured["status"] == 404
    # Content-type is application/json (the structured-error contract), not text/plain.
    assert captured["headers"].get(b"content-type") == b"application/json"
    payload = _json.loads(captured["body"])
    assert payload == {"error": "not_found", "detail": "/no-such-path"}


@pytest.mark.anyio
async def test_docs_app_200_paths_unregressed_by_the_json_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The /docs + /openapi.json 200s are unregressed after the JSON-404 change."""
    import json as _json

    import agentinvest_tools.openapi_surface as mod

    monkeypatch.setattr(mod, "fetch_service_openapi", lambda *a, **k: _CAPTURED_SPEC)

    captured: dict[str, Any] = {}

    async def send(message: dict[str, Any]) -> None:
        if message["type"] == "http.response.start":
            captured["status"] = message["status"]
            captured["headers"] = dict(message["headers"])
        elif message["type"] == "http.response.body":
            captured["body"] = message["body"]

    async def receive() -> dict[str, Any]:  # pragma: no cover - not read by the app
        return {"type": "http.request"}

    app = make_docs_app()

    await app({"type": "http", "path": "/openapi.json"}, receive, send)
    assert captured["status"] == 200
    assert captured["headers"].get(b"content-type") == b"application/json"
    assert _json.loads(captured["body"])["openapi"] == "3.1.0"

    await app({"type": "http", "path": "/docs"}, receive, send)
    assert captured["status"] == 200
    assert captured["headers"].get(b"content-type") == b"text/html; charset=utf-8"


@pytest.mark.anyio
async def test_swagger_ui_served_with_sri_pinned_assets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The programmatic Swagger-UI-served check — the autonomous proxy.

    Over the fixture path (no live server): ``/docs`` serves 200 HTML carrying the SRI-pinned
    Swagger asset references (a pinned version + an ``integrity=`` sha384 on BOTH the CSS and the
    JS, plus ``crossorigin``), and ``/openapi.json`` serves the validated 3.1 spec with the typed
    envelope present. The interactive in-browser click-through is checked separately.
    """
    import json as _json

    import agentinvest_tools.openapi_surface as mod

    monkeypatch.setattr(mod, "fetch_service_openapi", lambda *a, **k: _CAPTURED_SPEC)

    captured: dict[str, Any] = {}

    async def send(message: dict[str, Any]) -> None:
        if message["type"] == "http.response.start":
            captured["status"] = message["status"]
        elif message["type"] == "http.response.body":
            captured["body"] = message["body"]

    async def receive() -> dict[str, Any]:  # pragma: no cover - not read by the app
        return {"type": "http.request"}

    app = make_docs_app()

    # /docs: 200 HTML with the SRI-pinned Swagger assets.
    await app({"type": "http", "path": "/docs"}, receive, send)
    assert captured["status"] == 200
    html = captured["body"]
    assert b"swagger-ui" in html
    # The pinned version + SRI integrity on BOTH the CSS and the JS asset.
    assert b"swagger-ui-dist@" in html
    assert html.count(b"integrity=") >= 2, "expected SRI integrity on both the CSS and the JS asset"
    assert b"sha384-" in html
    assert b'crossorigin="anonymous"' in html
    # The render points at the live ./openapi.json (the auto-gen spec), not a hand-written copy.
    assert b'url: "./openapi.json"' in html

    # /openapi.json: 200 the validated 3.1 spec with the typed envelope.
    await app({"type": "http", "path": "/openapi.json"}, receive, send)
    assert captured["status"] == 200
    spec = _json.loads(captured["body"])
    assert is_openapi_31(spec)
    summary = assert_bd09_surface(spec)
    assert summary["request_schema_typed"] is True


# --- the /openapi.json upstream fetch is guarded → a well-formed 503 (not a 500) --------------
#
# ``make_docs_app``'s ``/openapi.json`` branch calls ``fetch_service_openapi`` (which
# ``raise_for_status()``es), so an admin-down/unreachable/timeout/5xx (or a malformed spec body)
# would RAISE inside the ASGI handler → an unhandled 500/crash. The guard wraps it so EVERY upstream
# failure surfaces a well-formed structured JSON 503 (``{"error":"upstream_unavailable",...}``,
# ``application/json``) — mirroring the sibling 404 envelope. These tests drive the docs app over a
# failing fetch (a raised transport error, a real 5xx through ``httpx.MockTransport``, a malformed
# body) → 503; admin-up → 200 unregressed; the ``detail`` leaks no ingress URL/secret/stack-trace.
# They are revert-sensitive: remove the guard and the admin-down cases error/500 instead of 503.


@pytest.mark.anyio
async def test_docs_app_openapi_json_admin_down_is_a_structured_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Admin down / fetch raises a transport error → a well-formed 503 JSON, no unhandled exception.

    The guard catches the ``httpx.HTTPError`` ``fetch_service_openapi`` raises when the Restate
    admin is unreachable and returns the ``upstream_unavailable`` 503 envelope instead of crashing.
    """
    import json as _json

    import agentinvest_tools.openapi_surface as mod

    def _raises(*a: Any, **k: Any) -> dict[str, Any]:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(mod, "fetch_service_openapi", _raises)

    captured: dict[str, Any] = {}

    async def send(message: dict[str, Any]) -> None:
        if message["type"] == "http.response.start":
            captured["status"] = message["status"]
            captured["headers"] = dict(message["headers"])
        elif message["type"] == "http.response.body":
            captured["body"] = message["body"]

    async def receive() -> dict[str, Any]:  # pragma: no cover - not read by the app
        return {"type": "http.request"}

    app = make_docs_app()
    # The handler must NOT raise (the crash this item closes) — it returns a clean 503.
    await app({"type": "http", "path": "/openapi.json"}, receive, send)

    assert captured["status"] == 503
    assert captured["headers"].get(b"content-type") == b"application/json"
    payload = _json.loads(captured["body"])
    assert payload["error"] == "upstream_unavailable"
    assert isinstance(payload["detail"], str) and payload["detail"]


@pytest.mark.anyio
async def test_docs_app_openapi_json_admin_5xx_is_a_structured_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A real 5xx from the admin (through ``httpx.MockTransport``) → 503 — the REAL fetch path.

    Drives ``fetch_service_openapi`` for real over a ``MockTransport`` that returns a 503, so the
    ``raise_for_status()`` ``HTTPStatusError`` is the thing the guard catches (not a stubbed raise).
    """
    import json as _json

    def admin_5xx(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="service unavailable")

    transport = httpx.MockTransport(admin_5xx)

    def _get_via_mock(url: str, **kwargs: Any) -> httpx.Response:
        # Route the real fetch's httpx.get through the mock transport (no live :9091).
        # ``fetch_service_openapi`` calls ``httpx.get`` resolved against this same ``httpx`` module
        # object, so patching it here exercises the REAL fetch + ``raise_for_status()`` path.
        with httpx.Client(transport=transport) as client:
            return client.get(url)

    monkeypatch.setattr(httpx, "get", _get_via_mock)

    captured: dict[str, Any] = {}

    async def send(message: dict[str, Any]) -> None:
        if message["type"] == "http.response.start":
            captured["status"] = message["status"]
            captured["headers"] = dict(message["headers"])
        elif message["type"] == "http.response.body":
            captured["body"] = message["body"]

    async def receive() -> dict[str, Any]:  # pragma: no cover - not read by the app
        return {"type": "http.request"}

    app = make_docs_app(admin_url="http://admin.invalid:9070")
    await app({"type": "http", "path": "/openapi.json"}, receive, send)

    assert captured["status"] == 503
    assert captured["headers"].get(b"content-type") == b"application/json"
    payload = _json.loads(captured["body"])
    assert payload == {
        "error": "upstream_unavailable",
        "detail": "cannot reach the Restate admin API to fetch the OpenAPI spec; retry",
    }


@pytest.mark.anyio
async def test_docs_app_openapi_json_malformed_spec_is_a_structured_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fetched-but-malformed spec body (a parse/normalise failure) → 503, not a crash."""
    import json as _json

    import agentinvest_tools.openapi_surface as mod

    def _bad_body(*a: Any, **k: Any) -> dict[str, Any]:
        # ``resp.json()`` raised inside the fetch on a non-JSON body — a ValueError class.
        raise ValueError("Expecting value: line 1 column 1 (char 0)")

    monkeypatch.setattr(mod, "fetch_service_openapi", _bad_body)

    captured: dict[str, Any] = {}

    async def send(message: dict[str, Any]) -> None:
        if message["type"] == "http.response.start":
            captured["status"] = message["status"]
            captured["headers"] = dict(message["headers"])
        elif message["type"] == "http.response.body":
            captured["body"] = message["body"]

    async def receive() -> dict[str, Any]:  # pragma: no cover - not read by the app
        return {"type": "http.request"}

    app = make_docs_app()
    await app({"type": "http", "path": "/openapi.json"}, receive, send)

    assert captured["status"] == 503
    assert _json.loads(captured["body"])["error"] == "upstream_unavailable"


@pytest.mark.anyio
async def test_docs_app_503_detail_leaks_no_url_secret_or_stacktrace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The 503 ``detail`` names the upstream condition only — no ingress URL / secret / stack-trace.

    The raised error carries the admin URL + a fake token in its text; the consumer-facing
    ``detail`` must contain none of it (it is a fixed, clean message, not the exception string).
    """
    import json as _json

    import agentinvest_tools.openapi_surface as mod

    leaky_url = "http://admin.invalid:9070/services/bd09/openapi?token=SECRET-abc123"

    def _raises(*a: Any, **k: Any) -> dict[str, Any]:
        raise httpx.ConnectError(f"connection refused to {leaky_url}")

    monkeypatch.setattr(mod, "fetch_service_openapi", _raises)

    captured: dict[str, Any] = {}

    async def send(message: dict[str, Any]) -> None:
        if message["type"] == "http.response.start":
            captured["status"] = message["status"]
        elif message["type"] == "http.response.body":
            captured["body"] = message["body"]

    async def receive() -> dict[str, Any]:  # pragma: no cover - not read by the app
        return {"type": "http.request"}

    app = make_docs_app(admin_url=leaky_url)
    await app({"type": "http", "path": "/openapi.json"}, receive, send)

    raw = captured["body"].decode()
    payload = _json.loads(raw)
    assert captured["status"] == 503
    # No ingress topology, credential, or stack-trace marker leaks into the consumer body.
    for leaked in ("admin.invalid", "9070", "SECRET", "token", "Traceback", "/services/"):
        assert leaked not in raw, f"the 503 body leaked {leaked!r}: {raw!r}"
    assert payload["detail"] == (
        "cannot reach the Restate admin API to fetch the OpenAPI spec; retry"
    )


@pytest.mark.anyio
async def test_docs_app_admin_up_unregressed_by_the_503_guard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Admin up → /openapi.json 200 the live validated spec; /docs 200; unknown → 404 JSON.

    The guard must not regress the happy paths: a successful fetch still 200s the spec, the Swagger
    page still serves, and the unknown-path 404 envelope is unchanged.
    """
    import json as _json

    import agentinvest_tools.openapi_surface as mod

    monkeypatch.setattr(mod, "fetch_service_openapi", lambda *a, **k: _CAPTURED_SPEC)

    captured: dict[str, Any] = {}

    async def send(message: dict[str, Any]) -> None:
        if message["type"] == "http.response.start":
            captured["status"] = message["status"]
            captured["headers"] = dict(message["headers"])
        elif message["type"] == "http.response.body":
            captured["body"] = message["body"]

    async def receive() -> dict[str, Any]:  # pragma: no cover - not read by the app
        return {"type": "http.request"}

    app = make_docs_app()

    # /openapi.json → 200 the validated 3.1 spec (the typed envelope present).
    await app({"type": "http", "path": "/openapi.json"}, receive, send)
    assert captured["status"] == 200
    assert captured["headers"].get(b"content-type") == b"application/json"
    spec = _json.loads(captured["body"])
    assert is_openapi_31(spec)
    assert assert_bd09_surface(spec)["request_schema_typed"] is True

    # /docs → 200 HTML.
    await app({"type": "http", "path": "/docs"}, receive, send)
    assert captured["status"] == 200
    assert captured["headers"].get(b"content-type") == b"text/html; charset=utf-8"

    # unknown → 404 structured JSON (unregressed).
    await app({"type": "http", "path": "/no-such-path"}, receive, send)
    assert captured["status"] == 404
    assert captured["headers"].get(b"content-type") == b"application/json"
    assert _json.loads(captured["body"]) == {"error": "not_found", "detail": "/no-such-path"}


# --- the emitter-quirk normalisation is scoped -------------------------------------------------
#
# A whole-spec recursive normalisation would drop EVERY null-valued dict key across the spec, which
# would silently corrupt a real tool schema the moment a tool gains an optional parameter: an
# ``Optional[str] = Field(default=None)`` emits ``"default": null`` (the default would vanish) and a
# ``const: null`` would invert. ``normalise_emitter_quirks`` is now path-scoped to Restate's
# externalDocs emitter quirk, so a MEANINGFUL schema null survives while the quirk is stripped.


def test_normalise_strips_only_the_externaldocs_emitter_quirk() -> None:
    """The Restate ``tags[].externalDocs.description: null`` quirk is stripped (so 3.1-valid)."""
    spec_with_quirk = {
        "openapi": "3.1.0",
        "info": {"title": "bd09", "version": "1.0"},
        "tags": [
            {"name": "bd09", "externalDocs": {"url": "https://x", "description": None}},
        ],
        "paths": {},
    }
    normalised = normalise_emitter_quirks(spec_with_quirk)
    # The spurious null description is gone (the only thing the normalisation touches).
    assert "description" not in normalised["tags"][0]["externalDocs"]
    assert normalised["tags"][0]["externalDocs"]["url"] == "https://x"
    # And the result is genuinely 3.1-valid (the quirk was what a strict validator rejected).
    assert validate_openapi_spec(spec_with_quirk) == "3.1.0"


def test_normalise_preserves_a_meaningful_schema_null() -> None:
    """A real tool schema's ``default: null`` / ``const: null`` / ``enum [.., null]`` is PRESERVED.

    This is the corruption the recursive whole-spec strip would have caused on the next
    optional-parameter tool — the scoped normalisation must leave every meaningful schema null
    intact while still stripping the externalDocs emitter quirk.
    """
    spec = {
        "openapi": "3.1.0",
        "info": {"title": "bd09", "version": "1.0"},
        "tags": [
            {"name": "bd09", "externalDocs": {"url": "https://x", "description": None}},
        ],
        "paths": {},
        "components": {
            "schemas": {
                "FutureToolInput": {
                    "type": "object",
                    "properties": {
                        # The single most common optional-parameter idiom: Optional[str]=None.
                        "risk_free_rate": {
                            "anyOf": [{"type": "string"}, {"type": "null"}],
                            "default": None,
                            "title": "Risk Free Rate",
                        },
                        # A field that MUST be null — const: null (recursive strip would invert it).
                        "sentinel": {"const": None, "title": "Sentinel"},
                        # An enum admitting null as a member.
                        "mode": {"enum": ["a", "b", None], "title": "Mode"},
                    },
                    "title": "FutureToolInput",
                },
            }
        },
    }
    normalised = normalise_emitter_quirks(spec)
    schema = normalised["components"]["schemas"]["FutureToolInput"]["properties"]

    # The meaningful nulls all survive — the next optional-parameter tool is published correctly.
    assert "default" in schema["risk_free_rate"], "default:null was dropped (schema corrupted)"
    assert schema["risk_free_rate"]["default"] is None
    assert "const" in schema["sentinel"], "const:null was dropped (must-be-null inverted)"
    assert schema["sentinel"]["const"] is None
    assert None in schema["mode"]["enum"], "enum null member was dropped"

    # ...while the externalDocs emitter quirk is still stripped.
    assert "description" not in normalised["tags"][0]["externalDocs"]

    # And the normalised spec is still genuine OpenAPI 3.1.
    assert validate_openapi_spec(spec) == "3.1.0"
    assert is_openapi_31(normalised)


# --- integration: the LIVE auto-gen spec (skipped if Restate/bd09 unreachable) -----------------


def _bd09_registered() -> bool:
    try:
        resp = httpx.get(f"{ADMIN_URL}/services/bd09/openapi", timeout=3.0)
        return resp.status_code == 200
    except Exception:
        return False


@pytest.mark.skipif(not _bd09_registered(), reason="shared Restate admin / bd09 not reachable")
def test_live_bd09_openapi_is_31_valid_with_typed_envelope() -> None:
    spec = fetch_service_openapi()
    version = validate_openapi_spec(spec)
    assert is_openapi_31(spec), f"live spec is {version}, expected 3.1"
    summary = assert_bd09_surface(spec)
    assert summary["request_schema_typed"] is True


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
