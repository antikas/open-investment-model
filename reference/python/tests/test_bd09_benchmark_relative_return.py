"""SO-09-04 compute_benchmark_relative_return — hand-verifiable oracle, determinism, boundaries.

The active-return identities (arithmetic ``r_p - r_b``; geometric ``(1+r_p)/(1+r_b)-1``) are
exact closed forms — the identity itself is the oracle (no toy number is invented), checked to
<= 1 bp against hand-derived figures (build-gate §A2 hand-verifiable).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from agentinvest_tools.bd09.benchmark_relative_return import (
    BenchmarkRelativeReturnInput,
    ExcessReturnMethod,
    so_09_04_compute_benchmark_relative_return,
)

ONE_BP = Decimal("0.0001")


# --- Hand-verifiable oracle (the identity is the oracle) ----------------------


def test_arithmetic_excess_is_portfolio_minus_benchmark() -> None:
    # Portfolio 8.50%, benchmark 6.20% -> active 2.30% exactly.
    out = so_09_04_compute_benchmark_relative_return(
        BenchmarkRelativeReturnInput(
            portfolio_return=Decimal("0.0850"), benchmark_return=Decimal("0.0620")
        )
    )
    assert out.method is ExcessReturnMethod.ARITHMETIC
    assert abs(out.active_return - Decimal("0.0230")) <= ONE_BP
    assert out.active_return == Decimal("0.0230")  # exact, not just within 1 bp


def test_geometric_excess_compounding_consistent() -> None:
    # (1.0850 / 1.0620) - 1 = 0.0216572... — hand-derived to compare to <= 1 bp.
    out = so_09_04_compute_benchmark_relative_return(
        BenchmarkRelativeReturnInput(
            portfolio_return=Decimal("0.0850"),
            benchmark_return=Decimal("0.0620"),
            method=ExcessReturnMethod.GEOMETRIC,
        )
    )
    expected = (Decimal("1.0850") / Decimal("1.0620")) - Decimal("1")
    assert out.method is ExcessReturnMethod.GEOMETRIC
    assert abs(out.active_return - expected) <= ONE_BP
    # Hand-derived value to 6 dp for an independent eyeball check.
    assert abs(out.active_return - Decimal("0.021657")) <= Decimal("0.000001")


def test_negative_active_return_underperformance() -> None:
    out = so_09_04_compute_benchmark_relative_return(
        BenchmarkRelativeReturnInput(
            portfolio_return=Decimal("0.04"), benchmark_return=Decimal("0.06")
        )
    )
    assert out.active_return == Decimal("-0.02")


# --- Determinism -------------------------------------------------------------


def test_deterministic_same_input_same_output() -> None:
    inp = BenchmarkRelativeReturnInput(
        portfolio_return=Decimal("0.07"), benchmark_return=Decimal("0.05")
    )
    assert (
        so_09_04_compute_benchmark_relative_return(inp)
        == so_09_04_compute_benchmark_relative_return(inp)
    )


# --- Boundary cases ----------------------------------------------------------


def test_zero_excess_when_portfolio_matches_benchmark() -> None:
    out = so_09_04_compute_benchmark_relative_return(
        BenchmarkRelativeReturnInput(
            portfolio_return=Decimal("0.05"), benchmark_return=Decimal("0.05")
        )
    )
    assert out.active_return == Decimal("0")


def test_geometric_zero_excess_when_equal() -> None:
    out = so_09_04_compute_benchmark_relative_return(
        BenchmarkRelativeReturnInput(
            portfolio_return=Decimal("0.05"),
            benchmark_return=Decimal("0.05"),
            method=ExcessReturnMethod.GEOMETRIC,
        )
    )
    assert out.active_return == Decimal("0")


def test_geometric_undefined_when_benchmark_minus_100pct() -> None:
    with pytest.raises(ValueError, match="undefined when benchmark_return is -100%"):
        so_09_04_compute_benchmark_relative_return(
            BenchmarkRelativeReturnInput(
                portfolio_return=Decimal("0.05"),
                benchmark_return=Decimal("-1"),
                method=ExcessReturnMethod.GEOMETRIC,
            )
        )
