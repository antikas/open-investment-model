"""The ``agentinvestPlanner`` ``planTask`` HANDLER — the WIRE path the orchestrator reaches.

These tests drive the ``planTask`` HANDLER through a faithful fake ``restate.Context`` — the same
service boundary the ``investmentOperation`` virtual object invokes at seam 1 via
``ctx.serviceClient(agentinvestPlanner).planTask(...)``. The load-bearing property: the
unknown-key reject is a clean ``TerminalError`` (400), matching the five other registered
request handlers (navData ×2, argResolver, pyTools, bd09.execute_so) rather than the status-less
500 the SDK default serde produced.

The request contract ``PlanTaskInput`` already carried ``extra="forbid"``, so an off-contract key
was already rejected — but via the SDK default serde, so the ``ValidationError`` raised inside the
SDK deserialise was re-wrapped as a status-less HTTP 500. The handler now uses a permissive
``_PassThroughJsonSerde`` + an in-handler ``_coerce_request``, so the reject is a clean 400.

Honest boundary: a STATUS-CONSISTENCY cleanup — the planner already failed loud on an unknown key;
this upgrades its status-less 500 to an actionable 400. No fiduciary number changes; no silent-drop
existed here. The valid path and the planner's own deterministic (422) / transient (retry)
classification are unchanged.

No live model call is made: the catalogue path is driven with ``plan_task`` monkeypatched (the same
offline discipline as ``test_planner.py``'s ``_FakeClient``).
"""

from __future__ import annotations

import asyncio
from typing import Any, cast

import pytest
import restate
from restate.exceptions import TerminalError

from agentinvest_orchestrator import service as planner_service
from agentinvest_orchestrator.plan_schema import PlanSchema
from agentinvest_orchestrator.planner import PlannerDeterministicError
from agentinvest_orchestrator.service import (
    PlanTaskInput,
    _coerce_request,
    plan_task_handler,
)
from agentinvest_tools.request_serde import PassThroughJsonSerde


class FakeContext:
    """A faithful stand-in for ``restate.Context``: ``run(name, action)`` invokes the action and
    propagates its value/exception unchanged — the same seam the orchestrator reaches."""

    def __init__(self) -> None:
        self.steps: list[str] = []

    async def run(self, name: str, action: Any, *args: Any, **kwargs: Any) -> Any:
        self.steps.append(name)
        result = action()
        if asyncio.iscoroutine(result):
            result = await result
        return result


def _plan(ctx: FakeContext, req: Any) -> Any:
    """Drive the ``planTask`` HANDLER (the wire path) — not a helper function."""
    return asyncio.run(plan_task_handler(cast(restate.Context, ctx), req))


# A schema-valid plan the monkeypatched ``plan_task`` returns (no model call).
_VALID_PLAN: dict[str, Any] = {
    "steps": [{"soId": "SO-09-02", "args": {}, "rationale": "selected for the task"}],
    "riskScore": 0.1,
    "summary": "a plan",
}

# A request whose catalogue is non-empty so the handler takes the in-request catalogue
# path (no ``load_tool_catalogue_from_bd09``, no bd09 dependency) — the planner is
# monkeypatched, so no live model call is made.
_VALID_REQUEST: dict[str, Any] = {
    "task": "Compute the time-weighted return for fund X over Q1.",
    "catalogue": [
        {
            "soId": "SO-09-02",
            "name": "compute_time_weighted_return",
            "summary": "Time-weighted return (linked sub-periods).",
        }
    ],
}


def _stub_plan_task_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    """Monkeypatch ``service.plan_task`` to return a schema-valid plan (no network)."""

    def _fake_plan_task(task: str, descriptors: Any, *args: Any) -> PlanSchema:
        return PlanSchema.model_validate(_VALID_PLAN)

    monkeypatch.setattr(planner_service, "plan_task", _fake_plan_task)


def test_valid_request_plans_on_the_wire(monkeypatch: pytest.MonkeyPatch) -> None:
    """A valid request through the HANDLER plans (valid contract keys still work)."""
    _stub_plan_task_ok(monkeypatch)
    out = _plan(FakeContext(), _VALID_REQUEST)
    assert out["steps"][0]["soId"] == "SO-09-02"
    assert out["riskScore"] == pytest.approx(0.1)


def test_unknown_key_is_terminal_400_on_the_wire(monkeypatch: pytest.MonkeyPatch) -> None:
    """An off-contract key on planTask → TerminalError(400) on the wire, not a status-less 500.

    The status-consistency fix: the SDK default serde re-wrapped the ``extra="forbid"``
    ``ValidationError`` as a 500; the pass-through serde + in-handler validation makes it a clean
    400, matching the five other registered request handlers.
    """
    _stub_plan_task_ok(monkeypatch)
    with pytest.raises(TerminalError) as excinfo:
        _plan(FakeContext(), {"task": "x", "bogus": 1})
    assert getattr(excinfo.value, "status_code", None) == 400
    assert "invalid request" in str(excinfo.value).lower()


