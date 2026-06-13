"""The ``argResolver`` service — unit + live-marts tests for the resolve step.

The resolver is the abstract-arg → concrete-tool-input seam: given a fund + a window it READS the
marts and DERIVES the SO-09-01 / SO-09-05 concrete inputs by REUSING the demo's derivation. These
tests pin:

- the REUSE — the resolver imports and uses the demo's ``_total_return_args`` /
  ``_breakdown_args`` (the same derivation, not a re-implementation);
- the v0.1 BOUND — an unresolvable tool (anything but SO-09-01/05) is a clean terminal failure
  (no marts read needed);
- the LIVE resolution — over the built marts, the resolved SO-09-01 args carry the fund begin/end
  NAV and the SO-09-05 args carry per-segment weights summing to ~1 (skip-guarded when the marts
  are not built, mirroring the phase2 integration test).

The handler itself wraps the derivation in ``ctx.run``; these tests exercise the derivation the
handler calls (``read_fund_window`` + the demo's arg builders) so they run without a live Restate
context, the same way the bd09/nav unit tests exercise the compute behind the handler.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any, cast

import pytest
import restate
from restate.exceptions import TerminalError

from agentinvest_demo.marts import (
    DEFAULT_BEGIN_DATE,
    DEFAULT_END_DATE,
    DEFAULT_FUND_ID,
    MartsUnavailableError,
    list_funds,
    read_fund_window,
)
from agentinvest_demo.phase2_demo import _breakdown_args, _total_return_args
from agentinvest_tools.arg_resolver_service import _RESOLVABLE_SO_IDS, resolve_step_args
from agentinvest_tools.request_serde import PassThroughJsonSerde


class FakeContext:
    """A faithful stand-in for ``restate.Context``: ``run(name, action)`` invokes the action and
    propagates its value/exception unchanged — the SAME seam the orchestrator reaches over the
    ingress (a ``TerminalError`` escaping ``ctx.run`` is terminal/no-retry)."""

    def __init__(self) -> None:
        self.steps: list[str] = []

    async def run(self, name: str, action: Any, *args: Any, **kwargs: Any) -> Any:
        self.steps.append(name)
        result = action()
        if asyncio.iscoroutine(result):
            result = await result
        return result


def _resolve(ctx: FakeContext, req: Any) -> Any:
    """Drive the ``resolveStepArgs`` HANDLER (the wire path) — not the derivation function."""
    return asyncio.run(resolve_step_args(cast(restate.Context, ctx), req))


def _marts_readable() -> bool:
    try:
        list_funds()
        return True
    except MartsUnavailableError:
        return False


live_marts = pytest.mark.skipif(
    not _marts_readable(),
    reason="canonical marts not readable (install the dbt group + run pnpm dbt:build)",
)


def test_v01_bound_names_only_the_bd09_return_tools() -> None:
    """The v0.1 resolver is honestly bounded to the demo's two BD-09 return tools."""
    assert _RESOLVABLE_SO_IDS == ("SO-09-01", "SO-09-05")
    # NOT the other BD-09 tools — those surface as a clean "cannot resolve" failure (a general
    # resolver for the full catalogue is forward, not silently guessed).
    assert "SO-09-02" not in _RESOLVABLE_SO_IDS
    assert "SO-09-03" not in _RESOLVABLE_SO_IDS


@live_marts
def test_resolves_so_09_01_to_concrete_begin_end_nav() -> None:
    """REUSE: the SO-09-01 resolution IS the demo's derivation (begin/end NAV + period + flows)."""
    data = read_fund_window(
        fund_id=DEFAULT_FUND_ID, begin_date=DEFAULT_BEGIN_DATE, end_date=DEFAULT_END_DATE
    )
    args = _total_return_args(data)
    # Concrete inputs the dispatch step passes to bd09.execute_so(SO-09-01) — the marts-derived NAV.
    assert args["beginning_value"] == str(data.begin_nav)
    assert args["ending_value"] == str(data.end_nav)
    assert args["period_days"] == data.period_days
    assert args["cash_flows"] == []  # the no-external-flow path (the synthetic seed carries none)
    # The end NAV reconciles to the published fund-NAV mart (the published-mart cross-check).
    assert data.end_nav == data.mart_fund_nav


