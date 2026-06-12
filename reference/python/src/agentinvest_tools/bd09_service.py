"""The ``bd09`` model-free Restate dispatch service — the per-Business-Domain tool boundary.

This is the BD-09 (Performance & Analytics) entry on the *service* axis: a model-free Restate
service that hosts the BD-09 tool catalogue and dispatches a *named* Service Operation to its tool
as a journaled durable step. It is the per-Business-Domain dispatch boundary the single
orchestrating loop invokes over typed Restate RPC.

Service, not agent (the load-bearing topology point). Per the agentINVEST topology, the per-BD
layer is a **model-free dispatch / tool-hosting boundary** — a namespace + single-writer state
isolation seam — that carries **no reasoning loop**. It routes a *named* SO to its tool; it does
**not** decide which SO to call. That decision belongs to the one orchestrating loop (the
``InvestmentOperation`` planning step), built separately. A green ``execute_so`` proves the
*plumbing* — typed dispatch, journaling, and terminal-error classification over the tool surface —
NOT an agent reasoning about which operation to run. The catalogue is *tools*; this is a *service*.

Two handlers:

- ``execute_so(soId, args)`` — looks the SO up in the registry of the five BD-09 tools, maps the
  ``args`` dict onto the tool's Pydantic input (honouring the tools' ``extra="forbid"`` — an
  unknown, missing or mistyped argument is a deterministic input error), runs the tool inside a
  journaled ``ctx.run`` step, and returns the typed result plus replay-safe provenance.
- ``list_capabilities()`` — returns the registered catalogue: each so_id with its real input and
  output JSON schema (derived from the Pydantic models, never stubbed).

Error classification (load-bearing). The tools are pure and deterministic, so essentially every
failure they can produce is a **deterministic error** that re-running cannot fix: an unknown
so_id, a bad/extra/missing argument (a Pydantic ``ValidationError``), a non-conventional cash-flow
series (the fail-loud ``NonConventionalCashFlowError``), or *any* other deterministic compute
failure — not only the input ``ValueError``\\ s but a ``ZeroDivisionError`` (a long-dated series
underflowing the IRR solver bracket), a ``decimal``/``ArithmeticError`` overflow (extreme-magnitude
inputs), a ``TypeError`` or ``KeyError``. The compute catch is therefore the **whole exception
class** (``except Exception``), not a narrow ``ValueError``: every one is raised as a Restate
``TerminalError`` so **Restate does not retry it**. This matters because the Restate Python SDK
retries a plain exception escaping a ``ctx.run`` step by default (it treats it as transient) — a
deterministic failure left unclassified would retry forever, a hang and a cost landmine.

Why the broad catch is correct *here*: this layer is **pure** — the tools take typed inputs and
compute, with no I/O, clock or RNG, so they have **no genuinely-transient failure surface**. Making
every tool-compute exception terminal is therefore strictly safer (a deterministic failure must
never retry). Forward refinement (a carry-forward, not built here): when a BD later hosts an
**I/O-touching** tool (reading the data layer / the marts), the classification must distinguish a
**transient** I/O failure (retryable — a recoverable DB blip must not be made permanent) from a
**deterministic** compute failure (terminal). At that point the I/O tool should raise a *typed
retryable* error that this layer lets propagate, rather than this catch terminalising everything.
For the current pure layer, all-compute-terminal is the safe and correct classification.

Provenance is replay-safe by construction: the metadata returned is derived solely from the request
and the tool's deterministic output (the so_id, the tool name, the methodology label the tool
itself emits). No wall-clock or other non-deterministic source is read inside (or outside) the
journaled step, so a replay reproduces the same provenance exactly.

Honest boundary: this wires the *synthetic* BD-09 tool surface over the durable substrate. A green
dispatch proves typed-dispatch + journaling + terminal-error classification; the tools' own honest
boundary (a correct computation over synthetic inputs is not a GIPS-verified production figure)
carries through unchanged.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypedDict

import restate
import restate.serde
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from restate.exceptions import TerminalError

from agentinvest_tools.bd09 import (
    BenchmarkRelativeReturnInput,
    BenchmarkRelativeReturnOutput,
    ContributionBreakdownInput,
    ContributionBreakdownOutput,
    MoneyWeightedReturnInput,
    MoneyWeightedReturnOutput,
    TimeWeightedReturnInput,
    TimeWeightedReturnOutput,
    TotalReturnInput,
    TotalReturnOutput,
    so_09_01_compute_total_return,
    so_09_02_compute_time_weighted_return,
    so_09_03_compute_money_weighted_return,
    so_09_04_compute_benchmark_relative_return,
    so_09_05_compute_contribution_breakdown,
)

BD09_SERVICE_NAME = "bd09"


@dataclass(frozen=True)
class ToolSpec:
    """One registry entry — a named Service Operation bound to its tool.

    ``compute`` is the pure tool function; ``input_model`` / ``output_model`` are its Pydantic I/O
    models (the source of truth for the auto-generated catalogue and, later, the MCP/OpenAPI
    surfaces). ``compute`` is typed loosely (``BaseModel`` in/out) because the registry is
    heterogeneous over the five tools; each entry pairs a model with its matching function.
    """

    so_id: str
    name: str
    summary: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    compute: Callable[[Any], BaseModel]


# The registered BD-09 tool catalogue — the five SD-09.1 Service Operations. Each so_id maps to its
# tool plus the Pydantic models that define its contract. Adding a BD-09 tool is one row here; the
# dispatch, the catalogue and the schemas all derive from it.
_REGISTRY: dict[str, ToolSpec] = {
    spec.so_id: spec
    for spec in (
        ToolSpec(
            so_id="SO-09-01",
            name="compute_total_return",
            summary="Total return over a window (Modified Dietz, day-weighted external flows).",
            input_model=TotalReturnInput,
            output_model=TotalReturnOutput,
            compute=so_09_01_compute_total_return,
        ),
        ToolSpec(
            so_id="SO-09-02",
            name="compute_time_weighted_return",
            summary="True time-weighted return (sub-period returns linked geometrically).",
            input_model=TimeWeightedReturnInput,
            output_model=TimeWeightedReturnOutput,
            compute=so_09_02_compute_time_weighted_return,
        ),
        ToolSpec(
            so_id="SO-09-03",
            name="compute_money_weighted_return",
            summary="Money-weighted return (the IRR of the dated cash-flow series).",
            input_model=MoneyWeightedReturnInput,
            output_model=MoneyWeightedReturnOutput,
            compute=so_09_03_compute_money_weighted_return,
        ),
        ToolSpec(
            so_id="SO-09-04",
            name="compute_benchmark_relative_return",
            summary="Active/excess return (portfolio minus benchmark; arithmetic or geometric).",
            input_model=BenchmarkRelativeReturnInput,
            output_model=BenchmarkRelativeReturnOutput,
            compute=so_09_04_compute_benchmark_relative_return,
        ),
        ToolSpec(
            so_id="SO-09-05",
            name="compute_contribution_breakdown",
            summary="Segment contributions (weight x segment return) summing to the total.",
            input_model=ContributionBreakdownInput,
            output_model=ContributionBreakdownOutput,
            compute=so_09_05_compute_contribution_breakdown,
        ),
    )
}


class ExecuteSoInput(BaseModel):
    """The ``execute_so`` request envelope — a named SO plus its argument dict.

    A **Pydantic model** (not a bare ``TypedDict``) so the Restate auto-generated OpenAPI/MCP
    surface derives a *real, typed* request schema from it — the envelope is typed at the boundary
    (goal (c)): a malformed body that is not this shape is rejected by the SDK's typed deserialiser
    as a ``TerminalError`` (no retry) before the handler runs. ``soId`` is the Service-Operation
    identifier (e.g. ``"SO-09-01"``); ``args`` is the tool's input as a plain object, mapped onto
    the tool's own ``extra="forbid"`` Pydantic input inside the journaled step.

    The envelope itself is permissive on ``args`` (an arbitrary object) on purpose — the *per-tool*
    validation (which argument keys are allowed) belongs to each tool's input model, surfaced via
    ``list_capabilities``; the envelope only types the *transport shape*.
    """

    model_config = ConfigDict(extra="forbid")

    soId: str = Field(description="The Service-Operation identifier to dispatch, e.g. 'SO-09-01'.")
    args: dict[str, Any] = Field(
        default_factory=dict,
        description="The tool's arguments as a JSON object, mapped onto the tool's typed input.",
    )


class ExecuteSoProvenance(TypedDict):
    """Replay-safe provenance — derived from the request + the tool's deterministic output."""

    soId: str
    tool: str
    methodology: str


