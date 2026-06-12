"""agentINVEST orchestrator-side services — the ``agentinvestPlanner`` planner (OIM-130).

This package hosts the **single reasoning loop** of agentINVEST: the planning
step (``.plan()``). It is a *model-free Restate service* (``agentinvestPlanner``,
sibling on the service axis to the ``bd09`` tool-hosting service in
``agentinvest_tools``) whose one handler — ``planTask`` — takes an analyst task
plus a candidate **tool catalogue** and returns a **schema-validated plan**
(``PlanSchema``) by making one real Anthropic call.

Vocabulary (load-bearing, ADR-0054). ``agentinvestPlanner`` is a **service**, not
an "agent": it is the hosting/dispatch boundary the orchestrator's one loop runs in.
The Service Operations it plans over are **tools** in a typed **tool catalogue**.
``planTask`` is **the** single reasoning loop — there is no fleet, no per-domain
agent, no second loop. The plan it returns is **generated, not executed**:
dispatch (running the plan's steps) is a separate, later step (OIM-131). A valid
plan is a *structure + tool-selection* claim, not an outcome.

Honest boundary (ADR-0054 v0.1 frontier-only):

- **Frontier-only.** One frontier model (Anthropic Sonnet 4.6) drives the loop.
  No fine-tuning, no specialist fleet, no office-split. The office-split is the
  *eval-gated upgrade* IF the cross-office tool-selection eval degrades — it is
  NOT built here.
- **Generated, not executed.** ``planTask`` returns a plan; it does not run it.
- **Non-deterministic.** The model is non-deterministic, so a "valid plan" is a
  *structural* claim (``PlanSchema``-valid, journaled exactly once by the
  orchestrator's call semantics). The *quantified* tool-selection claim is the
  eval number (the record-then-score harness in ``agentinvest_evals``).
- **Supervised-autonomous on synthetic data.** Not a production planner.
- **The tool-RAG seam is not yet real retrieval.** With ~5 BD-09 tools,
  ``load_tool_catalogue`` is a *seam* (the place a ~900-tool dynamic-scoping
  retriever plugs in), not exercised large-catalogue retrieval. See its docstring.
"""

from __future__ import annotations

from agentinvest_orchestrator.plan_schema import PlanSchema, PlanStep

__all__ = ["PlanSchema", "PlanStep"]
