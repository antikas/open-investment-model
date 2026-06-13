"""The ``.plan()`` planner — schema, the ten BD-09 tasks, error classification.

These tests are **offline + deterministic** (CI-safe): they inject a FAKE Anthropic
client so no live model call is made. The LIVE Sonnet 4.6 call is proven separately
(the record-then-score run + the crash-replay proof).
What these tests prove:

- **PlanSchema** validates a well-formed plan and rejects a malformed one;
- **the ten BD-09 tasks** each produce a ``PlanSchema``-valid plan through the
  planner (with the fake client returning a schema-valid plan), so the planner's
  parse-and-validate path is exercised over ten realistic tasks (the LIVE plans
  are journaled through the production VO + recorded in the transcripts);
- **error classification** — a malformed / schema-invalid response, a missing
  ``emit_plan`` tool-use, an empty task/catalogue → ``PlannerDeterministicError``
  (terminal); a 429 / 529 / timeout SDK fault → ``PlannerTransientError``
  (retryable). The deterministic path does NOT classify as transient (no retry
  storm); the transient path is NOT terminalised.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from agentinvest_orchestrator.plan_schema import PlanSchema
from agentinvest_orchestrator.planner import (
    PlannerDeterministicError,
    PlannerTransientError,
    ToolDescriptor,
    _raise_classified,
    plan_task,
)

# The BD-09 candidate catalogue (the 5 SD-09.1 return tools) the planner selects over.
_BD09_CATALOGUE: tuple[ToolDescriptor, ...] = (
    ToolDescriptor(
        "SO-09-01", "compute_total_return", "Total return over a window (Modified Dietz)."
    ),
    ToolDescriptor(
        "SO-09-02", "compute_time_weighted_return", "Time-weighted return (linked sub-periods)."
    ),
    ToolDescriptor(
        "SO-09-03", "compute_money_weighted_return", "Money-weighted return (IRR of cash flows)."
    ),
    ToolDescriptor(
        "SO-09-04", "compute_benchmark_relative_return", "Active/excess return (port minus bm)."
    ),
    ToolDescriptor(
        "SO-09-05", "compute_contribution_breakdown", "Segment contributions summing to the total."
    ),
)

# Ten realistic BD-09 analyst tasks. Each maps to a plausible SD-09.1 tool; the
# fake client returns a schema-valid plan so the planner's validate path runs.
# (The LIVE plans for these classes of task are journaled through the production
# VO + recorded in the transcripts.)
TEN_BD09_TASKS: tuple[tuple[str, str], ...] = (
    ("Compute the time-weighted return for fund X over Q1.", "SO-09-02"),
    ("What is the money-weighted (IRR) return for the LP's commitment to fund Y?", "SO-09-03"),
    ("Give me fund Z's total return over the calendar year.", "SO-09-01"),
    ("Break down fund A's return by sector so the contributions sum to the total.", "SO-09-05"),
    ("How did the portfolio do against its benchmark this quarter (active return)?", "SO-09-04"),
    ("I need the manager-skill return that strips out client cash-flow timing.", "SO-09-02"),
    ("What is the investor's actual experienced return given the dated cash flows?", "SO-09-03"),
    ("Show the excess return over the index, geometrically linked.", "SO-09-04"),
    ("Compute the Modified Dietz total return with day-weighted external flows.", "SO-09-01"),
    ("Which segments drove the portfolio's return this period and by how much?", "SO-09-05"),
)


class _FakeBlock:
    def __init__(self, type_: str, name: str | None, input_: Any) -> None:
        self.type = type_
        self.name = name
        self.input = input_


class _FakeResponse:
    def __init__(self, content: list[Any], stop_reason: str = "tool_use") -> None:
        self.content = content
        self.stop_reason = stop_reason


class _FakeMessages:
    def __init__(self, plan_for: Any) -> None:
        self._plan_for = plan_for

    def create(self, **kwargs: Any) -> _FakeResponse:
        # Return a single emit_plan tool-use whose input is a PlanSchema-shaped dict.
        prompt = kwargs["messages"][0]["content"]
        plan_dict = self._plan_for(prompt)
        return _FakeResponse([_FakeBlock("tool_use", "emit_plan", plan_dict)])


class _FakeClient:
    """A fake Anthropic client returning a configurable plan (no network)."""

    def __init__(self, plan_for: Any) -> None:
        self.messages = _FakeMessages(plan_for)


def _plan_choosing(so_id: str) -> dict[str, Any]:
    return {
        "steps": [{"soId": so_id, "args": {}, "rationale": "selected for the task"}],
        "riskScore": 0.1,
        "summary": "a plan",
    }


def test_plan_schema_validates_and_rejects() -> None:
    ok = PlanSchema.model_validate(_plan_choosing("SO-09-02"))
    assert ok.selected_so_ids() == ("SO-09-02",)
    # min_length on steps:
    with pytest.raises(ValidationError):
        PlanSchema.model_validate({"steps": [], "riskScore": 0.1})
    # riskScore range:
    with pytest.raises(ValidationError):
        PlanSchema.model_validate({"steps": [{"soId": "x"}], "riskScore": 2.0})
    # extra forbidden:
    with pytest.raises(ValidationError):
        PlanSchema.model_validate({"steps": [{"soId": "x"}], "riskScore": 0.1, "nope": 1})


@pytest.mark.parametrize("task,expected_so", TEN_BD09_TASKS)
def test_ten_bd09_tasks_produce_valid_plans(task: str, expected_so: str) -> None:
    """Each of the ten BD-09 tasks produces a PlanSchema-valid plan (offline)."""
    client = _FakeClient(lambda _prompt: _plan_choosing(expected_so))
    plan = plan_task(task, _BD09_CATALOGUE, client=client)
    assert isinstance(plan, PlanSchema)
    assert plan.steps[0].soId == expected_so
    assert 0.0 <= plan.riskScore <= 1.0


def test_ten_tasks_count() -> None:
    assert len(TEN_BD09_TASKS) == 10


def test_deterministic_error_empty_task() -> None:
    with pytest.raises(PlannerDeterministicError):
        plan_task("   ", _BD09_CATALOGUE, client=_FakeClient(lambda _p: _plan_choosing("SO-09-01")))


def test_deterministic_error_empty_catalogue() -> None:
    with pytest.raises(PlannerDeterministicError):
        plan_task("a task", (), client=_FakeClient(lambda _p: _plan_choosing("SO-09-01")))


def test_deterministic_error_missing_emit_plan_tool() -> None:
    # The model returned text, not the emit_plan tool-use → deterministic.
    bad = _FakeClient(lambda _p: _plan_choosing("SO-09-01"))
    bad.messages = _FakeMessages(lambda _p: _plan_choosing("SO-09-01"))

    class _NoToolMessages:
        def create(self, **_kwargs: Any) -> _FakeResponse:
            return _FakeResponse([_FakeBlock("text", None, None)], stop_reason="end_turn")

    bad.messages = _NoToolMessages()  # type: ignore[assignment]
    with pytest.raises(PlannerDeterministicError):
        plan_task("a task", _BD09_CATALOGUE, client=bad)


def test_deterministic_error_schema_invalid_response() -> None:
    # The model emitted emit_plan but with a schema-invalid input → deterministic.
    bad = _FakeClient(lambda _p: {"steps": [], "riskScore": 5.0})  # empty steps + bad risk
    with pytest.raises(PlannerDeterministicError):
        plan_task("a task", _BD09_CATALOGUE, client=bad)


# --- Error classification of SDK faults (the deterministic/transient split) ---


class _FakeRateLimit(Exception):
    pass


class _FakeBadRequest(Exception):
    pass


def test_classify_transient_by_name() -> None:
    exc = type("RateLimitError", (Exception,), {})()
    with pytest.raises(PlannerTransientError):
        _raise_classified(exc)


def test_classify_transient_by_status() -> None:
    exc = _FakeRateLimit()
    exc.status_code = 429  # type: ignore[attr-defined]
    with pytest.raises(PlannerTransientError):
        _raise_classified(exc)


def test_classify_overloaded_529_transient() -> None:
    exc = _FakeRateLimit()
    exc.status_code = 529  # type: ignore[attr-defined]
    with pytest.raises(PlannerTransientError):
        _raise_classified(exc)


def test_classify_deterministic_bad_request() -> None:
    exc = _FakeBadRequest()
    exc.status_code = 400  # type: ignore[attr-defined]
    with pytest.raises(PlannerDeterministicError):
        _raise_classified(exc)


def test_classify_deterministic_auth() -> None:
    exc = _FakeBadRequest()
    exc.status_code = 401  # type: ignore[attr-defined]
    with pytest.raises(PlannerDeterministicError):
        _raise_classified(exc)


def test_classify_unknown_defaults_deterministic() -> None:
    # An unrecognised error is treated deterministic (terminal) — the safe default
    # for a fiduciary substrate (never retry-storm an unknown).
    exc = type("WeirdError", (Exception,), {})()
    with pytest.raises(PlannerDeterministicError):
        _raise_classified(exc)
