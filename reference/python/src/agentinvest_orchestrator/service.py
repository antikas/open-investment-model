"""The ``agentinvestPlanner`` Restate service — the planning step's service boundary.

A model-free Restate **service** (sibling on the service axis to ``bd09``) hosting
the ONE handler the orchestrator's single reasoning loop runs in: ``planTask``.
The orchestrator (the ``investmentOperation`` virtual object) calls it at seam 1
via the legal direct ``ctx.serviceClient(agentinvestPlanner).planTask(...)`` shape,
so the plan — the model's non-deterministic output — is **journaled exactly once**
by Restate's call semantics and replay reads it back rather than re-invoking the
model.

The service name is agentINVEST-scoped (``agentinvestPlanner``, the ``bd09`` /
``pyTools`` naming discipline) so it does not collide with a same-named service
from a sibling project on the shared dev Restate.

Service, not agent (ADR-0054). ``agentinvestPlanner`` is a hosting/dispatch
boundary; the reasoning is the ``.plan()`` call it makes. The SOs it plans over are
tools. There is one loop, here.

Error classification (the OIM-112/113 deterministic-error-is-terminal discipline).
``plan_task`` raises a typed pair: ``PlannerDeterministicError`` (a missing key, a
malformed / schema-invalid response, a 4xx) and ``PlannerTransientError`` (429 /
529 / timeout / connection). This handler maps the FIRST to a Restate
``TerminalError`` so Restate does NOT retry a failure re-running cannot fix (no
retry storm); it lets the SECOND propagate as a plain exception so Restate retries
it (bounded). A deterministic bad plan is terminal; a transient API blip is
retried — never the other way round.

The key is NEVER in this module's surface: it loads from ``reference/.env`` inside
``plan_task`` (python-dotenv) and is handed only to the SDK client. No log line,
exception message, or handler output carries it.
"""

from __future__ import annotations

from typing import Any

import restate
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from restate.exceptions import TerminalError

from agentinvest_orchestrator.plan_schema import PlanSchema
from agentinvest_orchestrator.planner import (
    PlannerDeterministicError,
    PlannerTransientError,
    ToolDescriptor,
    plan_task,
)
from agentinvest_tools.request_serde import PassThroughJsonSerde

PLANNER_SERVICE_NAME = "agentinvestPlanner"


class CandidateTool(BaseModel):
    """One candidate tool in the ``planTask`` request catalogue (transport shape).

    The orchestrator passes the per-task catalogue (loaded via the tool-RAG seam)
    in the request, so the service is stateless over the catalogue: the planner
    selects among exactly the tools the orchestrator scoped. ``inputSchema`` is
    optional (the live bd09 tools carry it; the eval golden tools do not).
    """

    model_config = ConfigDict(extra="forbid")

    soId: str = Field(description="The Service-Operation id of the candidate tool.")
    name: str = Field(description="The tool's display name.")
    summary: str = Field(description="The tool's natural-language summary.")
    inputSchema: dict[str, Any] | None = Field(
        default=None, description="The tool's input JSON schema, when available."
    )


class PlanTaskInput(BaseModel):
    """The ``planTask`` request — a task plus an optional candidate tool catalogue + guardrails.

    The orchestrator may pass the candidate ``catalogue`` it scoped (the eval path,
    and any future per-task scoping). When it omits the catalogue (or passes an
    empty list), the service loads the BD-09 catalogue itself via the tool-RAG seam
    (``load_tool_catalogue_from_bd09`` over ``bd09.list_capabilities``) — the
    orchestrator path. Either way the planner selects only among the catalogue.
    """

    model_config = ConfigDict(extra="forbid")

    task: str = Field(description="The analyst task to plan (a natural-language request).")
    catalogue: list[CandidateTool] = Field(
        default_factory=list,
        description=(
            "The candidate tool descriptors the planner selects among. Omit/empty to "
            "have the service load the BD-09 catalogue via the tool-RAG seam."
        ),
    )
    guardrails: str | None = Field(
        default=None,
        description="Optional planning guardrails (defaults to the planner's own).",
    )


agentinvestPlanner = restate.Service(PLANNER_SERVICE_NAME)


