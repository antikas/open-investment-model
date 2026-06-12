"""The agentINVEST MCP server — the agent-to-agent face of the per-BD tool catalogues.

A thin MCP wrapper that exposes the per-BD Service-Operation tool catalogues (``bd09`` performance +
``bd12`` book-of-record read, OIM-161) to an *external* MCP client (another agent, the MCP
inspector, a programmatic client) over the MCP ``stdio`` transport. It holds **no tool logic**: it
loads each service's catalogue and dispatches each tool call to the SO's OWNING Restate service over
the ingress — the journaled, terminal-error-classified path — so a tool call inherits the durable
substrate's journal/replay and its deterministic-error-is-terminal classification. Adding ``bd12``
is additive: the ``bd09`` listing + dispatch is byte-identical; the ``bd12`` read tools are appended
and routed by the live name→service map.

Two transforms, both generated from the catalogue (the single source of truth — never hand-written):

1. **Catalogue -> MCP tool descriptors.** ``list_tools`` calls the ``bd09`` ``list_capabilities``
   handler over the ingress and turns each registered Service Operation into one MCP ``Tool``:
   the tool ``name`` is the SO ID (e.g. ``SO-09-01``), the ``description`` is the SO summary, and
   the ``inputSchema`` is the tool's live Pydantic JSON Schema. If a tool's schema changed, the
   descriptor regenerates on the next ``list_tools`` — no hand-maintained tool schema lives here.

2. **MCP tool call -> Restate dispatch.** ``call_tool`` POSTs the SO ID and the arguments to the
   ``bd09`` ``execute_so`` handler over the ingress as the request envelope ``{"soId", "args"}``.
   It does **not** re-implement the tool — re-implementing would duplicate the catalogue (an SSOT
   violation) and bypass the journal. A deterministic failure (a bad argument, an unknown SO, a
   non-conventional cash-flow series, a malformed envelope) comes back from the service as a
   terminal HTTP 4xx and is surfaced to the MCP client as an error result, not a silent success.

Transport + topology choice (architecture 5.2 allows a sidecar or a Restate-registered handler).
This server is a **stdio sidecar process**: the ``mcp`` SDK's ``Server`` speaks the MCP transport
(stdio for the inspector and programmatic clients), which is not a Restate handler signature, and
the durability the architecture asks for is inherited by **dispatching over the ingress to the
journaled ``execute_so`` handler** rather than by the MCP transport itself being journaled. The
sidecar therefore stays a thin, stateless transform/dispatch layer; the durable boundary remains
the ``bd09`` service it calls. (An http-transport variant or a Restate-registered front is a later
option; the stdio sidecar is the minimal honest first face.)

Robustness (the productionised sidecar):

- **Fault classification.** Every ingress call (catalogue-load and dispatch) classifies its outcome
  on EVERY surface — the request, the HTTP status, AND the response body. A **terminal** failure
  (the service's 4xx — a bad argument / unknown SO / malformed envelope) raises
  :class:`McpToolError` carrying the clean status + the service detail. A **transient/infra**
  failure (an ``httpx`` transport error, a 5xx, a catalogue-load failure, OR a **2xx whose body is
  unparseable/partial** — a non-JSON / empty dispatch body, or a non-JSON / missing-``capabilities``
  / partial catalogue body) raises a *distinct* :class:`McpServiceUnavailableError` ("service
  unavailable — …; retry"). A malformed/partial 2xx body never escapes raw and never crashes the
  session: on the call path the ``mcp`` SDK turns the raised exception into an ``isError``
  ``CallToolResult`` carrying ``str(exc)``; on the catalogue-load (``list_tools``) path — which the
  SDK does NOT auto-wrap — it is converted to a clean :class:`McpError` so the session survives. The
  client always sees a clean classified message, never a stack trace, an internal path, the raw
  parse string, or the ingress credentials.
- **Boundary validation.** Before any dispatch POST, the tool ``name`` must be a known SO in the
  live catalogue and ``arguments`` must be a ``dict`` — an unknown name / a non-dict args object is
  rejected as a clean :class:`McpToolError` without touching ``execute_so``. (The ``bd09`` service
  still validates the argument *content* — this is only the boundary name+shape check.)
- **Structured logging.** One JSON line per ``list_tools`` / ``call_tool`` to **stderr only**
  (stdout is the stdio MCP transport — a stray stdout write corrupts the protocol). The line carries
  ``{event, soId, outcome, duration_ms, status_code}`` and never an argument *value* or any secret.
- **Concurrency guard.** A minimal in-process ``asyncio.Semaphore`` (env-bounded, generous default)
  guards the dispatch path; exceeding the bound returns a clean *busy* unavailable error rather than
  an unbounded queue or a crash. This is the honest minimal "rate limiting" for a single-operator
  stdio sidecar; meaningful multi-tenant rate-limiting belongs to the http-transport / deploy
  surface and is out of scope here.

Honest boundary: a green MCP listing + round-trip proves the *ingress plumbing* — the catalogue is
correctly exposed as MCP tools and a call dispatches journaled to the ``bd09`` service over
synthetic data. It is **not** an agent reasoning about which tool to call (that orchestrating loop
is built separately), nor a production deployment. This surface lets an external agent call the
*named* tools; it does not itself plan.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import anyio
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.shared.exceptions import McpError
from mcp.types import INTERNAL_ERROR, ErrorData, TextContent, Tool

# The Restate ingress the journaled per-BD handlers are reachable on. The MCP server dispatches over
# this ingress so each tool call goes through the durable, terminal-error-classified service path.
INGRESS_URL = os.environ.get("AGENTINVEST_RESTATE_INGRESS_URL", "http://localhost:8080")
BD09_SERVICE_NAME = "bd09"
BD12_SERVICE_NAME = "bd12"
BD12_RECON_SERVICE_NAME = "bd12Recon"
# The per-BD model-free dispatch services the MCP face exposes. Each hosts the SAME
# execute_so / list_capabilities envelope, so the server loads each catalogue and routes each tool
# call (by its SO name) to its owning service. bd09 (performance) + bd12 (book-of-record read,
# OIM-161) + bd12Recon (SD-12.10 reconcile, OIM-162). Additive: bd09's + bd12's listing + dispatch
# are byte-identical to before — bd12Recon is appended.
SERVICE_NAMES = (BD09_SERVICE_NAME, BD12_SERVICE_NAME, BD12_RECON_SERVICE_NAME)
MCP_SERVER_NAME = "agentinvest"

# The concurrency-guard bound. A generous default so a normal single-operator session is never
# throttled; a test sets it low to prove the guard bites. The honest minimal "rate limiting" for a
# stdio sidecar — meaningful multi-tenant rate-limiting belongs to the deploy/http surface.
_DEFAULT_MAX_CONCURRENT = 8


# --- typed faults (the two-way classification the MCP SDK turns into an isError result) -----------


class McpToolError(Exception):
    """A **terminal** tool/argument error — surfaced to the MCP client as an ``isError`` result.

    Raised for a deterministic failure the client must fix and not blindly retry: an unknown tool
    name, a non-dict arguments object, or the service's own terminal 4xx (a bad argument / unknown
    SO / malformed envelope). ``str(self)`` is the clean, client-safe message — no stack trace, no
    internal path, no ingress credentials.
    """


class McpServiceUnavailableError(Exception):
    """A **transient/infra** error — surfaced to the MCP client as a *distinct* ``isError`` result.

    Raised when the failure is NOT the client's fault and a retry may succeed: the ingress is
    unreachable / timed out, the service returned a 5xx, the catalogue could not be loaded, or the
    concurrency guard is saturated. The message is "agentINVEST service unavailable — …; retry" so
    a client can tell a retryable infra fault from a terminal tool error. ``str(self)`` is
    client-safe.
    """


# --- structured logging (JSON lines to stderr ONLY — stdout is the stdio MCP transport) ----------


class _StderrHandler(logging.StreamHandler):  # type: ignore[type-arg]
    """A ``StreamHandler`` that resolves ``sys.stderr`` at *emit* time, never stdout.

    Binding ``sys.stderr`` once at construction would capture whatever stream existed at import —
    which breaks under a test harness that swaps the streams (``capsys``) and, worse, could pin a
    stale handle. Resolving ``sys.stderr`` dynamically guarantees the JSON line always goes to the
    *current* stderr and never to stdout (stdout is the stdio MCP transport).
    """

    @property
    def stream(self) -> Any:
        return sys.stderr

    @stream.setter
    def stream(self, value: Any) -> None:
        # Ignore the base class's attempt to pin a stream at construction — stderr is resolved live.
        pass


class _JsonLineFormatter(logging.Formatter):
    """Render a log record's structured fields as one compact JSON line (no secrets, no arg values).

    Only the explicitly-attached safe fields are emitted (``event``, ``soId``, ``outcome``,
    ``duration_ms``, ``status_code``) plus the level — never the call ``arguments`` (which could
    carry data) and never any secret/key/URL-with-credentials.
    """

    _SAFE_FIELDS = ("event", "soId", "outcome", "duration_ms", "status_code")

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {"level": record.levelname, "logger": record.name}
        for field in self._SAFE_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if not any(field in payload for field in self._SAFE_FIELDS):
            # A plain message (e.g. startup) — include the literal message, never structured args.
            payload["message"] = record.getMessage()
        return json.dumps(payload, sort_keys=True)


def _build_logger() -> logging.Logger:
    """Build the module logger writing JSON lines to **stderr** at the env-configured level.

    Critically the handler targets ``sys.stderr`` — stdout is the stdio MCP transport and a stray
    stdout write corrupts the protocol. ``propagate`` is disabled so a root handler cannot re-emit
    the record to stdout.
    """
    log = logging.getLogger("agentinvest.mcp")
    level_name = os.environ.get("AGENTINVEST_MCP_LOG_LEVEL", "INFO").upper()
    log.setLevel(getattr(logging, level_name, logging.INFO))
    log.propagate = False
    if not log.handlers:
        handler = _StderrHandler()
        handler.setFormatter(_JsonLineFormatter())
        log.addHandler(handler)
    return log


_LOG = _build_logger()


def _log_event(
    event: str,
    *,
    outcome: str,
    duration_ms: int,
    so_id: str | None = None,
    status_code: int | None = None,
) -> None:
    """Emit one structured stderr line — safe fields only (never arg values, never a secret)."""
    _LOG.info(
        "%s",
        event,
        extra={
            "event": event,
            "soId": so_id,
            "outcome": outcome,
            "duration_ms": duration_ms,
            "status_code": status_code,
        },
    )


# --- the concurrency guard (a minimal in-process semaphore; clean busy error past the bound) ------


def _max_concurrent() -> int:
    """The concurrency-guard bound from the env (``AGENTINVEST_MCP_MAX_CONCURRENT``), generous."""
    raw = os.environ.get("AGENTINVEST_MCP_MAX_CONCURRENT")
    if raw is None:
        return _DEFAULT_MAX_CONCURRENT
    try:
        value = int(raw)
    except ValueError:
        return _DEFAULT_MAX_CONCURRENT
    return value if value > 0 else _DEFAULT_MAX_CONCURRENT


@asynccontextmanager
async def _concurrency_slot(semaphore: anyio.Semaphore) -> AsyncIterator[None]:
    """Acquire a concurrency slot non-blocking; saturated -> a clean busy unavailable error.

    A non-blocking acquire (vs an unbounded ``async with`` wait) means an over-limit burst returns a
    clean *busy* error rather than silently queueing without bound. The slot is released on exit.
    """
    try:
        semaphore.acquire_nowait()
    except anyio.WouldBlock as exc:
        raise McpServiceUnavailableError(
            "agentINVEST service unavailable — busy: too many concurrent tool calls; retry"
        ) from exc
    try:
        yield
    finally:
        semaphore.release()


# --- the ingress transforms (catalogue-load + dispatch), fault-classified ------------------------


async def _load_catalogue(
    client: httpx.AsyncClient, service: str = BD09_SERVICE_NAME
) -> list[dict[str, Any]]:
    """Fetch one per-BD service's live tool catalogue from ``list_capabilities`` over the ingress.

    The catalogue is the single source the MCP descriptors derive from — never a hand-written
    schema. ``list_capabilities`` is an arity-0 handler, so it is POSTed with an empty body (a JSON
    body would be rejected 400; this is the documented invocation-shape contract). ``service``
    selects the per-BD dispatch service (bd09 / bd12) — defaulting to bd09 so the existing single-
    service call path is byte-unchanged.

    Faults are classified on EVERY surface — the request, the status, AND the response body. A
    transport error / a 5xx / any non-2xx on catalogue-load, OR a **2xx whose body is unparseable or
    partial** (non-JSON, missing the ``capabilities`` key, a non-dict/garbage shape, or an entry
    missing a required ``soId``/``summary``/``inputSchema`` field), is a transient
    :class:`McpServiceUnavailableError` (the catalogue is infrastructure, not a per-call argument);
    the descriptors simply cannot be served right now, and the client should retry. A malformed 2xx
    body never escapes raw and never crashes the listing — it is one clean classified error.
    """
    try:
        resp = await client.post(f"{INGRESS_URL}/{service}/list_capabilities")
    except httpx.TransportError as exc:
        raise McpServiceUnavailableError(
            f"agentINVEST service unavailable — cannot load tool catalogue ({type(exc).__name__});"
            " retry"
        ) from exc
    if resp.status_code >= 400:
        raise McpServiceUnavailableError(
            "agentINVEST service unavailable — cannot load tool catalogue "
            f"(ingress returned {resp.status_code}); retry"
        )
    # The body-parse + shape guard: a 2xx with an unparseable/partial catalogue body is an
    # infrastructure anomaly (the service answered OK but sent something the sidecar can't use), the
    # SAME transient class — never a bare exception, never a session crash. Validate the whole shape
    # here (the single catalogue read every consumer shares), so a missing top-level key OR a
    # missing per-entry field both surface as one clean unreadable-catalogue error.
    try:
        payload = resp.json()
        capabilities: list[dict[str, Any]] = payload["capabilities"]
        for cap in capabilities:
            # Each entry must carry the fields the descriptor transform reads — a missing one is the
            # same "parses-but-partial" payload class, classified the same way (no per-entry crash).
            cap["soId"], cap["summary"], cap["inputSchema"]
    except (json.JSONDecodeError, ValueError, KeyError, TypeError) as exc:
        raise McpServiceUnavailableError(
            "agentINVEST service unavailable — tool catalogue is unreadable; retry"
        ) from exc
    return capabilities


def _capability_to_tool(cap: dict[str, Any]) -> Tool:
    """Transform one catalogue entry into an MCP tool descriptor (name = SO ID, schema = Pydantic).

    The agent-facing consumer surface: ``name`` is the SO ID, ``description`` is the SO summary and
    the ``inputSchema`` is the tool's live Pydantic JSON Schema. No builder framing leaks into the
    description — this is what an external MCP client sees.

    The descriptor carries no ``outputSchema``: a tool call returns the ``execute_so`` *envelope*
    (the tool ``result`` plus provenance + ``computedBy``), not the bare tool output, so declaring
    the tool's own output schema would mis-describe the call result (and the MCP SDK would reject
    the enveloped result against it). The result is returned as text content.
    """
    return Tool(
        name=cap["soId"],
        description=cap["summary"],
        inputSchema=cap["inputSchema"],
    )


# The SO-id → owning-service routing prefix map. The SO namespaces are structured per Business
# Domain (``SO-09-*`` is BD-09; ``SO-12.1-*`` / ``SO-12.2-*`` are BD-12 reads; ``SO-12.10-*`` is the
# SD-12.10 reconcile), so the owning service for a dispatch is derivable from the SO id WITHOUT
# loading every service's catalogue — which keeps a dispatch to one service loading only THAT
# service's catalogue (the bd09 / bd12 dispatch paths are unperturbed by adding bd12Recon). The name
# is still validated against the owning service's LIVE catalogue (the SSOT of valid names), so an
# unknown SO is still a clean error; the prefix only selects which catalogue to check.
#
# ORDER IS LOAD-BEARING: ``SO-12.10-`` (the reconcile) MUST be matched BEFORE ``SO-12.`` (the read),
# because ``SO-12.10-01`` also starts with ``SO-12.`` — the most specific prefix is checked first so
# a reconcile SO routes to bd12Recon, not bd12.
_SERVICE_BY_SO_PREFIX: tuple[tuple[str, str], ...] = (
    ("SO-09-", BD09_SERVICE_NAME),
    ("SO-12.10-", BD12_RECON_SERVICE_NAME),
    ("SO-12.", BD12_SERVICE_NAME),
)


def _owning_service(name: str) -> str | None:
    """The per-BD service that owns SO ``name`` by its id prefix, or ``None`` if no BD claims it."""
    for prefix, service in _SERVICE_BY_SO_PREFIX:
        if name.startswith(prefix):
            return service
    return None


async def list_tools_from_catalogue(client: httpx.AsyncClient) -> list[Tool]:
    """Generate the MCP tool descriptors live from the per-BD catalogues (the SSOT transform).

    Aggregates the catalogues across ``SERVICE_NAMES`` (bd09 + bd12) — the bd09 descriptors first,
    byte-for-byte as before, then the bd12 read tools appended (OIM-161, additive). Module-level
    (not buried in the server closure) so the catalogue->descriptors transform is directly testable
    on the same path the server uses. Emits one structured ``list_tools`` log line (ok/transient)
    and lets a transient catalogue-load failure propagate as a clean
    :class:`McpServiceUnavailableError` rather than crashing the listing.
    """
    started = time.monotonic()
    tools: list[Tool] = []
    try:
        for service in SERVICE_NAMES:
            capabilities = await _load_catalogue(client, service)
            tools.extend(_capability_to_tool(cap) for cap in capabilities)
    except McpServiceUnavailableError:
        _log_event(
            "list_tools",
            outcome="transient",
            duration_ms=_elapsed_ms(started),
        )
        raise
    _log_event("list_tools", outcome="ok", duration_ms=_elapsed_ms(started))
    return tools


async def dispatch_call(
    client: httpx.AsyncClient, name: str, arguments: dict[str, Any]
) -> list[TextContent]:
    """Dispatch an MCP tool call to the SO's owning ``execute_so`` over the ingress (journaled).

    The tool name is the SO ID; the arguments are mapped onto the ``execute_so`` envelope
    ``{"soId", "args"}`` and POSTed to the journaled handler of the SO's OWNING service (bd09 /
    bd12 — routed by the live name→service map). The tool is NOT re-implemented here — the owning
    service owns the compute/read and the journal. Module-level so the dispatch path is directly
    testable on the same code the server runs.

    Boundary validation runs BEFORE any POST: ``arguments`` must be a ``dict`` and ``name`` must be
    a known SO in a live catalogue (an unknown name is rejected without ever POSTing it). Faults are
    then classified two ways: a transport error / a 5xx is a transient
    :class:`McpServiceUnavailableError` ("service unavailable; retry"); the service's terminal 4xx
    is a :class:`McpToolError` carrying the clean status + detail. The ``mcp`` SDK turns either into
    an ``isError`` result — the client never sees a stack trace or the ingress credentials.
    """
    started = time.monotonic()

    # --- boundary validation (before any dispatch POST) ---
    if not isinstance(arguments, dict):
        _log_event("call_tool", outcome="rejected", duration_ms=_elapsed_ms(started), so_id=name)
        raise McpToolError(
            f"{name}: invalid arguments — expected a JSON object, got {type(arguments).__name__}"
        )
    # Route by the SO-id prefix to the OWNING service, then validate the name against THAT service's
    # live catalogue only, so a dispatch loads one service's catalogue (bd09's path is unchanged).
    # A name no BD claims, or one absent from its owning service's catalogue, is unknown.
    service = _owning_service(name)
    if service is None:
        _log_event("call_tool", outcome="rejected", duration_ms=_elapsed_ms(started), so_id=name)
        raise McpToolError(f"unknown tool '{name}' — not a registered Service Operation")
    known = {cap["soId"] for cap in await _load_catalogue(client, service)}
    if name not in known:
        _log_event("call_tool", outcome="rejected", duration_ms=_elapsed_ms(started), so_id=name)
        raise McpToolError(f"unknown tool '{name}' — not a registered Service Operation")

    # --- dispatch (fault-classified) — to the SO's owning per-BD service ---
    envelope = {"soId": name, "args": arguments}
    try:
        resp = await client.post(
            f"{INGRESS_URL}/{service}/execute_so",
            json=envelope,
        )
    except httpx.TransportError as exc:
        _log_event("call_tool", outcome="transient", duration_ms=_elapsed_ms(started), so_id=name)
        raise McpServiceUnavailableError(
            f"agentINVEST service unavailable — cannot reach {service}.execute_so for {name} "
            f"({type(exc).__name__}); retry"
        ) from exc

    if resp.status_code >= 500:
        # The ingress / service failed transiently (not a deterministic argument fault). Distinct
        # from a terminal 4xx so the client can retry rather than "fixing" a correct argument.
        _log_event(
            "call_tool",
            outcome="transient",
            duration_ms=_elapsed_ms(started),
            so_id=name,
            status_code=resp.status_code,
        )
        raise McpServiceUnavailableError(
            f"agentINVEST service unavailable — {service}.execute_so returned {resp.status_code} "
            f"for {name}; retry"
        )
    if resp.status_code >= 400:
        # The service classified this as a terminal (deterministic) failure — a bad argument, an
        # unknown SO, a malformed envelope. Surface it as a terminal tool error (not a retry).
        detail = resp.text
        _log_event(
            "call_tool",
            outcome="terminal",
            duration_ms=_elapsed_ms(started),
            so_id=name,
            status_code=resp.status_code,
        )
        raise McpToolError(f"{name}: {service}.execute_so returned {resp.status_code}: {detail}")

    # The success-path body-parse guard: a 2xx whose body is unparseable/empty is an infrastructure
    # anomaly (the service answered OK but sent something unreadable), NOT a caller-argument fault.
    # Classify it as the SAME transient class — never leak the raw parse string, never a bare
    # exception. The clean message carries no body content.
    try:
        result = resp.json()
    except (json.JSONDecodeError, ValueError) as exc:
        _log_event(
            "call_tool",
            outcome="transient",
            duration_ms=_elapsed_ms(started),
            so_id=name,
            status_code=resp.status_code,
        )
        raise McpServiceUnavailableError(
            f"agentINVEST service unavailable — {service}.execute_so returned an unreadable "
            f"response for {name}; retry"
        ) from exc
    _log_event(
        "call_tool",
        outcome="ok",
        duration_ms=_elapsed_ms(started),
        so_id=name,
        status_code=resp.status_code,
    )
    return [TextContent(type="text", text=_render_result(result))]


def build_server(client: httpx.AsyncClient) -> Server:
    """Build the MCP server bound to an httpx client that dispatches over the Restate ingress.

    The ``client`` is injected so a programmatic test (or the real ``mcp`` client SDK over an
    in-memory stream pair) can drive the same ``list_tools``/``call_tool`` dispatch path the stdio
    process uses, without a subprocess. The handlers delegate to the module-level
    ``list_tools_from_catalogue`` / ``dispatch_call`` so the logic is testable in isolation, and a
    per-server :class:`anyio.Semaphore` guards the dispatch path (the concurrency guard).
    """
    server: Server = Server(MCP_SERVER_NAME)
    semaphore = anyio.Semaphore(_max_concurrent())

    @server.list_tools()  # type: ignore[no-untyped-call, untyped-decorator]
    async def list_tools() -> list[Tool]:
        """List the bd09 Service Operations as MCP tools — generated live from the catalogue.

        The ``mcp`` SDK's ``list_tools`` handler — unlike ``call_tool`` — does NOT wrap a raised
        exception into a clean error result; an exception escaping here tears down the session task
        group. So a transient catalogue-load fault (transport / non-2xx / **an unparseable or
        partial 2xx body**) is converted to a clean :class:`McpError` (the SDK maps that to a
        JSON-RPC error response, never a session crash). This mirrors how ``call_tool`` surfaces the
        typed errors:
        a malformed/partial catalogue is a clean classified error the client can read and retry,
        and the session stays usable.
        """
        try:
            return await list_tools_from_catalogue(client)
        except McpServiceUnavailableError as exc:
            raise McpError(ErrorData(code=INTERNAL_ERROR, message=str(exc))) from exc

    @server.call_tool()  # type: ignore[untyped-decorator]
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Dispatch an MCP call to the SO's owning ``execute_so`` over the ingress (guarded)."""
        async with _concurrency_slot(semaphore):
            return await dispatch_call(client, name, arguments)

    return server


def _render_result(result: dict[str, Any]) -> str:
    """Render the execute_so result envelope as JSON text for the MCP TextContent payload."""
    return json.dumps(result, indent=2, sort_keys=True)


def _elapsed_ms(started: float) -> int:
    """Milliseconds elapsed since a ``time.monotonic()`` start mark (for the structured log)."""
    return int((time.monotonic() - started) * 1000)


async def _run_stdio() -> None:
    """Serve the MCP server over stdio (the inspector / programmatic-client channel)."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        server = build_server(client)
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )


def main() -> None:
    anyio.run(_run_stdio)


if __name__ == "__main__":
    main()
