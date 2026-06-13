"""SO-09-02 compute_time_weighted_return (true TWR) — external oracle, determinism, boundaries.

The load-bearing test is ``test_oracle_*``: the geometric link matches a **published** TWR
worked example to <= 1 bp absolute.

Source-authority note: the oracle here is the **AnalystPrep CFA Level I** worked example
— a public, canonical-method mirror (the geometric link is textbook-invariant and was
independently re-derived). It is *not* the named primary source (the GIPS Handbook /
official CFA-CIPM curriculum). The primary GIPS Handbook / CFA-CIPM worked examples are the
production-grade oracle to fold in once properly sourced — a carry-forward. The figure is
correct; the authority caveat is recorded honestly.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from agentinvest_tools.bd09.time_weighted_return import (
    SubPeriod,
    TimeWeightedReturnInput,
    so_09_02_compute_time_weighted_return,
)

ONE_BP = Decimal("0.0001")


# --- external oracle ---------------------------------------------------------


def test_oracle_analystprep_two_period_linking_from_values() -> None:
    """PUBLISHED ORACLE — AnalystPrep CFA Level I, two-period TWR example.

    Source: https://analystprep.com/cfa-level-1-exam/quantitative-methods/money-weighted-and-time-weighted-rates-of-return/
    A share bought at 50; year 1 pays a 0.50 dividend and ends at 53 -> HPR1 = (53-50+0.5)/50 = 7%.
    A second share bought (value 106); year 2 pays 1.20 in dividends and ends at 110 ->
    HPR2 = (110-106+1.2)/106 = 4.9057%. Geometric link 1.07 * 1.049057 - 1, published as 12.24%.
    We derive the sub-period returns from the published values (not pre-supplied) so the tool's
    value-derivation path is exercised against the published figure.
    """
    published_twr = Decimal("0.1224")  # 12.24%, verbatim (AnalystPrep rounds/truncates to 2 dp).
    out = so_09_02_compute_time_weighted_return(
        TimeWeightedReturnInput(
            sub_periods=(
                SubPeriod(
                    beginning_value=Decimal("50"),
                    ending_value=Decimal("53"),
                    income=Decimal("0.50"),
                ),
                SubPeriod(
                    beginning_value=Decimal("106"),
                    ending_value=Decimal("110"),
                    income=Decimal("1.20"),
                ),
            )
        )
    )
    # The two sub-period returns reproduce the published 7% and ~4.9057%.
    assert abs(out.sub_period_returns[0] - Decimal("0.07")) <= ONE_BP
    assert abs(out.sub_period_returns[1] - Decimal("0.049057")) <= Decimal("0.000001")
    # The linked TWR matches the published 12.24% to <= 1 bp.
    assert abs(out.time_weighted_return - published_twr) <= ONE_BP


def test_oracle_exact_linking_identity() -> None:
    """Linking is exact: directly-supplied 7% and 4.9057% link to the same figure.

    This pins the geometric-linking arithmetic against the unambiguous (un-truncated) value
    1.07 * 1.049057 - 1 = 0.12249099, removing the published example's 2-dp truncation as a
    source of the residual — the formula itself is exact, the only gap is AnalystPrep's rounding.
    """
    out = so_09_02_compute_time_weighted_return(
        TimeWeightedReturnInput(
            sub_periods=(
                SubPeriod(sub_period_return=Decimal("0.07")),
                SubPeriod(sub_period_return=Decimal("0.049057")),
            )
        )
    )
    expected = (Decimal("1.07") * Decimal("1.049057")) - Decimal("1")
    assert out.time_weighted_return == expected


# --- Determinism -------------------------------------------------------------


def test_deterministic_same_input_same_output() -> None:
    inp = TimeWeightedReturnInput(
        sub_periods=(
            SubPeriod(sub_period_return=Decimal("0.03")),
            SubPeriod(sub_period_return=Decimal("-0.01")),
            SubPeriod(sub_period_return=Decimal("0.02")),
        )
    )
    assert so_09_02_compute_time_weighted_return(inp) == so_09_02_compute_time_weighted_return(inp)


# --- Boundary cases ----------------------------------------------------------


def test_single_sub_period_links_to_itself() -> None:
    out = so_09_02_compute_time_weighted_return(
        TimeWeightedReturnInput(sub_periods=(SubPeriod(sub_period_return=Decimal("0.05")),))
    )
    assert out.time_weighted_return == Decimal("0.05")


def test_empty_sub_periods_rejected() -> None:
    with pytest.raises(ValueError, match="at least one sub-period"):
        TimeWeightedReturnInput(sub_periods=())


def test_negative_and_recovery_links_correctly() -> None:
    # -50% then +100% returns to flat (a classic TWR boundary: links to 0, not the average).
    out = so_09_02_compute_time_weighted_return(
        TimeWeightedReturnInput(
            sub_periods=(
                SubPeriod(sub_period_return=Decimal("-0.5")),
                SubPeriod(sub_period_return=Decimal("1.0")),
            )
        )
    )
    assert out.time_weighted_return == Decimal("0")


def test_zero_beginning_value_in_derivation_rejected() -> None:
    with pytest.raises(ValueError, match="undefined when beginning_value is zero"):
        SubPeriod(beginning_value=Decimal("0"), ending_value=Decimal("10"))


def test_both_forms_supplied_rejected() -> None:
    with pytest.raises(ValueError, match="not both"):
        SubPeriod(
            sub_period_return=Decimal("0.05"),
            beginning_value=Decimal("100"),
            ending_value=Decimal("105"),
        )


def test_neither_form_supplied_rejected() -> None:
    with pytest.raises(ValueError, match="supply sub_period_return"):
        SubPeriod()