@live_marts
def test_resolves_so_09_05_to_per_segment_weights_summing_to_one() -> None:
    """REUSE: the SO-09-05 resolution IS the demo's derivation (per-segment weights + returns)."""
    data = read_fund_window(
        fund_id=DEFAULT_FUND_ID, begin_date=DEFAULT_BEGIN_DATE, end_date=DEFAULT_END_DATE
    )
    args = _breakdown_args(data)
    segments = args["segments"]
    assert isinstance(segments, list)
    assert len(segments) >= 1
    # The weights partition the fund — they sum to ~1 (the SO-09-05 contract's invariant), so the
    # resolved args are a valid contribution-breakdown input.
    weight_sum = sum(Decimal(str(s["weight"])) for s in segments)
    assert abs(weight_sum - Decimal(1)) < Decimal("0.0001")
    # Each segment carries its own window return — the marts-derived concrete input.
    for s in segments:
        assert "segment" in s
        assert "segment_return" in s


@live_marts
def test_resolution_reconciles_total_return_to_contribution_sum() -> None:
    """The coherence invariant holds on the RESOLVED args — contributions sum to the total.

    This is the property the aggregate (seam 4) reuses: the SO-09-01 total return equals the sum
    of the SO-09-05 per-segment contributions (weight x return), because both resolved-arg sets
    derive from one underlying per-segment NAV-delta derivation (the resolver's single
    ``read_fund_window``).
    """
    data = read_fund_window(
        fund_id=DEFAULT_FUND_ID, begin_date=DEFAULT_BEGIN_DATE, end_date=DEFAULT_END_DATE
    )
    total_return = (data.end_nav - data.begin_nav) / data.begin_nav
    contribution_sum = sum(seg.weight * seg.segment_return for seg in data.segments)
    assert abs(contribution_sum - total_return) < Decimal("0.000000001")


# --- THE REJECT-UNKNOWN-KEYS HARDENING — proven ON THE WIRE ----------------------------------
#
# The same fiduciary-surface input-validation hardening as navData: ``ResolveStepArgsRequest`` was
# a bare TypedDict, so an off-contract key was silently ignored — a step resolved over a
# wrong/default window under a mis-keyed request. It is now a Pydantic model with ``extra="forbid"``,
# validated IN THE HANDLER BODY, so an unrecognised key is a clean TerminalError (400) on the wire.
# These tests drive the HANDLER (NOT the bare derivation function — a bare function would not carry
# the handler's validation), and need NO store: both the guard AND the v0.1-bound / missing-fund
# refusals run before the marts read.


def test_resolve_unknown_key_is_terminal_400_on_the_wire() -> None:
    """An off-contract key on resolveStepArgs → TerminalError(400) on the wire, before the read.

    A mis-keyed abstract arg (e.g. snake_case ``begin_date`` instead of the contract ``beginDate``)
    used to be silently ignored — the step resolved over the DEFAULT window. It now fails loud.
    """
    with pytest.raises(TerminalError) as excinfo:
        _resolve(
            FakeContext(),
            {"soId": "SO-09-01", "fundId": "PF-0001", "begin_date": "2020-01-01"},  # off-contract
        )
    assert getattr(excinfo.value, "status_code", None) == 400
    assert "invalid request" in str(excinfo.value).lower()


def test_resolve_arbitrary_unknown_key_is_terminal_400_on_the_wire() -> None:
    """Any unrecognised key is a clean terminal 400 on the wire (the reject-unknown-keys guard)."""
    with pytest.raises(TerminalError) as excinfo:
        _resolve(FakeContext(), {"soId": "SO-09-01", "fundId": "PF-0001", "bogus": 1})
    assert getattr(excinfo.value, "status_code", None) == 400


