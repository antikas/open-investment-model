"""The ``agentinvestPlanner`` handler — error classification mapped onto Restate semantics.

The handler maps the planner's typed error pair onto Restate's retry semantics:

- ``PlannerDeterministicError`` -> a Restate ``TerminalError`` (Restate does NOT
  retry it — no retry storm on a deterministic bad plan / missing key / 4xx);
- ``PlannerTransientError`` -> a plain ``RuntimeError`` (Restate DOES retry it,
  bounded — a transient 429/529/timeout must not be made permanent).

The SDK turns a ``TerminalError`` escaping a handler into a terminal failure and
any *other* escaping exception into a *retried* transient failure. So "deterministic
is terminal / transient is retried" is exactly "a deterministic failure escapes as
a ``TerminalError`` and a transient one escapes as a plain exception" — asserted
directly here (offline; the planner is monkeypatched, no live call).
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from restate.exceptions import TerminalError

from agentinvest_orchestrator import service as svc
from agentinvest_orchestrator.plan_schema import PlanSchema
from agentinvest_orchestrator.planner import (
    PlannerDeterministicError,
    PlannerTransientError,
)
from agentinvest_orchestrator.service import (
    PLANNER_SERVICE_NAME,
    CandidateTool,
    PlanTaskInput,
    plan_task_handler,
)


class _FakeContext:
    """A minimal stand-in for ``restate.Context`` (the handler uses no ctx methods)."""


_CATALOGUE = [
    CandidateTool(soId="SO-09-02", name="compute_time_weighted_return", summary="TWR."),
    CandidateTool(soId="SO-09-03", name="compute_money_weighted_return", summary="MWR."),
]


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def test_service_name_is_agentinvest_scoped() -> None:
    # agentINVEST-scoped (the bd09 / pyTools discipline) so it does not collide
    # with a same-named sibling-project service on the shared dev Restate.
    assert PLANNER_SERVICE_NAME == "agentinvestPlanner"


def test_happy_path_returns_validated_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_plan(task: str, descriptors: Any, *args: Any) -> PlanSchema:
        return PlanSchema.model_validate(
            {"steps": [{"soId": "SO-09-02", "args": {}}], "riskScore": 0.1, "summary": "ok"}
        )

    monkeypatch.setattr(svc, "plan_task", fake_plan)
    req = PlanTaskInput(task="compute twr", catalogue=_CATALOGUE)
    out = _run(plan_task_handler(_FakeContext(), req))  # type: ignore[arg-type]
    assert out["steps"][0]["soId"] == "SO-09-02"
    assert out["riskScore"] == 0.1


def test_deterministic_error_becomes_terminalerror(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_plan(task: str, descriptors: Any, *args: Any) -> PlanSchema:
        raise PlannerDeterministicError("malformed plan")

    monkeypatch.setattr(svc, "plan_task", fake_plan)
    req = PlanTaskInput(task="x", catalogue=_CATALOGUE)
    with pytest.raises(TerminalError):
        _run(plan_task_handler(_FakeContext(), req))  # type: ignore[arg-type]


def test_transient_error_is_NOT_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_plan(task: str, descriptors: Any, *args: Any) -> PlanSchema:
        raise PlannerTransientError("429 rate limit")

    monkeypatch.setattr(svc, "plan_task", fake_plan)
    req = PlanTaskInput(task="x", catalogue=_CATALOGUE)
    # A transient fault escapes as a plain exception (NOT a TerminalError) so
    # Restate retries it (bounded) — never terminalised.
    with pytest.raises(Exception) as exc_info:
        _run(plan_task_handler(_FakeContext(), req))  # type: ignore[arg-type]
    assert not isinstance(exc_info.value, TerminalError)