def test_non_dict_body_is_terminal_400_on_the_wire(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-object body to the handler → a clean terminal 400, never a 500."""
    _stub_plan_task_ok(monkeypatch)
    with pytest.raises(TerminalError) as excinfo:
        _plan(FakeContext(), [1, 2, 3])
    assert getattr(excinfo.value, "status_code", None) == 400


def test_string_body_is_terminal_400_on_the_wire(monkeypatch: pytest.MonkeyPatch) -> None:
    """A bare string body (a valid JSON scalar) → a clean terminal 400, never a 500."""
    _stub_plan_task_ok(monkeypatch)
    with pytest.raises(TerminalError) as excinfo:
        _plan(FakeContext(), "just a string")
    assert getattr(excinfo.value, "status_code", None) == 400


def test_null_body_coerces_to_empty_then_400(monkeypatch: pytest.MonkeyPatch) -> None:
    """A null body → ``model_validate`` over an empty/missing-required dict → a clean 400.

    The serde maps an empty buffer to ``{}``; a ``None`` payload is a non-dict and is the
    explicit non-object 400 branch. Either way an off-contract/empty body is a clean 400, never a
    500. (Here ``None`` exercises the non-dict guard.)
    """
    _stub_plan_task_ok(monkeypatch)
    with pytest.raises(TerminalError) as excinfo:
        _plan(FakeContext(), None)
    assert getattr(excinfo.value, "status_code", None) == 400


@pytest.mark.parametrize("body", [b"{bad", b'{"x":', b'"unterminated', b"\xff\xfe", b"\x80\x81"])
def test_malformed_or_non_utf8_body_is_terminal_400_on_the_wire(
    monkeypatch: pytest.MonkeyPatch, body: bytes
) -> None:
    """A malformed-JSON / non-UTF8 transport body to planTask → clean 400, never a 500/uncaught.

    Drives the FULL wire path — the shared ``PassThroughJsonSerde.deserialize`` over the raw bytes
    (must NOT raise) then the REAL handler over its result (a non-dict ``str`` → clean 400).
    """
    _stub_plan_task_ok(monkeypatch)
    deserialised = PassThroughJsonSerde().deserialize(body)  # must NOT raise
    with pytest.raises(TerminalError) as excinfo:
        _plan(FakeContext(), deserialised)
    assert getattr(excinfo.value, "status_code", None) == 400


# --- DEEP-NEST BODY → CLEAN 400 (the never-raise invariant is structural) --------------------
#
# A deeply-nested JSON body makes ``json.loads`` raise ``RecursionError`` (a ``RuntimeError``
# subclass, NOT a ``ValueError``) — an enumerated ``except`` tuple would not catch it (→ a
# status-less 500). Catching the WHOLE parse-failure class (``except Exception``) →
# the serde returns the raw text as a non-dict ``str`` the handler 400s. REVERT-SENSITIVE.

# A few-KB craftable payload: 20000 levels of nesting, well past the C scanner's depth budget.
DEEP_NEST_BODY = b"[" * 20000 + b"]" * 20000


def test_deep_nest_body_is_terminal_400_on_the_wire(monkeypatch: pytest.MonkeyPatch) -> None:
    """planTask: a deeply-nested JSON body → a clean 400, never a status-less 500."""
    _stub_plan_task_ok(monkeypatch)
    deserialised = PassThroughJsonSerde().deserialize(DEEP_NEST_BODY)  # must NOT raise
    with pytest.raises(TerminalError) as excinfo:
        _plan(FakeContext(), deserialised)
    assert getattr(excinfo.value, "status_code", None) == 400


def test_serde_never_raises_on_deep_nest_body() -> None:
    """The structural never-raise invariant: a deep-nest body that trips ``RecursionError`` inside
    ``json.loads`` does NOT escape ``deserialize`` — it returns a (str) value. Revert-sensitive."""
    out = PassThroughJsonSerde().deserialize(DEEP_NEST_BODY)  # must NOT raise (was RecursionError)
    assert isinstance(out, str)


def test_deterministic_failure_stays_422_unregressed(monkeypatch: pytest.MonkeyPatch) -> None:
    """A ``PlannerDeterministicError`` still surfaces as ``TerminalError(422)``, NOT downgraded.

    The request-shape guard (400) must not swallow or downgrade the planner's own deterministic
    classification (422). A valid request whose planner raises ``PlannerDeterministicError`` is a
    terminal 422.
    """

    def _fake_plan_task_raises(task: str, descriptors: Any, *args: Any) -> PlanSchema:
        raise PlannerDeterministicError("schema-invalid plan")

    monkeypatch.setattr(planner_service, "plan_task", _fake_plan_task_raises)
    with pytest.raises(TerminalError) as excinfo:
        _plan(FakeContext(), _VALID_REQUEST)
    assert getattr(excinfo.value, "status_code", None) == 422


def test_coerce_request_passes_valid_body_through() -> None:
    """``_coerce_request`` returns a faithful ``PlanTaskInput`` for the valid contract keys."""
    out = _coerce_request(_VALID_REQUEST)
    assert isinstance(out, PlanTaskInput)
    assert out.task == _VALID_REQUEST["task"]
    assert out.catalogue[0].soId == "SO-09-02"


def test_coerce_request_idempotent_on_typed_input() -> None:
    """An already-built ``PlanTaskInput`` passes through ``_coerce_request`` unchanged."""
    typed = PlanTaskInput.model_validate(_VALID_REQUEST)
    assert _coerce_request(typed) is typed
