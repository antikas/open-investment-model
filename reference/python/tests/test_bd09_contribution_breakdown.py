"""SO-09-05 compute_contribution_breakdown — hand-verifiable oracle, determinism, boundaries.

The contribution identity (``sum_i w_i * r_i = r_total``) is exact — it is its own oracle,
checked to <= 1 bp against a hand-derived breakdown (build-gate §A2 hand-verifiable). A
deliberately weight-unbalanced input is rejected (the breakdown must partition the portfolio).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from agentinvest_tools.bd09.contribution_breakdown import (
    ContributionBreakdownInput,
    SegmentInput,
    so_09_05_compute_contribution_breakdown,
)

ONE_BP = Decimal("0.0001")


def _seg(label: str, weight: str, ret: str) -> SegmentInput:
    """Terse SegmentInput builder for readable hand-derived fixtures."""
    return SegmentInput(segment=label, weight=Decimal(weight), segment_return=Decimal(ret))


# --- Hand-verifiable oracle (the summing identity is the oracle) --------------


def test_contributions_sum_to_total_hand_derived() -> None:
    """Hand-derived: 60% @ +10% and 40% @ -5% -> contributions 6% and -2% -> total 4%."""
    out = so_09_05_compute_contribution_breakdown(
        ContributionBreakdownInput(
            segments=(
                _seg("equities", "0.60", "0.10"),
                _seg("bonds", "0.40", "-0.05"),
            )
        )
    )
    contribs = {c.segment: c.contribution for c in out.contributions}
    assert contribs["equities"] == Decimal("0.060")
    assert contribs["bonds"] == Decimal("-0.020")
    # The contributions sum to the total return (the load-bearing identity).
    assert out.total_return == Decimal("0.040")
    summed = sum((c.contribution for c in out.contributions), Decimal(0))
    assert abs(out.total_return - summed) <= ONE_BP


def test_three_segment_asset_class_axis() -> None:
    # 50% @ 8%, 30% @ 4%, 20% @ -2% -> 4% + 1.2% - 0.4% = 4.8%.
    out = so_09_05_compute_contribution_breakdown(
        ContributionBreakdownInput(
            segments=(
                _seg("public-equity", "0.50", "0.08"),
                _seg("fixed-income", "0.30", "0.04"),
                _seg("real-assets", "0.20", "-0.02"),
            )
        )
    )
    assert abs(out.total_return - Decimal("0.048")) <= ONE_BP


# --- Determinism -------------------------------------------------------------


def test_deterministic_same_input_same_output() -> None:
    inp = ContributionBreakdownInput(
        segments=(
            SegmentInput(segment="a", weight=Decimal("0.5"), segment_return=Decimal("0.1")),
            SegmentInput(segment="b", weight=Decimal("0.5"), segment_return=Decimal("0.2")),
        )
    )
    assert (
        so_09_05_compute_contribution_breakdown(inp)
        == so_09_05_compute_contribution_breakdown(inp)
    )


def test_segment_order_preserved_and_total_order_independent() -> None:
    s_eq = _seg("eq", "0.6", "0.1")
    s_fi = _seg("fi", "0.4", "-0.05")
    forward = so_09_05_compute_contribution_breakdown(
        ContributionBreakdownInput(segments=(s_eq, s_fi))
    )
    reverse = so_09_05_compute_contribution_breakdown(
        ContributionBreakdownInput(segments=(s_fi, s_eq))
    )
    # Output preserves input order ...
    assert [c.segment for c in forward.contributions] == ["eq", "fi"]
    assert [c.segment for c in reverse.contributions] == ["fi", "eq"]
    # ... and the total is the same regardless of order.
    assert forward.total_return == reverse.total_return


# --- Boundary cases ----------------------------------------------------------


def test_single_segment_is_the_whole_portfolio() -> None:
    out = so_09_05_compute_contribution_breakdown(
        ContributionBreakdownInput(
            segments=(_seg("all", "1", "0.07"),)
        )
    )
    assert out.total_return == Decimal("0.07")


def test_empty_segments_rejected() -> None:
    with pytest.raises(ValueError, match="at least one segment"):
        ContributionBreakdownInput(segments=())


def test_unbalanced_weights_rejected() -> None:
    with pytest.raises(ValueError, match="must partition the portfolio"):
        ContributionBreakdownInput(
            segments=(
                SegmentInput(segment="a", weight=Decimal("0.6"), segment_return=Decimal("0.1")),
                SegmentInput(segment="b", weight=Decimal("0.6"), segment_return=Decimal("0.1")),
            )
        )


def test_weights_within_rounding_tolerance_accepted() -> None:
    # 0.3333 + 0.3333 + 0.3334 = 1.0000 -> accepted (legitimate rounding).
    out = so_09_05_compute_contribution_breakdown(
        ContributionBreakdownInput(
            segments=(
                SegmentInput(segment="a", weight=Decimal("0.3333"), segment_return=Decimal("0.03")),
                SegmentInput(segment="b", weight=Decimal("0.3333"), segment_return=Decimal("0.03")),
                SegmentInput(segment="c", weight=Decimal("0.3334"), segment_return=Decimal("0.03")),
            )
        )
    )
    assert abs(out.total_return - Decimal("0.03")) <= ONE_BP
