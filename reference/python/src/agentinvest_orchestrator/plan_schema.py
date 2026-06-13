"""``PlanSchema`` — the structured, validated output of the ``.plan()`` loop.

The planner's contract: a task plus a candidate tool catalogue in, a
``PlanSchema``-validated plan out. The plan is a list of ``steps`` (each naming
the ``soId`` of a catalogue tool plus its ``args``) and a ``riskScore`` (a float
for the future high-stakes approval gate — declared here, **not exercised** yet).

This is the SSOT for the plan shape. The Python ``agentinvestPlanner`` validates the
model's response against it; the TS orchestrator parses the returned plan against
a thin zod mirror (the service stays the schema authority, the orchestrator does a
defensive parse). Adding a field is one row here.

``extra="forbid"`` on every model: the structured-output call is constrained to
this schema, so a response carrying an unexpected key is a **deterministic**
schema failure (a bad plan the planner must reject as a typed error, never pass
through silently) — which the handler classifies as terminal (no retry storm).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PlanStep(BaseModel):
    """One step of a plan — a named tool to call plus its arguments.

    ``soId`` is the Service-Operation identifier of a tool in the candidate
    catalogue the planner was given (e.g. ``"SO-09-01"`` or, in the eval path, a
    catalogue ``tool_id`` such as ``"SO-09-01-twr"``). ``args`` is the tool's
    input as a plain object — it is NOT validated against the tool's own input
    model here (that is the dispatch step's job); at the planning step a
    step is a *tool-selection + argument-intent* claim, not a checked tool call.
    ``rationale`` is the planner's short justification for choosing this tool —
    optional, captured for the audit trail and the future approval gate.
    """

    model_config = ConfigDict(extra="forbid")

    soId: str = Field(
        description="The Service-Operation id of the catalogue tool this step calls.",
    )
    args: dict[str, object] = Field(
        default_factory=dict,
        description="The tool's arguments as a JSON object (validated at dispatch, not here).",
    )
    rationale: str | None = Field(
        default=None,
        description="Short justification for selecting this tool (for the audit trail).",
    )


class PlanSchema(BaseModel):
    """A validated plan — the structured output of the one ``.plan()`` loop.

    ``steps`` is the ordered list of tool calls the planner proposes for the task
    (at least one). ``riskScore`` is a float in [0, 1] flagging how high-stakes the
    plan is, for the future approval gate — it is **declared, not exercised** yet
    (nothing reads it to gate anything yet). ``summary``
    is a one-line natural-language description of the plan, captured for the audit
    trail and the operator surface.

    The plan is **generated, not executed**: a ``PlanSchema``-valid instance is a
    structure + tool-selection claim, not an outcome.
    """

    model_config = ConfigDict(extra="forbid")

    steps: list[PlanStep] = Field(
        min_length=1,
        description="The ordered tool-call steps the planner proposes (at least one).",
    )
    riskScore: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "How high-stakes the plan is, in [0,1], for the future approval gate. "
            "Declared here; NOT exercised yet."
        ),
    )
    summary: str | None = Field(
        default=None,
        description="One-line natural-language description of the plan (audit trail).",
    )

    def selected_so_ids(self) -> tuple[str, ...]:
        """The ordered ``soId``s the plan selects — the record-then-score key.

        The eval's record-then-score adapter records ``selected_so_ids()[0]`` (the
        plan's primary tool selection) as the per-query transcript entry, scored
        through the existing harness ``Selector`` contract.
        """
        return tuple(step.soId for step in self.steps)
