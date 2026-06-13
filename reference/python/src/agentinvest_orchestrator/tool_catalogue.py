"""``load_tool_catalogue`` — the tool-RAG seam over the candidate tool surface.

The catalogue is the set of candidate ``ToolDescriptor``s the planner selects
among for a task. Two sources:

- **the orchestrator path** — the live ``bd09.list_capabilities`` catalogue (the
  5 SO-09 tool schemas), loaded over the Restate ingress;
- **the eval path** — the eval set's candidate descriptors (the SAME candidate
  sets the OIM-105/106 deterministic baseline scored over), built from an
  ``EvalSet``'s ``tools``.

**Honest boundary — this is a SEAM, not real retrieval (ADR-0054).** At ~5 BD-09
tools (or ~16 in the cross-office eval set), there is nothing to retrieve: the
catalogue is small enough to pass whole. ``load_tool_catalogue`` therefore
*loads all candidate tools* — a documented v0.1 behaviour, NOT a sophisticated
RAG doing dynamic scoping. The **seam exists** so that when OIM-120+ grows the
surface to ~900 tools, a real per-task retriever (embedding / RAG over the
catalogue) plugs in HERE without changing the planner or the orchestrator. We do
NOT pretend a large-catalogue retriever is load-bearing yet — it is not. The
function's contract (task + source -> candidate descriptors) is the seam; its
v0.1 body is load-all.
"""

from __future__ import annotations

from typing import Any

from agentinvest_orchestrator.planner import ToolDescriptor

BD09_SERVICE_NAME = "bd09"
BD12_SERVICE_NAME = "bd12"
BD12_RECON_SERVICE_NAME = "bd12Recon"
ENTITY_RESOLUTION_SERVICE_NAME = "entityResolution"


def load_tool_catalogue_from_bd09(
    task: str,  # noqa: ARG001 - the seam's task arg (a real retriever would scope on it)
) -> tuple[ToolDescriptor, ...]:
    """Load the BD-09 candidate catalogue from the bd09 registry (the seam).

    The orchestrator path's catalogue source. The ``bd09`` service's ``_REGISTRY``
    IS the SSOT that ``list_capabilities`` serves; this seam reads it **in-process**
    (the planner runs in the same Python endpoint the ``bd09`` service is bound
    into), NOT over an ingress HTTP hop — a synchronous HTTP call to the same
    single-loop endpoint from inside an async handler would deadlock the event
    loop. Reading the registry directly is both correct (same SSOT) and safe.

    Loads ALL of the bd09 tools (the load-all v0.1 seam behaviour — see the module
    docstring). ``task`` is accepted so the signature is the seam a future per-task
    retriever drops into; at v0.1 it is not used to scope (nothing to retrieve at
    ~5 tools). Returns the catalogue as ``ToolDescriptor``s carrying each tool's
    real input JSON schema (from the registry's Pydantic model), so the planner can
    fill ``args`` plausibly.
    """
    from agentinvest_tools.bd09_service import _REGISTRY

    return tuple(
        ToolDescriptor(
            so_id=spec.so_id,
            name=spec.name,
            summary=spec.summary,
            input_schema=_bd09_input_schema(spec),
        )
        for spec in _REGISTRY.values()
    )


def _bd09_input_schema(spec: Any) -> dict[str, Any]:
    """The tool's input JSON schema from its Pydantic input model (the registry SSOT)."""
    schema: dict[str, Any] = spec.input_model.model_json_schema()
    return schema


def load_tool_catalogue_from_bd12(
    task: str,  # noqa: ARG001 - the seam's task arg (a real retriever would scope on it)
) -> tuple[ToolDescriptor, ...]:
    """Load the BD-12 read candidate catalogue from the bd12 registry (the seam).

    The BD-12 book-of-record read tools (SD-12.1 IBOR + SD-12.2 ABOR), loaded the SAME way as
    ``load_tool_catalogue_from_bd09`` — in-process from the ``bd12`` ``_REGISTRY`` (the SSOT
    ``list_capabilities`` serves), NOT over an ingress HTTP hop (which would deadlock the
    single-loop
    endpoint from inside an async handler). Load-all (the v0.1 seam behaviour). Each descriptor
    carries the tool's abstract input schema (book / portfolio / as-of) so the planner can fill
    ``args`` plausibly. Additive to bd09 — the bd09 descriptors are untouched.
    """
    from agentinvest_tools.bd12_service import _REGISTRY

    return tuple(
        ToolDescriptor(
            so_id=spec.so_id,
            name=spec.name,
            summary=spec.summary,
            input_schema=spec.input_model.model_json_schema(),
        )
        for spec in _REGISTRY.values()
    )