class ExecuteSoOutput(TypedDict):
    """The ``execute_so`` result envelope — the typed tool result plus provenance."""

    result: dict[str, Any]
    provenance: ExecuteSoProvenance
    computedBy: str


class CapabilityDescriptor(TypedDict):
    """One catalogue entry — a named SO with its real input/output JSON schema."""

    soId: str
    name: str
    summary: str
    inputSchema: dict[str, Any]
    outputSchema: dict[str, Any]


class ListCapabilitiesOutput(TypedDict):
    """The ``list_capabilities`` result — the registered tool catalogue."""

    service: str
    capabilities: list[CapabilityDescriptor]


bd09 = restate.Service(BD09_SERVICE_NAME)


class ExecuteSoEnvelopeSerde(restate.serde.Serde[Any]):
    """A permissive pass-through JSON deserialiser so the in-handler envelope guard owns the status.

    The envelope-type guard must make a malformed non-dict body **terminal 400** (the ingress
    completion of deterministic-error-is-terminal). The catch: the Restate SDK *re-wraps* any
    exception raised inside a serde's ``deserialize`` as its own status-less ``TerminalError``
    (surfaced HTTP 500), discarding a serde-set status code — so the guard cannot set 400 from the
    serde. This serde therefore does NOT validate or raise: it parses the JSON body and returns the
    raw value unchanged (a dict, or a non-dict for a malformed body). The handler's
    ``_coerce_envelope`` then runs the guard in the *handler body* (where a raised ``TerminalError``
    keeps its 400, not re-wrapped), so a non-dict body is a clean terminal **400**.

    The handler keeps its typed ``ExecuteSoInput`` annotation, so the auto-generated OpenAPI/MCP
    surface schema stays a typed object naming ``soId``/``args`` (the SDK derives the schema from
    the Pydantic annotation independently of the serde). Result: the surface is typed AND a
    malformed body is terminal 400 — both halves of the carry-forward, the bounded-retry closed.
    """

    def deserialize(self, buf: bytes) -> Any:
        if not buf:
            # An empty body parses to an empty envelope; the handler guard rejects the missing soId
            # as a terminal 404 (unknown SO). Returning {} keeps the status logic in the handler.
            return {}
        try:
            # A valid JSON non-dict (array/string/number/null) is returned as-is for the in-handler
            # guard to reject as a clean 400.
            return json.loads(buf)
        except Exception:
            # The pass-through serde must NEVER raise (the SDK re-wraps a serde-raised exception as
            # a status-less 500). ``except Exception`` (NOT ``BaseException`` — KeyboardInterrupt /
            # SystemExit keep propagating) makes the never-raise invariant STRUCTURALLY TRUE: an
            # enumerated tuple (``json.JSONDecodeError`` / ``ValueError`` / ``UnicodeDecodeError``)
            # missed ``RecursionError`` (raised by ``json.loads`` on a deeply-nested body — a
            # ``RuntimeError`` subclass, not a ``ValueError``) which escaped → a status-less 500
            # (OIM-187 cycle-2). The serde does NOTHING but parse, so a blanket catch masks no
            # logic.
            # Any parse failure — malformed JSON, non-UTF8, RecursionError on a deeply-nested body,
            # MemoryError on a huge body — returns the raw decoded text as a non-dict ``str`` so
            # ``_coerce_envelope`` rejects it as a clean ``TerminalError(400)`` via its existing
            # non-dict branch — consistent with the pass-through handlers, while bd09's own envelope
            # contract (soId/args) stays its own (not the shared serde).
            return buf.decode("utf-8", errors="replace")

    def serialize(self, obj: Any) -> bytes:
        if obj is None:
            return b""
        return json.dumps(obj).encode("utf-8")


