"""Unit tests for the sample module — the pytest-green proof for the workspace."""

from __future__ import annotations

import math

import pytest

from agentinvest_tools.sample import SimpleReturnInput, compute_simple_return


def test_simple_return_no_cash_flow() -> None:
    # 100 -> 110, no flow: 10% return.
    r = compute_simple_return(
        SimpleReturnInput(beginning_value=100.0, ending_value=110.0, cash_flow=0.0)
    )
    assert math.isclose(r, 0.10, rel_tol=1e-9)


def test_simple_return_with_cash_flow() -> None:
    # 100 begin + 50 contribution -> 165 end. Gain over invested base 150 = 10%.
    r = compute_simple_return(
        SimpleReturnInput(beginning_value=100.0, ending_value=165.0, cash_flow=50.0)
    )
    assert math.isclose(r, 0.10, rel_tol=1e-9)


def test_simple_return_loss() -> None:
    r = compute_simple_return(
        SimpleReturnInput(beginning_value=200.0, ending_value=180.0, cash_flow=0.0)
    )
    assert math.isclose(r, -0.10, rel_tol=1e-9)


def test_simple_return_undefined_denominator() -> None:
    with pytest.raises(ValueError, match="undefined"):
        compute_simple_return(
            SimpleReturnInput(beginning_value=0.0, ending_value=10.0, cash_flow=0.0)
        )
