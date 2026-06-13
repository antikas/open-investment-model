"""The agentINVEST MCP server — catalogue->descriptors transform + dispatch to ``bd09.execute_so``.

The MCP server is a thin, stateless transform/dispatch layer: it loads the ``bd09`` catalogue over
the ingress and turns each Service Operation into an MCP tool descriptor (name = SO ID, inputSchema
= the tool's Pydantic JSON Schema), and on a call dispatches to ``bd09.execute_so`` over the ingress
(the journaled, terminal-error-classified path — it does NOT re-implement the tool). These tests
drive the *real* server code (``list_tools_from_catalogue`` / ``dispatch_call`` / ``build_server``)
against a mock ingress (``httpx.MockTransport``) so they are deterministic and CI-safe — they prove
the transform and the dispatch wiring without a live Restate. The end-to-end round-trip through the
real Restate server is proven separately.

Load-bearing properties asserted:

- **auto-generation from the catalogue** — the descriptors are built from what ``list_capabilities``
  returns (the real per-tool Pydantic schemas), never hand-written here; all five SOs appear with
  the SO ID as the tool name and the catalogue's inputSchema;
- **dispatch, not re-implementation** — a tool call POSTs the ``{soId, args}`` envelope to
  ``execute_so`` and returns its result; the MCP server holds no compute;
- **terminal error surfaces** — a deterministic failure (the service returns HTTP 4xx) is raised, so
  the MCP client sees an error result, never a fabricated success.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import anyio
import httpx
import pytest

from agentinvest_tools.bd09_service import _REGISTRY
from agentinvest_tools.bd12_recon_service import _REGISTRY as _BD12_RECON_REGISTRY
from agentinvest_tools.bd12_service import _REGISTRY as _BD12_REGISTRY
from agentinvest_tools.entity_resolution_service import _REGISTRY as _ER_REGISTRY
from agentinvest_tools.mcp_server import (
    McpServiceUnavailableError,
    McpToolError,
    build_server,
    dispatch_call,
    list_tools_from_catalogue,
)

# A catalogue payload shaped exactly like the real bd09 ``list_capabilities`` response — built from
# the live registry so the test stays in lock-step with the real tools (not a hand-written stub).
_CATALOGUE = {
    "service": "bd09",
    "capabilities": [
        {
            "soId": spec.so_id,
            "name": spec.name,
            "summary": spec.summary,
            "inputSchema": spec.input_model.model_json_schema(),
            "outputSchema": spec.output_model.model_json_schema(),
        }
        for spec in _REGISTRY.values()
    ],
}

# The bd12 (book-of-record read) catalogue the MCP face aggregates alongside bd09.
# Built from the live bd12 registry so the mock stays in lock-step with the real read tools.
_BD12_CATALOGUE = {
    "service": "bd12",
    "capabilities": [
        {
            "soId": spec.so_id,
            "name": spec.name,
            "summary": spec.summary,
            "books": list(spec.books),
            "inputSchema": spec.input_model.model_json_schema(),
            "outputSchema": spec.output_model.model_json_schema(),
        }
        for spec in _BD12_REGISTRY.values()
    ],
}

# The bd12Recon (SD-12.10 reconcile) catalogue the MCP face also aggregates. Built
# from the live bd12Recon registry so the mock stays in lock-step with the real reconcile tools.
_BD12_RECON_CATALOGUE = {
    "service": "bd12Recon",
    "capabilities": [
        {
            "soId": spec.so_id,
            "name": spec.name,
            "summary": spec.summary,
            "inputSchema": spec.input_model.model_json_schema(),
            "outputSchema": spec.output_model.model_json_schema(),
        }
        for spec in _BD12_RECON_REGISTRY.values()
    ],
}

# The entityResolution (SD-13.2 resolution) catalogue the MCP face also aggregates. Built
# from the live entityResolution registry so the mock stays in lock-step with the real tools.
_ENTITY_RESOLUTION_CATALOGUE = {
    "service": "entityResolution",
    "capabilities": [
        {
            "soId": spec.so_id,
            "name": spec.name,
            "summary": spec.summary,
            "inputSchema": spec.input_model.model_json_schema(),
            "outputSchema": spec.output_model.model_json_schema(),
        }
        for spec in _ER_REGISTRY.values()
    ],
}


def _mock_ingress(
    execute_response: tuple[int, dict[str, Any]] | None = None,
) -> httpx.MockTransport:
    """A mock Restate ingress: serves each per-BD catalogue + a canned execute_so for both services.

    Serves both ``bd09`` and ``bd12`` ``list_capabilities`` (the MCP face aggregates across
    both); ``execute_so`` is canned for whichever service path the test dispatches to (the SO
    namespaces are disjoint, so the response is the configured one regardless of service).
    """

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/bd09/list_capabilities":
            return httpx.Response(200, json=_CATALOGUE)
        if request.url.path == "/bd12/list_capabilities":
            return httpx.Response(200, json=_BD12_CATALOGUE)
        if request.url.path == "/bd12Recon/list_capabilities":
            return httpx.Response(200, json=_BD12_RECON_CATALOGUE)
        if request.url.path == "/entityResolution/list_capabilities":
            return httpx.Response(200, json=_ENTITY_RESOLUTION_CATALOGUE)
        if request.url.path in (
            "/bd09/execute_so",
            "/bd12/execute_so",
            "/bd12Recon/execute_so",
            "/entityResolution/execute_so",
        ):
            assert execute_response is not None, "no execute_so response configured"
            status, body = execute_response
            return httpx.Response(status, json=body)
        return httpx.Response(404, text=f"unexpected path {request.url.path}")

    return httpx.MockTransport(handler)


def _client(transport: httpx.MockTransport) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=transport, base_url="http://localhost:8080")


# --- the catalogue -> MCP descriptors transform (auto-generated) ------------------------------


@pytest.mark.anyio
async def test_list_tools_generates_descriptors_from_the_aggregated_catalogue() -> None:
    async with _client(_mock_ingress()) as client:
        tools = await list_tools_from_catalogue(client)

    names = [t.name for t in tools]
    # The bd09 five come FIRST, byte-for-byte (the NAV-path tools unperturbed)...
    assert names[:5] == ["SO-09-01", "SO-09-02", "SO-09-03", "SO-09-04", "SO-09-05"]
    # ...then the bd12 read tools, the bd12Recon reconcile tools and the entityResolution tools
    # are APPENDED, additive — the 9 IBOR + ABOR reads, the 4 SD-12.10 reconciles, and the 3
    # SD-13.2 resolution tools.
    assert set(names[5:]) == {
        "SO-12.1-01",
        "SO-12.1-02",
        "SO-12.1-03",
        "SO-12.1-04",
        "SO-12.1-05",
        "SO-12.2-01",
        "SO-12.2-02",
        "SO-12.2-03",
        "SO-12.2-04",
        "SO-12.10-01",
        "SO-12.10-02",
        "SO-12.10-03",
        "SO-12.10-04",
        "SO-13.2-01",
        "SO-13.2-02",
        "SO-13.2-03",
    }
    for tool in tools:
        # The inputSchema is the tool's real Pydantic JSON Schema (auto-generated, not a stub):
        # an object with named properties matching the tool model.
        assert tool.inputSchema["type"] == "object"
        assert tool.inputSchema["properties"], f"{tool.name} descriptor has no input properties"
        assert tool.description, f"{tool.name} descriptor has no description"

    # Spot-check: the SO-09-01 descriptor carries the real tool field (proving it is catalogue-led).
    total_return = next(t for t in tools if t.name == "SO-09-01")
    assert "beginning_value" in total_return.inputSchema["properties"]


@pytest.mark.anyio
async def test_descriptor_schema_matches_the_registry_not_a_handwritten_copy() -> None:
    """The descriptor inputSchema is byte-identical to the live tool model schema (no hand-copy)."""
    async with _client(_mock_ingress()) as client:
        tools = await list_tools_from_catalogue(client)
    by_id = {t.name: t for t in tools}
    for spec in _REGISTRY.values():
        assert by_id[spec.so_id].inputSchema == spec.input_model.model_json_schema()


# --- dispatch to bd09.execute_so (journaled, not re-implemented) ------------------------------


@pytest.mark.anyio
async def test_call_tool_round_trips_through_execute_so() -> None:
    """A tool call POSTs {soId, args} to execute_so and returns its result — no local re-compute."""
    result_envelope = {
        "result": {"active_return": "0.02", "methodology": "arithmetic-excess"},
        "provenance": {
            "soId": "SO-09-04",
            "tool": "compute_benchmark_relative_return",
            "methodology": "arithmetic-excess",
        },
        "computedBy": "python:bd09",
    }
    captured: dict[str, Any] = {}

    def record(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/bd09/execute_so":
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json=result_envelope)
        return httpx.Response(200, json=_CATALOGUE)

    async with _client(httpx.MockTransport(record)) as client:
        content = await dispatch_call(
            client,
            "SO-09-04",
            {"portfolio_return": "0.12", "benchmark_return": "0.10"},
        )

    # The dispatch built the execute_so envelope (soId + args) — the journaled service path.
    assert captured["body"] == {
        "soId": "SO-09-04",
        "args": {"portfolio_return": "0.12", "benchmark_return": "0.10"},
    }
    # The MCP result is the service's result, rendered as text (not re-computed locally).
    assert len(content) == 1
    payload = json.loads(content[0].text)
    assert payload["result"]["active_return"] == "0.02"
    assert payload["computedBy"] == "python:bd09"


@pytest.mark.anyio
async def test_call_tool_surfaces_a_terminal_error_not_a_silent_success() -> None:
    """A deterministic failure (the service returns HTTP 4xx) is raised, not a fabricated result.

    A 4xx surfaces as an error, not a success — as the typed :class:`McpToolError` (terminal),
    which the MCP SDK marks ``isError`` (see ``test_real_mcp_client_*`` for the SDK-level proof).
    """
    transport = _mock_ingress(execute_response=(400, {"message": "invalid arguments"}))
    async with _client(transport) as client:
        with pytest.raises(McpToolError, match="returned 400"):
            await dispatch_call(client, "SO-09-01", {"bogus": 1})


@pytest.mark.anyio
async def test_build_server_registers_the_mcp_handlers() -> None:
    """The MCP server wires the catalogue/dispatch handlers (the stdio sidecar's handlers)."""
    import mcp.types as mcp_types

    async with _client(_mock_ingress()) as client:
        server = build_server(client)
    assert mcp_types.ListToolsRequest in server.request_handlers
    assert mcp_types.CallToolRequest in server.request_handlers


# --- fault classification: terminal (4xx) vs transient (transport / 5xx / catalogue-load) --------


@pytest.mark.anyio
async def test_call_tool_5xx_is_transient_not_terminal() -> None:
    """A 5xx from the ingress on a call → a DISTINCT transient unavailable error, not a tool err."""
    transport = _mock_ingress(execute_response=(503, {"message": "upstream down"}))
    async with _client(transport) as client:
        with pytest.raises(McpServiceUnavailableError, match="service unavailable"):
            await dispatch_call(client, "SO-09-01", {"x": 1})
    # And it is NOT classified terminal (the two classes are genuinely distinct exception types).
    transport2 = _mock_ingress(execute_response=(503, {"message": "upstream down"}))
    async with _client(transport2) as client:
        with pytest.raises(McpServiceUnavailableError):
            await dispatch_call(client, "SO-09-01", {"x": 1})


@pytest.mark.anyio
async def test_call_tool_connect_error_is_transient() -> None:
    """A transport error (connection refused / timeout) on a call → a transient unavailable err."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/bd09/list_capabilities":
            return httpx.Response(200, json=_CATALOGUE)
        raise httpx.ConnectError("connection refused", request=request)

    async with _client(httpx.MockTransport(handler)) as client:
        with pytest.raises(McpServiceUnavailableError, match="retry"):
            await dispatch_call(client, "SO-09-01", {"x": 1})


@pytest.mark.anyio
async def test_call_tool_timeout_is_transient() -> None:
    """An httpx timeout on a call → a transient unavailable error (not a crash, not terminal)."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/bd09/list_capabilities":
            return httpx.Response(200, json=_CATALOGUE)
        raise httpx.ReadTimeout("timed out", request=request)

    async with _client(httpx.MockTransport(handler)) as client:
        with pytest.raises(McpServiceUnavailableError):
            await dispatch_call(client, "SO-09-01", {"x": 1})


@pytest.mark.anyio
async def test_list_tools_transient_when_catalogue_load_fails() -> None:
    """The SAME transient class on catalogue-load: list_tools when the ingress is down → unavail.

    Proves part-1's "on BOTH paths": a transport error OR a non-2xx on ``list_capabilities``
    surfaces a clean :class:`McpServiceUnavailableError`, never a crash / a half-built descriptors.
    """

    def connect_refused(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    async with _client(httpx.MockTransport(connect_refused)) as client:
        with pytest.raises(McpServiceUnavailableError, match="catalogue"):
            await list_tools_from_catalogue(client)

    def ingress_5xx(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, text="bad gateway")

    async with _client(httpx.MockTransport(ingress_5xx)) as client:
        with pytest.raises(McpServiceUnavailableError, match="catalogue"):
            await list_tools_from_catalogue(client)


# --- body-parse fault: a malformed/empty/partial 2xx body is the SAME transient class -------------
# A 2xx whose body is unparseable (non-JSON / empty) or partial (missing capabilities / a per-entry
# missing key) is an infrastructure anomaly — the service answered OK but sent something the sidecar
# can't use — NOT a caller-argument fault. It must surface as a clean transient/unavailable error,
# never the raw parse string, and on the catalogue path NEVER a session crash. These tests are
# revert-sensitive: remove either body-parse guard and they go RED (raw JSONDecodeError / KeyError /
# session crash). They use the MockTransport + real-mcp-client SDK patterns.


def _catalogue_then(
    execute_handler: Callable[[httpx.Request], httpx.Response],
) -> httpx.MockTransport:
    """A mock ingress: both healthy catalogues + a caller-supplied bd09 execute_so handler.

    Serves both ``bd09`` + ``bd12`` ``list_capabilities`` (the aggregated MCP face the real client
    lists over), so a real-client ``call_tool`` whose internal ``list_tools`` aggregates both
    catalogues succeeds, and the dispatch reaches the caller-supplied ``bd09/execute_so``.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/bd09/list_capabilities":
            return httpx.Response(200, json=_CATALOGUE)
        if request.url.path == "/bd12/list_capabilities":
            return httpx.Response(200, json=_BD12_CATALOGUE)
        if request.url.path == "/bd12Recon/list_capabilities":
            return httpx.Response(200, json=_BD12_RECON_CATALOGUE)
        if request.url.path == "/entityResolution/list_capabilities":
            return httpx.Response(200, json=_ENTITY_RESOLUTION_CATALOGUE)
        if request.url.path == "/bd09/execute_so":
            return execute_handler(request)
        return httpx.Response(404, text=f"unexpected path {request.url.path}")

    return httpx.MockTransport(handler)


@pytest.mark.anyio
async def test_call_tool_non_json_200_body_is_clean_transient_not_raw_parse() -> None:
    """A 200 execute_so with a non-JSON body → a clean transient unavailable, NOT a raw parse."""
    transport = _catalogue_then(lambda req: httpx.Response(200, content=b"<<<notjson>>>"))
    async with _client(transport) as client:
        with pytest.raises(McpServiceUnavailableError, match="unreadable response") as exc_info:
            await dispatch_call(client, "SO-09-01", {"x": 1})
    message = str(exc_info.value)
    # The clean classified message — NOT the raw "Expecting value: line 1 column 1" parse artefact.
    assert "Expecting value" not in message
    assert "JSONDecodeError" not in message
    assert "retry" in message


@pytest.mark.anyio
async def test_call_tool_empty_200_body_is_clean_transient() -> None:
    """A 200 execute_so with an EMPTY body → the same clean transient unavailable (no raw parse)."""
    transport = _catalogue_then(lambda req: httpx.Response(200, content=b""))
    async with _client(transport) as client:
        with pytest.raises(McpServiceUnavailableError, match="unreadable response") as exc_info:
            await dispatch_call(client, "SO-09-01", {"x": 1})
    assert "Expecting value" not in str(exc_info.value)


@pytest.mark.anyio
async def test_call_tool_non_json_body_is_revert_sensitive() -> None:
    """Revert-sensitivity: the non-JSON 200 body is classified transient, never McpToolError/raw.

    Without the dispatch_call body-parse guard this raises a bare json.JSONDecodeError (neither
    typed class) — so asserting McpServiceUnavailableError genuinely exercises the classification.
    """
    transport = _catalogue_then(lambda req: httpx.Response(200, content=b"not json at all"))
    async with _client(transport) as client:
        with pytest.raises(McpServiceUnavailableError):
            await dispatch_call(client, "SO-09-01", {"x": 1})
        # And it is NOT mislabelled a terminal tool error.
        with pytest.raises(McpServiceUnavailableError):
            await dispatch_call(client, "SO-09-01", {"x": 1})


def _catalogue_body(
    catalogue_handler: Callable[[httpx.Request], httpx.Response],
) -> httpx.MockTransport:
    """A mock ingress whose list_capabilities body is caller-supplied (malformed catalogues)."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/bd09/list_capabilities":
            return catalogue_handler(request)
        return httpx.Response(404, text=f"unexpected path {request.url.path}")

    return httpx.MockTransport(handler)


@pytest.mark.anyio
async def test_list_tools_non_json_catalogue_is_clean_unavailable() -> None:
    """A 200 list_capabilities with a non-JSON body → a clean unavailable (no raw parse string)."""
    transport = _catalogue_body(lambda req: httpx.Response(200, content=b"garbage"))
    async with _client(transport) as client:
        with pytest.raises(McpServiceUnavailableError, match="catalogue is unreadable") as exc_info:
            await list_tools_from_catalogue(client)
    assert "Expecting value" not in str(exc_info.value)


@pytest.mark.anyio
async def test_list_tools_partial_catalogue_missing_capabilities_is_clean_unavailable() -> None:
    """A 200 catalogue that parses but lacks ``capabilities`` → clean unavailable, not KeyError."""
    transport = _catalogue_body(lambda req: httpx.Response(200, json={"service": "bd09"}))
    async with _client(transport) as client:
        with pytest.raises(McpServiceUnavailableError, match="catalogue is unreadable") as exc_info:
            await list_tools_from_catalogue(client)
    # NOT the raw "'capabilities'" KeyError string.
    assert "'capabilities'" not in str(exc_info.value)


@pytest.mark.anyio
async def test_list_tools_non_dict_catalogue_body_is_clean_unavailable() -> None:
    """A 200 catalogue body that is a JSON array (not a dict) → clean unavailable, no TypeError."""
    transport = _catalogue_body(lambda req: httpx.Response(200, json=[1, 2, 3]))
    async with _client(transport) as client:
        with pytest.raises(McpServiceUnavailableError, match="catalogue is unreadable"):
            await list_tools_from_catalogue(client)


@pytest.mark.anyio
async def test_list_tools_partial_entry_missing_so_id_is_clean_unavailable() -> None:
    """A catalogue parsing OK but whose entry lacks ``soId`` → clean unavailable, no crash."""
    partial = {"service": "bd09", "capabilities": [{"summary": "s", "inputSchema": {}}]}
    transport = _catalogue_body(lambda req: httpx.Response(200, json=partial))
    async with _client(transport) as client:
        with pytest.raises(McpServiceUnavailableError, match="catalogue is unreadable"):
            await list_tools_from_catalogue(client)


@pytest.mark.anyio
async def test_real_mcp_client_malformed_catalogue_does_not_crash_session() -> None:
    """A non-JSON catalogue → a clean MCP error AND the session SURVIVES (no crash).

    Drives the REAL ``mcp`` client SDK. The first ``list_tools()`` (malformed catalogue) returns a
    clean error — NOT a raw parse string, NOT an ``ExceptionGroup`` session crash. The catalogue
    recovers and a second ``list_tools()`` succeeds on the SAME session, proving the session stayed
    usable (no ``unhandled errors in a TaskGroup`` teardown).
    """
    from mcp.shared.exceptions import McpError
    from mcp.shared.memory import create_connected_server_and_client_session

    state = {"calls": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/bd09/list_capabilities":
            state["calls"] += 1
            if state["calls"] == 1:
                return httpx.Response(200, content=b"<<<garbage catalogue>>>")
            return httpx.Response(200, json=_CATALOGUE)  # recovered
        if request.url.path == "/bd12/list_capabilities":
            return httpx.Response(200, json=_BD12_CATALOGUE)
        if request.url.path == "/bd12Recon/list_capabilities":
            return httpx.Response(200, json=_BD12_RECON_CATALOGUE)
        if request.url.path == "/entityResolution/list_capabilities":
            return httpx.Response(200, json=_ENTITY_RESOLUTION_CATALOGUE)
        return httpx.Response(404, text="unexpected")

    async with _client(httpx.MockTransport(handler)) as client:
        server = build_server(client)
        async with create_connected_server_and_client_session(server) as session:
            # First list: malformed catalogue → a clean MCP error (no raw parse string, no crash).
            with pytest.raises(McpError) as exc_info:
                await session.list_tools()
            assert "unreadable" in exc_info.value.error.message
            assert "Expecting value" not in exc_info.value.error.message
            # The session SURVIVES — a second list (catalogue recovered) round-trips cleanly. The
            # bd09 five first, then bd12 nine + bd12Recon four + entityResolution three appended.
            recovered = await session.list_tools()
            names = [t.name for t in recovered.tools]
            assert names[:5] == ["SO-09-01", "SO-09-02", "SO-09-03", "SO-09-04", "SO-09-05"]
            assert len(names) == 21


@pytest.mark.anyio
async def test_real_mcp_client_partial_catalogue_does_not_crash_session() -> None:
    """A partial catalogue (missing ``capabilities``) → a clean MCP error, the session survives."""
    from mcp.shared.exceptions import McpError
    from mcp.shared.memory import create_connected_server_and_client_session

    state = {"calls": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/bd09/list_capabilities":
            state["calls"] += 1
            if state["calls"] == 1:
                return httpx.Response(200, json={"service": "bd09"})  # partial: no capabilities
            return httpx.Response(200, json=_CATALOGUE)
        if request.url.path == "/bd12/list_capabilities":
            return httpx.Response(200, json=_BD12_CATALOGUE)
        if request.url.path == "/bd12Recon/list_capabilities":
            return httpx.Response(200, json=_BD12_RECON_CATALOGUE)
        if request.url.path == "/entityResolution/list_capabilities":
            return httpx.Response(200, json=_ENTITY_RESOLUTION_CATALOGUE)
        return httpx.Response(404, text="unexpected")

    async with _client(httpx.MockTransport(handler)) as client:
        server = build_server(client)
        async with create_connected_server_and_client_session(server) as session:
            with pytest.raises(McpError) as exc_info:
                await session.list_tools()
            assert "unreadable" in exc_info.value.error.message
            assert "'capabilities'" not in exc_info.value.error.message
            recovered = await session.list_tools()
            # The aggregated face: bd09 five + bd12 nine + bd12Recon four + entityResolution three
            # = 21 read/compute tools.
            assert len(recovered.tools) == 21


@pytest.mark.anyio
async def test_real_mcp_client_non_json_execute_body_is_clean_iserror() -> None:
    """A 200 execute_so with a non-JSON body → a clean transient ``isError`` (no raw parse)."""
    from mcp.shared.memory import create_connected_server_and_client_session

    transport = _catalogue_then(lambda req: httpx.Response(200, content=b"<<<not json>>>"))
    async with _client(transport) as client:
        server = build_server(client)
        async with create_connected_server_and_client_session(server) as session:
            call = await session.call_tool(
                "SO-09-04", {"portfolio_return": "0.12", "benchmark_return": "0.10"}
            )
    assert call.isError is True
    text = _text_of(call)
    assert "service unavailable" in text
    assert "unreadable response" in text
    # NOT the raw parse artefact a leaky sidecar would surface.
    assert "Expecting value" not in text
    assert "JSONDecodeError" not in text


@pytest.mark.anyio
async def test_valid_200_body_still_parses_and_returns_normally() -> None:
    """The guard does NOT swallow a genuine result: a valid 200 envelope parses + returns OK."""
    envelope = {"result": {"active_return": "0.02"}, "computedBy": "python:bd09"}
    transport = _catalogue_then(lambda req: httpx.Response(200, json=envelope))
    async with _client(transport) as client:
        content = await dispatch_call(client, "SO-09-01", {"x": 1})
    assert len(content) == 1
    payload = json.loads(content[0].text)
    assert payload["result"]["active_return"] == "0.02"
    assert payload["computedBy"] == "python:bd09"


@pytest.mark.anyio
async def test_faults_never_leak_the_ingress_url_or_a_stack_trace() -> None:
    """The client-facing message is clean — no ingress URL/credentials, no stack-trace artefact."""
    transport = _mock_ingress(execute_response=(503, {"message": "x"}))
    async with _client(transport) as client:
        try:
            await dispatch_call(client, "SO-09-01", {"x": 1})
        except McpServiceUnavailableError as exc:
            message = str(exc)
    assert "localhost:8080" not in message
    assert "http://" not in message
    assert "Traceback" not in message


# --- boundary validation: unknown tool name (no POST) + non-dict args ----------------------------


@pytest.mark.anyio
async def test_unknown_tool_name_rejected_before_any_post() -> None:
    """An unknown tool name → a clean McpToolError BEFORE any execute_so POST (assert none made)."""
    execute_posts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/bd09/list_capabilities":
            return httpx.Response(200, json=_CATALOGUE)
        if request.url.path == "/bd09/execute_so":
            execute_posts.append("posted")
            return httpx.Response(200, json={})
        return httpx.Response(404, text="unexpected")

    async with _client(httpx.MockTransport(handler)) as client:
        with pytest.raises(McpToolError, match="unknown tool 'SO-99-99'"):
            await dispatch_call(client, "SO-99-99", {"x": 1})

    assert execute_posts == [], "an unknown tool must NOT be POSTed to execute_so"


@pytest.mark.anyio
async def test_non_dict_arguments_rejected_cleanly() -> None:
    """Non-dict arguments → a clean McpToolError before any dispatch (the boundary shape check)."""
    execute_posts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/bd09/list_capabilities":
            return httpx.Response(200, json=_CATALOGUE)
        if request.url.path == "/bd09/execute_so":
            execute_posts.append("posted")
            return httpx.Response(200, json={})
        return httpx.Response(404, text="unexpected")

    async with _client(httpx.MockTransport(handler)) as client:
        with pytest.raises(McpToolError, match="invalid arguments"):
            await dispatch_call(client, "SO-09-01", ["not", "a", "dict"])  # type: ignore[arg-type]

    assert execute_posts == [], "a malformed-shape call must NOT be POSTed to execute_so"


# --- structured logging: one stderr line, right outcome, no arg values, no secret, stdout pure ---


@pytest.mark.anyio
async def test_call_emits_one_structured_stderr_line_no_arg_values(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A call emits one JSON stderr line with the right fields; no arg value, stdout stays pure."""
    result_envelope = {"result": {"active_return": "0.02"}, "computedBy": "python:bd09"}
    secret_like_arg_value = "SECRET-9f3a-token"
    transport = _mock_ingress(execute_response=(200, result_envelope))
    async with _client(transport) as client:
        await dispatch_call(client, "SO-09-04", {"portfolio_return": secret_like_arg_value})

    captured = capsys.readouterr()
    # stdout MUST stay pure (it is the stdio MCP transport) — the logger writes to stderr only.
    assert captured.out == "", f"the logger polluted stdout: {captured.out!r}"
    stderr_lines = [ln for ln in captured.err.splitlines() if ln.strip()]
    assert len(stderr_lines) == 1, f"expected one structured line, got {stderr_lines!r}"
    record = json.loads(stderr_lines[0])
    assert record["event"] == "call_tool"
    assert record["soId"] == "SO-09-04"
    assert record["outcome"] == "ok"
    assert record["status_code"] == 200
    assert isinstance(record["duration_ms"], int)
    # NEVER an arg value and NEVER a secret in the log line.
    assert secret_like_arg_value not in stderr_lines[0]
    assert "portfolio_return" not in stderr_lines[0]


@pytest.mark.anyio
async def test_terminal_and_transient_outcomes_are_logged(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A terminal call logs outcome=terminal; a transient call logs outcome=transient."""
    async with _client(_mock_ingress(execute_response=(400, {"m": "bad"}))) as client:
        with pytest.raises(McpToolError):
            await dispatch_call(client, "SO-09-01", {"x": 1})
    terminal = json.loads(capsys.readouterr().err.splitlines()[-1])
    assert terminal["outcome"] == "terminal"
    assert terminal["status_code"] == 400

    async with _client(_mock_ingress(execute_response=(503, {"m": "down"}))) as client:
        with pytest.raises(McpServiceUnavailableError):
            await dispatch_call(client, "SO-09-01", {"x": 1})
    transient = json.loads(capsys.readouterr().err.splitlines()[-1])
    assert transient["outcome"] == "transient"


@pytest.mark.anyio
async def test_rejected_call_is_logged_rejected(capsys: pytest.CaptureFixture[str]) -> None:
    """A rejected call (unknown tool) logs outcome=rejected and writes nothing to stdout."""
    async with _client(_mock_ingress()) as client:
        with pytest.raises(McpToolError):
            await dispatch_call(client, "SO-99-99", {"x": 1})
    captured = capsys.readouterr()
    assert captured.out == ""
    record = json.loads(captured.err.splitlines()[-1])
    assert record["outcome"] == "rejected"
    assert record["soId"] == "SO-99-99"


# --- concurrency guard: clean busy past the bound; a normal call is never throttled ---------------


@pytest.mark.anyio
async def test_concurrency_guard_busy_past_the_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """> bound concurrent in-flight calls → the excess gets a clean busy error; the rest succeed.

    The bound is set to 1; two calls are held in-flight against a blocking mock ingress, so the
    second call hits the saturated semaphore and returns the clean busy McpServiceUnavailableError
    while the first proceeds. Proves the guard bites at the *server boundary* (build_server's
    call_tool), not just in isolation.

    The calls are driven through the SDK's registered ``CallToolRequest`` handler with
    **schema-valid** arguments, so the SDK's inputSchema validation passes and the call reaches the
    semaphore-wrapped ``func`` (bogus args would be rejected by the SDK *before* the guard, never
    exercising it). The handler turns the raised :class:`McpServiceUnavailableError` into an
    ``isError`` result, so the busy rejection is a clean result — not an exception that could leave
    the first call's slot held forever.
    """
    monkeypatch.setenv("AGENTINVEST_MCP_MAX_CONCURRENT", "1")

    # Schema-valid args (so the SDK validation passes and the call reaches the guard-wrapped func).
    first_args = {"beginning_value": "100", "ending_value": "110", "period_days": 365}
    second_args = {"sub_periods": [{"sub_period_return": "0.01"}, {"sub_period_return": "0.02"}]}

    release = anyio.Event()
    in_flight = anyio.Event()

    async def blocking_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/bd09/list_capabilities":
            return httpx.Response(200, json=_CATALOGUE)
        if request.url.path == "/bd12/list_capabilities":
            return httpx.Response(200, json=_BD12_CATALOGUE)
        if request.url.path == "/bd12Recon/list_capabilities":
            return httpx.Response(200, json=_BD12_RECON_CATALOGUE)
        if request.url.path == "/entityResolution/list_capabilities":
            return httpx.Response(200, json=_ENTITY_RESOLUTION_CATALOGUE)
        # execute_so: signal we are in-flight, then block until released.
        in_flight.set()
        await release.wait()
        return httpx.Response(200, json={"result": {}, "computedBy": "python:bd09"})

    transport = httpx.MockTransport(blocking_handler)  # async handler is supported by httpx
    async with _client(transport) as client:
        server = build_server(client)
        handler = server.request_handlers  # the dispatch happens via call_tool closure
        # Call the registered call_tool handler through the same path the SDK uses.
        from mcp.types import CallToolRequest, CallToolRequestParams

        async def invoke(name: str, args: dict[str, Any]) -> Any:
            req = CallToolRequest(
                method="tools/call",
                params=CallToolRequestParams(name=name, arguments=args),
            )
            return await handler[CallToolRequest](req)

        results: dict[str, Any] = {}

        async def first() -> None:
            try:
                results["first"] = await invoke("SO-09-01", first_args)
            finally:
                release.set()  # belt-and-braces: never leave the second task wedged

        async def second() -> None:
            try:
                await in_flight.wait()  # ensure the first call holds the only slot
                results["second"] = await invoke("SO-09-02", second_args)
            finally:
                release.set()  # let the first finish (also unblocks if the first never started)

        async with anyio.create_task_group() as tg:
            tg.start_soon(first)
            tg.start_soon(second)

    # The second call was rejected busy — the SDK turned the raised McpServiceUnavailableError into
    # an isError result whose text carries the busy message.
    second_result = results["second"]
    assert second_result.root.isError is True
    assert "busy" in second_result.root.content[0].text
    # The first call (holding the slot) completed successfully.
    assert results["first"].root.isError is False


@pytest.mark.anyio
async def test_normal_single_call_is_never_throttled_at_default() -> None:
    """At the generous default bound a normal single call dispatches cleanly (no busy error)."""
    transport = _mock_ingress(execute_response=(200, {"result": {}, "computedBy": "python:bd09"}))
    async with _client(transport) as client:
        content = await dispatch_call(client, "SO-09-01", {"x": 1})
    assert len(content) == 1  # a clean dispatch, never throttled


# --- the real mcp client SDK round-trip (the autonomous "production MCP client" proof) ------------


def _text_of(call: Any) -> str:
    """Return the first content block's text, narrowing the SDK's content union to ``TextContent``.

    ``call_tool`` returns content typed as a union (text / image / audio / resource); the MCP server
    only ever returns ``TextContent``, so the first block must be text — this asserts that narrowing
    so the ``.text`` access is type-safe (and would fail loudly if the SDK returned another block).
    """
    from mcp.types import TextContent

    block = call.content[0]
    assert isinstance(block, TextContent), f"expected TextContent, got {type(block).__name__}"
    return block.text


@pytest.mark.anyio
async def test_real_mcp_client_round_trips_list_and_call() -> None:
    """Drive the server through the REAL ``mcp`` client SDK (in-memory) — list + call round-trip.

    Uses ``create_connected_server_and_client_session`` to connect a real ``ClientSession`` to
    ``build_server(...)`` over an in-memory stream pair — a genuine MCP client (the SDK's
    JSON-RPC initialize / tools/list / tools/call), not the internal functions. This is the
    load-bearing "a production MCP client round-trips" proof.
    """
    from mcp.shared.memory import create_connected_server_and_client_session

    result_envelope = {
        "result": {"active_return": "0.02", "methodology": "arithmetic-excess"},
        "computedBy": "python:bd09",
    }
    transport = _mock_ingress(execute_response=(200, result_envelope))
    async with _client(transport) as client:
        server = build_server(client)
        async with create_connected_server_and_client_session(server) as session:
            listed = await session.list_tools()
            names = [t.name for t in listed.tools]
            # The aggregated face: bd09 five first (unperturbed), then the bd12 nine, the
            # bd12Recon four and the entityResolution three.
            assert names[:5] == ["SO-09-01", "SO-09-02", "SO-09-03", "SO-09-04", "SO-09-05"]
            assert len(names) == 21
            call = await session.call_tool(
                "SO-09-04", {"portfolio_return": "0.12", "benchmark_return": "0.10"}
            )
            assert call.isError is False
            payload = json.loads(_text_of(call))
            assert payload["result"]["active_return"] == "0.02"


@pytest.mark.anyio
async def test_real_mcp_client_terminal_error_is_iserror() -> None:
    """A 4xx from the (mock) ingress surfaces to the real client as an ``isError`` result+detail."""
    from mcp.shared.memory import create_connected_server_and_client_session

    # Schema-valid args (so the SDK's inputSchema check passes and the call reaches the dispatch),
    # but the service classifies it terminal 4xx (e.g. a non-conventional series) — the case the
    # fault classifier must surface as a clean terminal isError with the status + detail.
    transport = _mock_ingress(execute_response=(400, {"message": "invalid arguments"}))
    async with _client(transport) as client:
        server = build_server(client)
        async with create_connected_server_and_client_session(server) as session:
            call = await session.call_tool(
                "SO-09-04", {"portfolio_return": "0.12", "benchmark_return": "0.10"}
            )
    assert call.isError is True
    assert "returned 400" in _text_of(call)


@pytest.mark.anyio
async def test_real_mcp_client_transient_error_is_distinct_iserror() -> None:
    """A 5xx surfaces to the real client as an ``isError`` result carrying the distinct unavailable.

    The "real client sees the transient class as a clean retryable error, not a silent success and
    not a mislabelled terminal" proof at the SDK boundary.
    """
    from mcp.shared.memory import create_connected_server_and_client_session

    transport = _mock_ingress(execute_response=(503, {"message": "upstream down"}))
    async with _client(transport) as client:
        server = build_server(client)
        async with create_connected_server_and_client_session(server) as session:
            call = await session.call_tool(
                "SO-09-04", {"portfolio_return": "0.12", "benchmark_return": "0.10"}
            )
    assert call.isError is True
    assert "service unavailable" in _text_of(call)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