def _dispatch(spec: ToolSpec, args: dict[str, Any]) -> ExecuteSoOutput:
    """Map ``args`` onto the tool's input, run the tool, and shape the result.

    Runs inside the journaled ``ctx.run`` step. Any deterministic failure — a Pydantic
    ``ValidationError`` from the envelope mapping (unknown/missing/mistyped arg under
    ``extra="forbid"``), or *any* exception from the tool compute (the fail-loud
    ``NonConventionalCashFlowError`` and the input ``ValueError``\\ s, but also a
    ``ZeroDivisionError``, a ``decimal``/``ArithmeticError`` overflow, a ``TypeError`` — the whole
    deterministic-compute class) — is re-raised as a ``TerminalError`` so Restate does not retry a
    failure that re-running cannot fix. The tools are pure, so every compute exception is
    deterministic and terminal is strictly safe; an I/O-touching tool (a future BD) would instead
    raise a typed *retryable* error this layer lets propagate.
    """
    try:
        tool_input = spec.input_model.model_validate(args)
    except ValidationError as exc:
        raise TerminalError(
            f"{spec.so_id} ({spec.name}): invalid arguments — {exc.error_count()} error(s): {exc}",
            status_code=400,
        ) from exc

    try:
        output = spec.compute(tool_input)
    except Exception as exc:
        # Any deterministic compute failure — terminal, never retried. The tools are pure (no I/O,
        # clock or RNG), so every exception escaping a tool compute is deterministic: re-running the
        # same typed input recomputes the same failure. The class is not only the fail-loud
        # NonConventionalCashFlowError and the input ValueErrors but every deterministic compute
        # exception type — ZeroDivisionError (a long-dated series underflowing the IRR bracket),
        # decimal.* / ArithmeticError (extreme-magnitude inputs), TypeError, KeyError. Catching the
        # whole exception class (not a narrow ValueError) is what keeps every one of them off the
        # retry path; a non-ValueError deterministic failure left to escape ctx.run would be
        # classified transient and retried unboundedly (a hang and a cost landmine).
        #
        # This blanket-terminal classification is correct *because this layer is pure*. When a BD
        # later hosts an I/O-touching tool, the classification must distinguish a transient I/O
        # failure (retryable — a recoverable data-layer blip must not become permanent) from a
        # deterministic compute failure (terminal); that tool should raise a typed retryable error
        # this layer lets propagate, rather than this catch terminalising everything. No such
        # transient surface exists in the current pure layer, so all-compute-terminal is the safe
        # classification here.
        raise TerminalError(
            f"{spec.so_id} ({spec.name}): {type(exc).__name__}: {exc}",
            status_code=422,
        ) from exc

    return {
        "result": output.model_dump(mode="json"),
        "provenance": {
            "soId": spec.so_id,
            "tool": spec.name,
            "methodology": getattr(output, "methodology", spec.name),
        },
        "computedBy": f"python:{BD09_SERVICE_NAME}",
    }