def test_resolve_non_dict_body_is_terminal_400_on_the_wire() -> None:
    """A non-object body to the handler → a clean terminal 400, never a 500."""
    with pytest.raises(TerminalError) as excinfo:
        _resolve(FakeContext(), "not-an-object")
    assert getattr(excinfo.value, "status_code", None) == 400


# --- MALFORMED-BODY → CLEAN 400 (the serde never raises) -------------------------------------
#
# Drive the FULL wire path — the shared ``PassThroughJsonSerde.deserialize`` over the raw bytes
# (must NOT raise) then the REAL handler over its result. A malformed-JSON / non-UTF8 transport body
# → a clean ``TerminalError(400)``, never a status-less 500 / uncaught decode error.


@pytest.mark.parametrize("body", [b"{bad", b'{"x":', b'"unterminated', b"\xff\xfe", b"\x80\x81"])
def test_resolve_malformed_or_non_utf8_body_is_terminal_400(body: bytes) -> None:
    """resolveStepArgs: a malformed-JSON / non-UTF8 body → a clean 400, never a 500."""
    deserialised = PassThroughJsonSerde().deserialize(body)  # must NOT raise
    with pytest.raises(TerminalError) as excinfo:
        _resolve(FakeContext(), deserialised)
    assert getattr(excinfo.value, "status_code", None) == 400


# --- DEEP-NEST BODY → CLEAN 400 (the never-raise invariant is structural) --------------------
#
# A deeply-nested JSON body makes ``json.loads`` raise ``RecursionError`` (a ``RuntimeError``
# subclass, NOT a ``ValueError``) — an enumerated ``except`` tuple would NOT catch it (→ a
# status-less 500). Catching the WHOLE parse-failure class (``except Exception``) → the serde
# returns the raw text as a non-dict ``str`` the handler 400s. REVERT-SENSITIVE.

# A few-KB craftable payload: 20000 levels of nesting, well past the C scanner's depth budget.
DEEP_NEST_BODY = b"[" * 20000 + b"]" * 20000


def test_resolve_deep_nest_body_is_terminal_400() -> None:
    """resolveStepArgs: a deeply-nested JSON body → a clean 400, never a status-less 500."""
    deserialised = PassThroughJsonSerde().deserialize(DEEP_NEST_BODY)  # must NOT raise
    with pytest.raises(TerminalError) as excinfo:
        _resolve(FakeContext(), deserialised)
    assert getattr(excinfo.value, "status_code", None) == 400


def test_serde_never_raises_on_deep_nest_body() -> None:
    """The structural never-raise invariant: a deep-nest body that trips ``RecursionError`` inside
    ``json.loads`` does NOT escape ``deserialize`` — it returns a (str) value. Revert-sensitive."""
    out = PassThroughJsonSerde().deserialize(DEEP_NEST_BODY)  # must NOT raise (was RecursionError)
    assert isinstance(out, str)


def test_v01_bound_refusal_still_fires_422_on_the_wire() -> None:
    """A valid-but-unresolvable tool still refuses 422 on the wire — the guard didn't break it.

    The existing v0.1 bound (anything but SO-09-01/05 is a clean "cannot resolve" 422) must still
    fire through the handler — and as a 422, NOT the new guard's 400 (a valid contract shape with a
    known-unresolvable soId). Store-independent: the bound check runs before the read.
    """
    with pytest.raises(TerminalError) as excinfo:
        _resolve(FakeContext(), {"soId": "SO-09-02", "fundId": "PF-0001"})
    assert getattr(excinfo.value, "status_code", None) == 422
    assert "cannot resolve" in str(excinfo.value).lower()


def test_missing_fund_refusal_still_fires_422_on_the_wire() -> None:
    """A valid request with no fund still refuses 422 on the wire (not the guard's 400).

    ``fundId`` defaults to empty in the contract (the in-handler refusal owns that message), so a
    valid-shape request omitting it is the existing 422 missing-fund refusal — unchanged.
    """
    with pytest.raises(TerminalError) as excinfo:
        _resolve(FakeContext(), {"soId": "SO-09-01"})
    assert getattr(excinfo.value, "status_code", None) == 422
