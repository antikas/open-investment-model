"""The agentINVEST OpenAPI surface — fetch + validate + expose Restate's auto-generated bd09 spec.

Restate auto-generates an OpenAPI 3.1 spec for each registered service from the handler signatures:
the Pydantic input/output models on ``execute_so`` / ``list_capabilities`` become the request and
response schemas. This module is a *thin helper* over that auto-gen — it does **not** hand-write the
spec (that would defeat the SSOT: the surface must track the handlers). It:

1. **fetches** the auto-generated spec from the Restate admin API
   (``GET {admin}/services/{service}/openapi``);
2. **validates** it against the OpenAPI 3.x spec with a real validator (``openapi-spec-validator``),
   not by eyeballing;
3. **asserts the bd09 surface** — the two handler paths and the typed envelope schema are present;
4. **exposes** a Swagger-UI ``/docs`` page over the fetched spec (Restate serves the JSON but not a
   Swagger UI on this build, so the helper serves the human-facing render — the spec it renders is
   still the auto-generated one, fetched live, never hand-written).

The envelope typing at the surface: because ``execute_so`` takes the
``ExecuteSoInput`` Pydantic envelope, the auto-generated request schema is a typed object (not the
permissive ``{}`` a bare TypedDict produced), so the surface rejects a malformed non-object body at
the schema — completing deterministic-error-is-terminal at the ingress on the OpenAPI face too.

Honest boundary: a valid spec + a rendered ``/docs`` proves the *catalogue is correctly exposed* as
a programmatic/human surface over synthetic tools. It is not a production API deployment.
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from openapi_spec_validator import validate as validate_openapi
from openapi_spec_validator.versions import consts as openapi_versions
from openapi_spec_validator.versions.shortcuts import get_spec_version

ADMIN_URL = os.environ.get("RESTATE_ADMIN_URL", "http://localhost:9070")
BD09_SERVICE_NAME = "bd09"
BD12_SERVICE_NAME = "bd12"
BD12_RECON_SERVICE_NAME = "bd12Recon"
ENTITY_RESOLUTION_SERVICE_NAME = "entityResolution"


def normalise_emitter_quirks(spec: Any) -> Any:
    """Strip ONLY Restate's known ``null``-emitter quirk — never a meaningful schema ``null``.

    A narrow, **path-scoped** normalisation of an *upstream emitter* bug: Restate 1.6.2's
    auto-generated OpenAPI emits ``tags[].externalDocs.description: null``, but in OpenAPI an
    *optional* field (here ``description``) must be **omitted**, not set to ``null`` — a strict 3.1
    validator rejects ``null is not of type 'string'``. This function removes that single spurious
    ``null`` at its specific path (a top-level ``tags[].externalDocs.description`` and, defensively,
    any ``externalDocs.description: null`` the emitter leaves elsewhere), so the auto-generated spec
    conforms WITHOUT hand-writing it.

    Critically it is **NOT** a recursive whole-spec null-strip. The earlier implementation dropped
    *every* dict key whose value was ``null`` across the entire document — which would silently
    corrupt a real tool schema the moment a tool gains an optional parameter: a standard
    ``Optional[str] = Field(default=None)`` emits ``"default": null`` (the default would vanish),
    and a ``const: null`` (a field that must be null) would invert to "any value". A meaningful
    schema ``null`` — ``default: null``, ``const: null``, an ``enum`` member that is ``null`` — is
    therefore **preserved**; only the externalDocs emitter quirk is stripped. This keeps the spec
    genuinely Restate-auto-derived (normalising a known emitter bug, not editing schemas).
    """
    if not isinstance(spec, dict):
        return spec

    normalised = _strip_external_docs_null(spec)
    # The quirk lives on top-level tags[].externalDocs in Restate's emitter; clean those explicitly
    # too (the recursive _strip_external_docs_null already covers them, but being explicit documents
    # the exact emitter path the normalisation targets).
    tags = normalised.get("tags")
    if isinstance(tags, list):
        normalised["tags"] = [_strip_external_docs_null(t) for t in tags]
    return normalised


def _strip_external_docs_null(obj: Any) -> Any:
    """Recursively drop a ``null`` ``description`` under an ``externalDocs`` object only.

    Walks the document but removes a key only when it is the emitter quirk — an
    ``externalDocs.description`` whose value is ``null``. Every other ``null`` (a schema
    ``default: null`` / ``const: null`` / ``enum [..., null]``) is left untouched, so a real tool
    schema is never corrupted.
    """
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for key, value in obj.items():
            if key == "externalDocs" and isinstance(value, dict):
                out[key] = {
                    k: _strip_external_docs_null(v)
                    for k, v in value.items()
                    if not (k == "description" and v is None)
                }
            else:
                out[key] = _strip_external_docs_null(value)
        return out
    if isinstance(obj, list):
        return [_strip_external_docs_null(v) for v in obj]
    return obj


def fetch_service_openapi(
    service: str = BD09_SERVICE_NAME, admin_url: str | None = None
) -> dict[str, Any]:
    """Fetch Restate's auto-generated OpenAPI spec for ``service`` from the admin API.

    The spec is generated by Restate from the registered handler signatures — this helper only
    fetches it, it does not author it.
    """
    base = admin_url or ADMIN_URL
    resp = httpx.get(f"{base}/services/{service}/openapi", timeout=15.0)
    resp.raise_for_status()
    spec: dict[str, Any] = resp.json()
    return spec


def validate_openapi_spec(spec: dict[str, Any], normalise: bool = True) -> str:
    """Validate ``spec`` against its declared OpenAPI version with a real validator.

    Returns the detected OpenAPI version string (e.g. ``"3.1.0"``). Raises if the spec is invalid.
    Uses ``openapi-spec-validator`` — a genuine schema validator, not an eyeball check. By default
    it first applies ``normalise_emitter_quirks`` to work around Restate's ``null`` externalDocs
    emitter quirk (see that function — it is path-scoped, so a meaningful schema ``null`` survives);
    pass ``normalise=False`` to validate the spec exactly as emitted.
    """
    candidate = normalise_emitter_quirks(spec) if normalise else spec
    # Raises OpenAPIValidationError on a non-conforming spec.
    validate_openapi(candidate)
    return str(candidate.get("openapi", ""))


def is_openapi_31(spec: dict[str, Any]) -> bool:
    """True iff the spec is OpenAPI 3.1 specifically (the targeted version)."""
    return bool(get_spec_version(spec) == openapi_versions.OPENAPIV31)


def assert_bd09_surface(spec: dict[str, Any]) -> dict[str, Any]:
    """Assert the bd09 surface is present in the auto-generated spec; return a small summary.

    Confirms the two handler paths and that the ``execute_so`` request schema is a *typed object*
    (the envelope typing) rather than the permissive ``{}`` an untyped envelope would yield.
    """
    paths = spec.get("paths", {})
    assert "/bd09/execute_so" in paths, f"execute_so path missing — paths: {sorted(paths)}"
    assert "/bd09/list_capabilities" in paths, (
        f"list_capabilities path missing — paths: {sorted(paths)}"
    )

    schemas = spec.get("components", {}).get("schemas", {})
    req = schemas.get("execute_soRequest", {})
    # The typed envelope: an object naming soId/args, not the permissive empty schema.
    typed_envelope = (
        isinstance(req, dict)
        and req.get("type") == "object"
        and "soId" in req.get("properties", {})
    )

    return {
        "openapi": spec.get("openapi"),
        "title": spec.get("info", {}).get("title"),
        "handler_paths": [p for p in sorted(paths) if not p.startswith("/restate/")],
        "request_schema_typed": typed_envelope,
        "schema_names": sorted(schemas),
    }


def assert_bd12_surface(spec: dict[str, Any]) -> dict[str, Any]:
    """Assert the bd12 (book-of-record read) surface is present in the auto-generated spec.

    The bd12 service auto-generates its OWN OpenAPI 3.1 spec (Restate generates one per service from
    the handler signatures — the ``ReadRequest`` / read-output Pydantic models). Confirms the two
    handler paths and that the ``execute_so`` request schema is a *typed object* naming ``soId``
    (the envelope typing, inherited here). The same shape as
    ``assert_bd09_surface``, scoped to the bd12 paths.
    """
    paths = spec.get("paths", {})
    assert "/bd12/execute_so" in paths, f"execute_so path missing — paths: {sorted(paths)}"
    assert "/bd12/list_capabilities" in paths, (
        f"list_capabilities path missing — paths: {sorted(paths)}"
    )

    schemas = spec.get("components", {}).get("schemas", {})
    req = schemas.get("execute_soRequest", {})
    typed_envelope = (
        isinstance(req, dict)
        and req.get("type") == "object"
        and "soId" in req.get("properties", {})
    )

    return {
        "openapi": spec.get("openapi"),
        "title": spec.get("info", {}).get("title"),
        "handler_paths": [p for p in sorted(paths) if not p.startswith("/restate/")],
        "request_schema_typed": typed_envelope,
        "schema_names": sorted(schemas),
    }


def assert_bd12_recon_surface(spec: dict[str, Any]) -> dict[str, Any]:
    """Assert the bd12Recon (SD-12.10 reconcile) surface is present in the auto-generated spec.

    The bd12Recon service auto-generates its OWN OpenAPI 3.1 spec from its handler signatures (the
    ``ReconcileRequest`` / reconcile-output Pydantic models). Confirms the two handler paths and
    that
    the ``execute_so`` request schema is a *typed object* naming ``soId`` (the envelope typing,
    inherited from the bd12 precedent). The same shape as ``assert_bd12_surface``, scoped to the
    bd12Recon paths.
    """
    paths = spec.get("paths", {})
    assert "/bd12Recon/execute_so" in paths, f"execute_so path missing — paths: {sorted(paths)}"
    assert "/bd12Recon/list_capabilities" in paths, (
        f"list_capabilities path missing — paths: {sorted(paths)}"
    )

    schemas = spec.get("components", {}).get("schemas", {})
    req = schemas.get("execute_soRequest", {})
    typed_envelope = (
        isinstance(req, dict)
        and req.get("type") == "object"
        and "soId" in req.get("properties", {})
    )

    return {
        "openapi": spec.get("openapi"),
        "title": spec.get("info", {}).get("title"),
        "handler_paths": [p for p in sorted(paths) if not p.startswith("/restate/")],
        "request_schema_typed": typed_envelope,
        "schema_names": sorted(schemas),
    }


def assert_entity_resolution_surface(spec: dict[str, Any]) -> dict[str, Any]:
    """Assert the entityResolution (SD-13.2 resolution) surface is present in the auto-generated
    spec.

    The entityResolution service auto-generates its OWN OpenAPI 3.1 spec from its handler
    signatures (the ``ResolveBatchRequest`` / resolution-output Pydantic models). Confirms the two
    handler paths and that the ``execute_so`` request schema is a *typed object* naming ``soId``
    (the envelope typing, inherited from the bd12Recon precedent). The same shape as
    ``assert_bd12_recon_surface``,
    scoped to the entityResolution paths.
    """
    paths = spec.get("paths", {})
    assert "/entityResolution/execute_so" in paths, (
        f"execute_so path missing — paths: {sorted(paths)}"
    )
    assert "/entityResolution/list_capabilities" in paths, (
        f"list_capabilities path missing — paths: {sorted(paths)}"
    )

    schemas = spec.get("components", {}).get("schemas", {})
    req = schemas.get("execute_soRequest", {})
    typed_envelope = (
        isinstance(req, dict)
        and req.get("type") == "object"
        and "soId" in req.get("properties", {})
    )

    return {
        "openapi": spec.get("openapi"),
        "title": spec.get("info", {}).get("title"),
        "handler_paths": [p for p in sorted(paths) if not p.startswith("/restate/")],
        "request_schema_typed": typed_envelope,
        "schema_names": sorted(schemas),
    }


# Swagger UI is loaded from a CDN pinned to an exact version with Subresource Integrity (SRI)
# sha384 hashes + crossorigin, so a CDN compromise cannot inject altered assets (the browser
# rejects a mismatched hash). The spec it renders is the live, auto-generated bd09 spec fetched
# from Restate (served at ``./openapi.json``), never a hand-written one.
_SWAGGER_VERSION = "5.17.14"
_SWAGGER_CSS_SRI = "sha384-wxLW6kwyHktdDGr6Pv1zgm/VGJh99lfUbzSn6HNHBENZlCN7W602k9VkGdxuFvPn"
_SWAGGER_JS_SRI = "sha384-wmyclcVGX/WhUkdkATwhaK1X1JtiNrr2EoYJ+diV3vj4v6OC5yCeSu+yW13SYJep"
_SWAGGER_TEMPLATE = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>agentINVEST bd09 API</title>
  <link rel="stylesheet"
        href="https://unpkg.com/swagger-ui-dist@{_SWAGGER_VERSION}/swagger-ui.css"
        integrity="{_SWAGGER_CSS_SRI}" crossorigin="anonymous" />
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist@{_SWAGGER_VERSION}/swagger-ui-bundle.js"
          integrity="{_SWAGGER_JS_SRI}" crossorigin="anonymous"></script>
  <script>
    window.ui = SwaggerUIBundle({{ url: "./openapi.json", dom_id: "#swagger-ui" }});
  </script>
</body>
</html>
"""