def _coerce_envelope(req: Any) -> dict[str, Any]:
    """Validate the request body against the published envelope schema, or fail terminal.

    The envelope-type guard (the ingress completion of deterministic-error-is-terminal) AND the
    envelope-schema guard (making the *published contract* true). A valid body is either an
    ``ExecuteSoInput`` model (the typed Restate ingress path) or a plain ``dict`` (the
    programmatic / unit-test path); the dict is then **validated through ``ExecuteSoInput``** so the
    runtime actually enforces what the auto-generated OpenAPI/MCP schema advertises.

    Two guards, in order:

    1. **The type guard** — anything that is not an ``ExecuteSoInput`` or a ``dict`` (a top-level
       array, string, number or ``null``) is a deterministic input error: a raw ``req.get`` on it
       would raise an ``AttributeError`` *outside* the journaled ``ctx.run`` step, escaping the
       compute catch and being (mis)classified transient, so Restate would retry a body that
       re-sending cannot fix. The explicit ``isinstance`` guard raises a clear ``TerminalError``
       (400) instead — terminal at the boundary, never on the retry path.

    2. **The schema guard** — a ``dict`` body is validated through ``ExecuteSoInput.model_validate``
       (``extra="forbid"`` + ``soId``-is-a-string). This makes the runtime enforce the *exact*
       constraint the published ``execute_soRequest`` schema advertises (``additionalProperties:
       false`` + ``soId`` required string): an extra top-level key, a non-string ``soId``, or a
       missing ``soId`` is a ``ValidationError`` → a clear ``TerminalError`` (400). Without this,
       the permissive pass-through serde lets an extra-key / wrong-type envelope through with HTTP
       200, so the published contract would *lie* (advertise a constraint the ingress never checks).

    Both guards run in the **handler body** (not the serde) on purpose: the Restate SDK re-wraps an
    exception raised inside a serde's ``deserialize`` as a status-less ``TerminalError`` (HTTP 500),
    discarding a serde-set 400 — so the 400 must be raised here to stay a clean terminal 400 (the
    cycle-1 design choice, preserved). The model is dumped back to a plain dict so the downstream
    registry lookup / arg-mapping path is unchanged.
    """
    if isinstance(req, ExecuteSoInput):
        return req.model_dump()
    if not isinstance(req, dict):
        raise TerminalError(
            f"execute_so: request body must be a JSON object with 'soId' and 'args' — "
            f"got {type(req).__name__}",
            status_code=400,
        )
    try:
        envelope = ExecuteSoInput.model_validate(req)
    except ValidationError as exc:
        raise TerminalError(
            f"execute_so: invalid request envelope — {exc.error_count()} error(s): {exc}",
            status_code=400,
        ) from exc
    return envelope.model_dump()


