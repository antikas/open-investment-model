"""The end-to-end analytics demo — the integration test over the live stack.

Runs the demo's full pipeline (read the canonical marts -> dispatch ``SO-09-01`` then
``SO-09-05`` to the ``bd09`` service over the Restate substrate -> reconcile) against the **live
local stack** and asserts the load-bearing properties:

- the task completes green and produces a total return + a per-segment breakdown;
- **both** operations round-tripped **through the bd09 service over the substrate** — proven on
  the service provenance (``computedBy == python:bd09`` + the per-tool methodology label), not a
  local compute;
- the **cross-step coherence invariant** holds: the per-segment contributions sum to the fund
  total return within the demo's declared tolerance — over the *whole* breakdown, not a subset;
- the derived **end NAV equals the fund-NAV mart** (the window endpoint reconciles to the
  published mart);
- the **per-operation warm latency is under the 2 s bar**, for *both* calls.

Skip semantics (the live-surface test pattern): this is a live-stack test, skipped
unless BOTH preconditions hold — the canonical marts are readable (duckdb installed + the store
built) AND the ``bd09`` service is registered and reachable over the ingress. So a plain
``uv run pytest`` in the base venv (no dbt group, substrate down) skips it cleanly; the data +
substrate provisioned, it runs end to end. The skip reason names which precondition is missing.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from agentinvest_demo.marts import (
    DEFAULT_BEGIN_DATE,
    DEFAULT_END_DATE,
    DEFAULT_FUND_ID,
    MartsUnavailableError,
    list_funds,
)
from agentinvest_demo.phase2_demo import (
    LATENCY_BAR_S,
    RECONCILIATION_TOLERANCE,
    run_phase2_demo,
)
from agentinvest_demo.restate_client import RestateDispatcher


def _marts_readable() -> bool:
    """True iff the canonical store can be read (duckdb installed + the store built)."""
    try:
        list_funds()
        return True
    except MartsUnavailableError:
        return False


def _bd09_reachable() -> bool:
    """True iff the bd09 service answers over the Restate ingress (substrate up + registered)."""
    return RestateDispatcher().ingress_healthy()


def _skip_reason() -> str | None:
    """The skip reason naming the missing precondition, or None if the live stack is ready."""
    if not _marts_readable():
        return "canonical marts not readable (install the dbt group + run pnpm dbt:build)"
    if not _bd09_reachable():
        return "bd09 service not reachable over the Restate ingress (bring the stack up)"
    return None


_SKIP_REASON = _skip_reason()
live_stack = pytest.mark.skipif(_SKIP_REASON is not None, reason=_SKIP_REASON or "")


@live_stack
def test_phase2_demo_runs_green_end_to_end() -> None:
    """The full task runs green: total return + a non-trivial multi-segment breakdown."""
    result = run_phase2_demo(
        fund_id=DEFAULT_FUND_ID, begin_date=DEFAULT_BEGIN_DATE, end_date=DEFAULT_END_DATE
    )
    assert result.data.fund_id == DEFAULT_FUND_ID
    # A non-trivial breakdown (the default fund carries several asset classes).
    assert len(result.data.segments) >= 2
    assert len(result.breakdown_call.result["contributions"]) == len(result.data.segments)
    # The figures are real numbers (a return was computed, segments contributed).
    assert isinstance(result.total_return, Decimal)


@live_stack
def test_both_operations_round_tripped_through_the_service_over_the_substrate() -> None:
    """Both SO calls carry the bd09 service provenance — proven not a local compute.

    The provenance stamp (``computedBy == python:bd09``) + the per-tool methodology label are the
    evidence the figure came back from the ``bd09`` service over the substrate. A local re-compute
    would carry neither.
    """
    result = run_phase2_demo()

    assert result.total_return_call.computed_by == "python:bd09"
    assert result.total_return_call.provenance["soId"] == "SO-09-01"
    assert result.total_return_call.provenance["methodology"] == "modified-dietz"

    assert result.breakdown_call.computed_by == "python:bd09"
    assert result.breakdown_call.provenance["soId"] == "SO-09-05"
    assert (
        result.breakdown_call.provenance["methodology"] == "contribution-weight-times-return"
    )


@live_stack
def test_contributions_reconcile_to_total_return_over_the_whole_breakdown() -> None:
    """The cross-step coherence invariant: Σ(all sector contributions) == the total return.

    The sum is over the WHOLE breakdown (every segment), not a cherry-picked subset, and it is the
    breakdown tool's own returned total (``contributions`` summed) checked against the
    total-return tool's figure. They reconcile within the demo's declared tolerance because both
    draw on one underlying per-segment NAV-delta derivation.
    """
    result = run_phase2_demo()

    # The breakdown tool's own sum over all contributions.
    contributions = result.breakdown_call.result["contributions"]
    summed = sum((Decimal(str(c["contribution"])) for c in contributions), Decimal(0))
    assert summed == result.contribution_sum, "the demo's contribution sum must be the full sum"

    # … reconciles to the total-return tool's figure within the declared tolerance.
    assert result.reconciliation_diff <= RECONCILIATION_TOLERANCE
    assert result.reconciles


@live_stack
def test_derived_end_nav_reconciles_to_the_fund_nav_mart() -> None:
    """The window end NAV equals the published fund-NAV mart — the endpoint ties to the mart."""
    result = run_phase2_demo()
    assert result.data.end_nav == result.data.mart_fund_nav


@live_stack
def test_per_operation_warm_latency_is_under_the_two_second_bar() -> None:
    """Both operations' warm round-trip latency is under the 2 s success bar.

    The bar applies to the WARM latency (a warm-up dispatch precedes the timed pair), so a one-off
    cold connection cost does not fail it; both operations are checked, not just one.
    """
    result = run_phase2_demo()
    for latency in result.latencies:
        assert latency.warm_s < LATENCY_BAR_S, (
            f"{latency.so_id} warm latency {latency.warm_s:.3f}s exceeded the "
            f"{LATENCY_BAR_S:.0f}s bar"
        )


@live_stack
def test_demo_runs_for_each_seeded_fund() -> None:
    """The task runs and reconciles for every fund the store carries — not only the default.

    Walks the whole fund set (not a single hard-coded fund), proving the pipeline is general over
    the canonical data, and that the reconciliation holds for each.
    """
    funds = list_funds()
    assert len(funds) >= 1
    for fund_id, _name in funds:
        result = run_phase2_demo(fund_id=fund_id)
        assert result.reconciles, f"{fund_id} contributions did not reconcile to the total return"
        assert result.total_return_call.computed_by == "python:bd09"
        assert result.breakdown_call.computed_by == "python:bd09"