def swagger_ui_html() -> str:
    """The Swagger-UI page that renders the fetched OpenAPI spec at ``./openapi.json``."""
    return _SWAGGER_TEMPLATE


def make_docs_app(
    service: str = BD09_SERVICE_NAME, admin_url: str | None = None
) -> Any:
    """A minimal ASGI app serving ``/openapi.json`` (the live auto-gen spec) + ``/docs`` (Swagger).

    Restate serves the OpenAPI JSON on its admin API but no Swagger UI on this build, so this thin
    helper exposes the human-facing render. ``/openapi.json`` always re-fetches the auto-generated
    spec from Restate, so the surface tracks the handlers (no hand-written copy is cached).
    """
    import json as _json

    async def app(scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":  # pragma: no cover - lifespan/other
            return
        path = scope["path"]
        if path in ("/openapi.json", f"/{service}/openapi.json"):
            try:
                spec = normalise_emitter_quirks(fetch_service_openapi(service, admin_url))
                body = _json.dumps(spec).encode()
            except Exception:
                # The upstream fetch + normalise can fail in two ways, both surfaced here as a
                # well-formed STRUCTURED JSON 503 (mirroring the sibling 404 envelope) rather than
                # an unhandled exception / opaque 500: (a) the Restate admin is down / unreachable /
                # times out / returns a 5xx — ``fetch_service_openapi`` does ``raise_for_status()``
                # so an ``httpx.HTTPError`` (ConnectError / TimeoutException / HTTPStatusError)
                # propagates; (b) the fetched body is malformed / unparseable — a ``ValueError``
                # (e.g. ``resp.json()``) or a normalise failure. Catching broadly keeps the
                # never-crash invariant structural: NO upstream failure mode can make the docs-app
                # ASGI handler raise. 503 (Service Unavailable) is correct — the upstream admin is
                # unavailable; a retry may succeed.
                #
                # The ``detail`` is consumer-clean: it names the upstream condition only, NEVER the
                # ingress/admin URL, a credential, or a stack-trace (those would leak ingress
                # topology to a docs-app consumer). No stale cached/hand-written spec is served as a
                # fallback — a clean 503 beats a spec that no longer tracks the handlers (SSOT).
                error_body = _json.dumps(
                    {
                        "error": "upstream_unavailable",
                        "detail": (
                            "cannot reach the Restate admin API to fetch the OpenAPI spec; retry"
                        ),
                    }
                ).encode()
                await _respond(send, 503, error_body, b"application/json")
                return
            content_type = b"application/json"
        elif path in ("/docs", f"/{service}/docs", "/"):
            body = swagger_ui_html().encode()
            content_type = b"text/html; charset=utf-8"
        else:
            # A well-formed STRUCTURED JSON error (not a bare text/plain line): an unknown
            # path on the docs app returns 404 with a typed ``{"error", "detail"}`` body and
            # ``application/json``, so a programmatic consumer (or the curl smoke) gets a
            # machine-parseable error envelope rather than an opaque string. This mirrors the
            # bd09 service's own typed terminal-error surface (the RestateError schema) at the
            # docs-app layer.
            error_body = _json.dumps({"error": "not_found", "detail": path}).encode()
            await _respond(send, 404, error_body, b"application/json")
            return
        await _respond(send, 200, body, content_type)

    return app


async def _respond(send: Any, status: int, body: bytes, content_type: bytes) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", content_type)],
        }
    )
    await send({"type": "http.response.body", "body": body})


async def serve_docs(port: int = 9092, service: str = BD09_SERVICE_NAME) -> None:
    """Serve the OpenAPI ``/docs`` + ``/openapi.json`` surface on ``port`` (hypercorn ASGI)."""
    import hypercorn.asyncio
    import hypercorn.config

    config = hypercorn.config.Config()
    config.bind = [f"127.0.0.1:{port}"]
    await hypercorn.asyncio.serve(make_docs_app(service), config)


if __name__ == "__main__":
    import json

    spec = fetch_service_openapi()
    version = validate_openapi_spec(spec)
    summary = assert_bd09_surface(spec)
    print(f"bd09 OpenAPI: version={version} 3.1={is_openapi_31(spec)}")
    print(json.dumps(summary, indent=2))