@bd09.handler(name="execute_so", input_serde=ExecuteSoEnvelopeSerde())
async def execute_so(ctx: restate.Context, req: ExecuteSoInput) -> ExecuteSoOutput:
    """Dispatch a named BD-09 Service Operation to its tool as a journaled durable step.

    Model-free dispatch — it routes the *named* ``soId`` to its registered tool; it does not decide
    which SO to call (that is the orchestrator's one planning loop, built separately). An unknown
    ``soId`` is a ``TerminalError`` (Restate does not retry it). The ``args`` are mapped onto the
    tool's Pydantic input inside the journaled step; a bad/extra/missing argument or a deterministic
    compute failure (including the non-conventional-cash-flow fail-loud) is likewise terminal —
    never a retry storm.

    The request envelope is the ``ExecuteSoInput`` Pydantic model, so the Restate auto-generated
    OpenAPI/MCP surface types it and the SDK's typed deserialiser rejects a non-object body as a
    ``TerminalError`` (no retry) before this handler runs; ``_coerce_envelope`` carries the same
    guard for the programmatic path. A malformed non-dict body is therefore terminal at the ingress
    (the OIM-113 carry-forward), not a bounded retry.

    Provenance is replay-safe: it is derived only from the request and the tool's deterministic
    output (no wall-clock is read inside the journaled step).
    """
    envelope = _coerce_envelope(req)

    so_id = envelope.get("soId")
    spec = _REGISTRY.get(so_id) if so_id is not None else None
    if spec is None:
        raise TerminalError(
            f"unknown Service Operation '{so_id}' — registered: {sorted(_REGISTRY)}",
            status_code=404,
        )

    args = envelope.get("args", {})

    # The tool call is a journaled durable step. _dispatch classifies every deterministic failure
    # as a TerminalError before it escapes the step, so Restate records a terminal failure (no
    # retry) rather than retrying a deterministic error forever.
    return await ctx.run(f"so-{spec.so_id}", lambda: _dispatch(spec, args))


@bd09.handler(name="list_capabilities")
async def list_capabilities(ctx: restate.Context) -> ListCapabilitiesOutput:
    """Return the registered BD-09 tool catalogue — each so_id with its real I/O JSON schema.

    The schemas are the live Pydantic ``model_json_schema()`` of each tool's input and output, the
    single source the MCP and OpenAPI surfaces (built separately) generate from. Read-only; no
    journaled step needed (it derives from the static registry).

    Invocation note: this handler takes no input argument, so over the Restate HTTP ingress it is
    called with an empty request body (``POST /bd09/list_capabilities`` with no body) — a JSON body
    is rejected. ``execute_so``, which takes an input, is called with the JSON request envelope.
    """
    capabilities: list[CapabilityDescriptor] = [
        {
            "soId": spec.so_id,
            "name": spec.name,
            "summary": spec.summary,
            "inputSchema": spec.input_model.model_json_schema(),
            "outputSchema": spec.output_model.model_json_schema(),
        }
        for spec in _REGISTRY.values()
    ]
    return {"service": BD09_SERVICE_NAME, "capabilities": capabilities}