def _coerce_request(req: Any) -> PlanTaskInput:
    """Validate the raw request body against ``PlanTaskInput`` (``extra="forbid"``), or a clean 400.

    A valid body is either an already-built ``PlanTaskInput`` (a typed-ingress path) or a plain
    ``dict`` (the pass-through-serde / unit-test path); the dict is validated through
    ``model_validate`` so an UNRECOGNISED request key is a clean ``TerminalError`` (400). Run in the
    HANDLER BODY (the SDK re-wraps a serde error as a status-less 500); the message is clean.
    """
    if isinstance(req, PlanTaskInput):
        return req
    if not isinstance(req, dict):
        raise TerminalError(
            f"planTask: request body must be a JSON object — got {type(req).__name__}",
            status_code=400,
        )
    try:
        return PlanTaskInput.model_validate(req)
    except ValidationError as exc:
        raise TerminalError(
            f"planTask: invalid request — {exc.error_count()} error(s): {exc}",
            status_code=400,
        ) from exc


def _to_descriptors(catalogue: list[CandidateTool]) -> tuple[ToolDescriptor, ...]:
    return tuple(
        ToolDescriptor(
            so_id=c.soId,
            name=c.name,
            summary=c.summary,
            input_schema=c.inputSchema,
        )
        for c in catalogue
    )


@agentinvestPlanner.handler(name="planTask", input_serde=PassThroughJsonSerde())
async def plan_task_handler(ctx: restate.Context, req: PlanTaskInput) -> dict[str, Any]:
    """Plan one task: one real Sonnet 4.6 structured-output call → a validated plan.

    Returns the ``PlanSchema`` as a plain JSON dict (the orchestrator parses it
    against a thin zod mirror; this service is the schema SSOT and returns an
    already-validated plan). The plan is GENERATED, not executed — dispatch is a
    separate step (OIM-131).

    Error classification: a ``PlannerDeterministicError`` (missing key, malformed /
    schema-invalid response, 4xx) becomes a Restate ``TerminalError`` (no retry
    storm); a ``PlannerTransientError`` (429/529/timeout) is re-raised as a plain
    exception so Restate retries it (bounded). Neither path's message carries the
    key.

    The model call is NOT wrapped in ``ctx.run`` here. The orchestrator calls this
    handler via ``ctx.serviceClient(agentinvestPlanner).planTask(...)`` — that RPC is
    journaled by Restate's call semantics, so the non-deterministic plan is
    journaled exactly once at the CALL boundary (the legal shape A). Wrapping the
    model call in a nested ``ctx.run`` here would be redundant and is unnecessary;
    the journaling is the orchestrator's call, not an inner step.

    An UNRECOGNISED request key is a clean ``TerminalError`` (400) before any planning (the
    reject-unknown-keys hardening, consistent with the tool-service request contracts); the valid
    contract keys are unchanged. The planner's own deterministic (422) / transient (retry)
    classification is untouched.
    """
    request = _coerce_request(req)
    if request.catalogue:
        descriptors = _to_descriptors(request.catalogue)
    else:
        # The orchestrator path: load the BD-09 (performance) + BD-12 (book-of-record read)
        # catalogues via the tool-RAG seam (load-all at the v0.1 surface — the seam, not real
        # retrieval; see tool_catalogue). The BD-09 descriptors come first BYTE-FOR-BYTE (the W1
        # NAV-strike path is unperturbed); the BD-12 read tools are appended (OIM-161, additive).
        from agentinvest_orchestrator.tool_catalogue import load_tool_catalogue_from_services

        descriptors = load_tool_catalogue_from_services(request.task)
    guardrails = request.guardrails
    try:
        if guardrails is not None:
            plan: PlanSchema = plan_task(request.task, descriptors, guardrails)
        else:
            plan = plan_task(request.task, descriptors)
    except PlannerDeterministicError as exc:
        # Deterministic — re-running reproduces it. Terminal, so Restate does NOT
        # retry-storm. The message is key-free by construction (see planner.py).
        raise TerminalError(f"planTask deterministic failure: {exc}", status_code=422) from exc
    except PlannerTransientError as exc:
        # Transient — let Restate retry (bounded). Re-raise as a plain exception so
        # the SDK classifies it retryable (NOT a TerminalError).
        raise RuntimeError(f"planTask transient fault (retryable): {exc}") from exc

    return plan.model_dump(mode="json")