def load_tool_catalogue_from_bd12_recon(
    task: str,  # noqa: ARG001 - the seam's task arg (a real retriever would scope on it)
) -> tuple[ToolDescriptor, ...]:
    """Load the SD-12.10 reconcile candidate catalogue from the bd12Recon registry (the seam).

    The BD-12 SD-12.10 reconcile tools (position · cash · transaction-matching · IBOR/ABOR,
    OIM-162),
    loaded the SAME way as the bd09 / bd12 catalogues — in-process from the ``bd12Recon``
    ``_REGISTRY`` (the SSOT ``list_capabilities`` serves), NOT over an ingress HTTP hop (which would
    deadlock the single-loop endpoint from inside an async handler). Load-all (the v0.1 seam
    behaviour). Each descriptor carries the tool's reconcile input schema (as_of / persist) so the
    planner can fill ``args`` plausibly. Additive to bd09 + bd12 — those descriptors are untouched.
    """
    from agentinvest_tools.bd12_recon_service import (
        _REGISTRY,
        PROPOSER_SO_ID,
        PROPOSER_SUMMARY,
        PROPOSER_TOOL_NAME,
        ProposeRequest,
    )

    reconcile_tools = tuple(
        ToolDescriptor(
            so_id=spec.so_id,
            name=spec.name,
            summary=spec.summary,
            input_schema=spec.input_model.model_json_schema(),
        )
        for spec in _REGISTRY.values()
    )
    # SO-12.10-05 — the propose-only cause-proposer (OIM-162 cycle-2), appended after the four
    # reconcile tools (additive; the reconcile descriptors are byte-unperturbed).
    proposer_tool = ToolDescriptor(
        so_id=PROPOSER_SO_ID,
        name=PROPOSER_TOOL_NAME,
        summary=PROPOSER_SUMMARY,
        input_schema=ProposeRequest.model_json_schema(),
    )
    return (*reconcile_tools, proposer_tool)


def load_tool_catalogue_from_entity_resolution(
    task: str,  # noqa: ARG001 - the seam's task arg (a real retriever would scope on it)
) -> tuple[ToolDescriptor, ...]:
    """Load the SD-13.2 resolution candidate catalogue from the entityResolution registry (the
    seam).

    The SD-13.2 entity-resolution tools (resolve_batch · get_golden_record · list_review_queue,
    OIM-199), loaded the SAME way as the bd09 / bd12 / bd12Recon catalogues — in-process from the
    ``entityResolution`` ``_REGISTRY`` (the SSOT ``list_capabilities`` serves), NOT over an ingress
    HTTP hop (which would deadlock the single-loop endpoint from inside an async handler). Load-all
    (the v0.1 seam behaviour). Each descriptor carries the tool's input schema so the planner can
    fill ``args`` plausibly. Additive to bd09 + bd12 + bd12Recon — those descriptors are untouched.
    """
    from agentinvest_tools.entity_resolution_service import _REGISTRY

    return tuple(
        ToolDescriptor(
            so_id=spec.so_id,
            name=spec.name,
            summary=spec.summary,
            input_schema=spec.input_model.model_json_schema(),
        )
        for spec in _REGISTRY.values()
    )


def load_tool_catalogue_from_services(
    task: str,
) -> tuple[ToolDescriptor, ...]:
    """The orchestrator-path catalogue across the registered per-BD read/compute services.

    Aggregates the BD-09 (performance) + BD-12 (book-of-record read) + BD-12 SD-12.10 (reconcile) +
    BD-13 SD-13.2 (entity resolution) catalogues the planner selects among — the load-all v0.1 seam
    over the services. The BD-09 descriptors come first, BYTE-FOR-BYTE as
    ``load_tool_catalogue_from_bd09`` produces them (so the W1 NAV-strike path that resolves the
    BD-09 / NAV tools is unperturbed), then the bd12 read tools, then the bd12Recon reconcile tools,
    then the entityResolution tools — each set *appended*, never interleaved into nor altering the
    earlier entries (additive). When the surface grows (OIM-120+), a real per-task retriever scopes
    HERE without changing the planner.
    """
    return (
        load_tool_catalogue_from_bd09(task)
        + load_tool_catalogue_from_bd12(task)
        + load_tool_catalogue_from_bd12_recon(task)
        + load_tool_catalogue_from_entity_resolution(task)
    )


def load_tool_catalogue_from_eval_tools(
    eval_tools: tuple[Any, ...],
) -> tuple[ToolDescriptor, ...]:
    """Build the candidate catalogue from an eval set's ``tools`` (the eval path).

    The eval path's catalogue source: the SAME candidate descriptors the OIM-105/
    106 baseline scored over (an ``EvalSet``'s ``ToolSpec``s, each with a
    ``tool_id`` / ``name`` / ``description``). Load-all (the whole set's catalogue
    is the candidate set for every case — apples-to-apples with the baseline, which
    also ranked over the whole set). No input schema (the eval tools are
    description-only golden tools, not the live bd09 tools).
    """
    return tuple(
        ToolDescriptor(
            so_id=t.tool_id,
            name=t.name,
            summary=t.description,
            input_schema=None,
        )
        for t in eval_tools
    )
