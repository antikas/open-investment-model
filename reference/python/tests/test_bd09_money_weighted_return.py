"""SO-09-03 compute_money_weighted_return (IRR/MWR) — §A2 oracle, determinism, boundaries.

The load-bearing test is ``test_oracle_*``: the IRR matches a **published** MWR worked example
to <= 1 bp absolute (build-gate §A2).

§A2 source-authority note: the §A2 oracle here is the **AnalystPrep CFA Level I** worked example
— a public, canonical-method mirror (the IRR root is textbook-invariant regardless of which
publication prints it, and the figure was independently re-derived). It is *not* the brief's
named primary source (the GIPS Handbook / official CFA-CIPM curriculum worked examples). The
primary GIPS Handbook / CFA-CIPM examples are the production-grade oracle to fold into the
eval-harness Class-A arm once properly sourced — a carry-forward. The figure is correct; the
authority caveat is recorded honestly.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from agentinvest_tools.bd09.money_weighted_return import (
    DatedCashFlow,
    MoneyWeightedReturnInput,
    NonConventionalCashFlowError,
    so_09_03_compute_money_weighted_return,
)

ONE_BP = Decimal("0.0001")


# --- §A2 external oracle -----------------------------------------------------


def test_oracle_analystprep_irr_example() -> None:
    """PUBLISHED ORACLE — AnalystPrep CFA Level I money-weighted-return example.

    Source: https://analystprep.com/cfa-level-1-exam/quantitative-methods/money-weighted-and-time-weighted-rates-of-return/
    Cash flows: -10,000 at t=0, -5,000 at t=1, +25,000 at t=2 (the terminal value). The
    money-weighted return (the IRR solving NPV = 0) is published as approximately 35.08%.
    """
    published_irr = Decimal("0.3508")  # 35.08%, verbatim from AnalystPrep.
    out = so_09_03_compute_money_weighted_return(
        MoneyWeightedReturnInput(
            cash_flows=(
                DatedCashFlow(time=Decimal("0"), amount=Decimal("-10000")),
                DatedCashFlow(time=Decimal("1"), amount=Decimal("-5000")),
                DatedCashFlow(time=Decimal("2"), amount=Decimal("25000")),
            )
        )
    )
    assert abs(out.money_weighted_return - published_irr) <= ONE_BP


def test_oracle_simple_single_period_irr_is_exact() -> None:
    """A one-period -100 / +110 series has an exact IRR of 10% — pins the solver's accuracy.

    This is the textbook degenerate IRR (a single contribution and a single terminal value one
    period later); the root is the holding-period return exactly, so it pins solver convergence
    well inside the 1 bp gate independently of any external source's rounding.
    """
    out = so_09_03_compute_money_weighted_return(
        MoneyWeightedReturnInput(
            cash_flows=(
                DatedCashFlow(time=Decimal("0"), amount=Decimal("-100")),
                DatedCashFlow(time=Decimal("1"), amount=Decimal("110")),
            )
        )
    )
    assert abs(out.money_weighted_return - Decimal("0.10")) <= ONE_BP


# --- Determinism -------------------------------------------------------------


def test_deterministic_same_input_same_root_and_iterations() -> None:
    inp = MoneyWeightedReturnInput(
        cash_flows=(
            DatedCashFlow(time=Decimal("0"), amount=Decimal("-1000")),
            DatedCashFlow(time=Decimal("1"), amount=Decimal("300")),
            DatedCashFlow(time=Decimal("2"), amount=Decimal("900")),
        )
    )
    a = so_09_03_compute_money_weighted_return(inp)
    b = so_09_03_compute_money_weighted_return(inp)
    # Identical root AND identical iteration count — the bisection is fully deterministic.
    assert a == b
    assert a.iterations == b.iterations


# --- Boundary cases ----------------------------------------------------------


def test_mixed_sign_negative_irr() -> None:
    # -1000 then +900 one period later -> a -10% IRR (a loss).
    out = so_09_03_compute_money_weighted_return(
        MoneyWeightedReturnInput(
            cash_flows=(
                DatedCashFlow(time=Decimal("0"), amount=Decimal("-1000")),
                DatedCashFlow(time=Decimal("1"), amount=Decimal("900")),
            )
        )
    )
    assert abs(out.money_weighted_return - Decimal("-0.10")) <= ONE_BP


def test_single_flow_rejected() -> None:
    with pytest.raises(ValueError, match="at least two cash flows"):
        MoneyWeightedReturnInput(
            cash_flows=(DatedCashFlow(time=Decimal("0"), amount=Decimal("-100")),)
        )


def test_all_same_sign_rejected() -> None:
    with pytest.raises(ValueError, match="without both an inflow and an outflow"):
        MoneyWeightedReturnInput(
            cash_flows=(
                DatedCashFlow(time=Decimal("0"), amount=Decimal("-100")),
                DatedCashFlow(time=Decimal("1"), amount=Decimal("-50")),
            )
        )


def test_zero_irr_when_flows_net_to_zero_undiscounted() -> None:
    # -100 at t0, +100 at t1: the rate that zeros NPV is 0%.
    out = so_09_03_compute_money_weighted_return(
        MoneyWeightedReturnInput(
            cash_flows=(
                DatedCashFlow(time=Decimal("0"), amount=Decimal("-100")),
                DatedCashFlow(time=Decimal("1"), amount=Decimal("100")),
            )
        )
    )
    assert abs(out.money_weighted_return) <= ONE_BP


# --- Fail-loud on a non-conventional (multiple-sign-change) series ------------
#
# A non-conventional series (> 1 sign change in time order) may have multiple real IRRs or none
# in range; a single-root bracketed bisection would silently return one arbitrary root with no
# signal that others are equally valid (a fiduciary landmine — J-curve fund flows are exactly
# this shape). The solver must instead FAIL LOUD with a typed error. The *resolution* of such a
# series (the economically-meaningful root, or MIRR) is a deferred carry-forward, not built here.


def test_three_irr_series_raises_not_silently_returns_a_root() -> None:
    """A non-conventional series with three real IRRs (0%, 100%, 200%) — must fail loud.

    ``-1000, +6000, -11000, +6000`` has signs ``- + - +`` (three sign changes) and three real
    IRRs. A single-root solver would return ~0% silently with no multi-root signal; it must
    instead raise ``NonConventionalCashFlowError``.
    """
    inp = MoneyWeightedReturnInput(
        cash_flows=(
            DatedCashFlow(time=Decimal("0"), amount=Decimal("-1000")),
            DatedCashFlow(time=Decimal("1"), amount=Decimal("6000")),
            DatedCashFlow(time=Decimal("2"), amount=Decimal("-11000")),
            DatedCashFlow(time=Decimal("3"), amount=Decimal("6000")),
        )
    )
    with pytest.raises(NonConventionalCashFlowError, match="non-conventional"):
        so_09_03_compute_money_weighted_return(inp)


def test_two_irr_series_raises_consistently() -> None:
    """A two-IRR series — signs ``- + -`` (two sign changes), IRRs at 25% and 400%.

    Previously a two-root series happened to *raise* ("not bracketed") while a three-root series
    *silently returned* — the failure mode was parity-dependent. Now both raise the same typed
    error consistently, because the sign-change guard runs before bracketing.
    """
    inp = MoneyWeightedReturnInput(
        cash_flows=(
            DatedCashFlow(time=Decimal("0"), amount=Decimal("-4000")),
            DatedCashFlow(time=Decimal("1"), amount=Decimal("25000")),
            DatedCashFlow(time=Decimal("2"), amount=Decimal("-25000")),
        )
    )
    with pytest.raises(NonConventionalCashFlowError, match="non-conventional"):
        so_09_03_compute_money_weighted_return(inp)


def test_non_conventional_error_is_a_valueerror() -> None:
    """The typed error subclasses ValueError so existing ``except ValueError`` handling holds."""
    assert issubclass(NonConventionalCashFlowError, ValueError)


def test_conventional_series_with_root_outside_range_raises_clearly() -> None:
    """A conventional (one-sign-change) series whose unique IRR is above the bracket fails loud.

    ``-1, +102`` is conventional (one sign change) and has a single IRR of 10,100%, which lies
    above the ``[-0.999999, 100.0]`` (−100% … 10,000%) bracket. The solver raises a clear
    "not bracketed" ValueError rather than returning a mis-bracketed number — a no-root-in-range
    conventional case, distinct from the non-conventional guard above.
    """
    inp = MoneyWeightedReturnInput(
        cash_flows=(
            DatedCashFlow(time=Decimal("0"), amount=Decimal("-1")),
            DatedCashFlow(time=Decimal("1"), amount=Decimal("102")),
        )
    )
    with pytest.raises(ValueError, match="not bracketed"):
        so_09_03_compute_money_weighted_return(inp)
