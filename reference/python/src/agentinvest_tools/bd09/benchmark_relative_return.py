"""SO-09-04 — compute_benchmark_relative_return (active / excess return).

The portfolio's return relative to its benchmark — the active (excess) return that is the
basis for judging a manager against the mandate's benchmark. This realises the SD-09.1 input
to benchmark comparison and feeds SD-09.2 attribution. Two declared methods:

- **arithmetic** (the default): ``active = r_portfolio - r_benchmark`` — the simple excess
  return, the standard headline active-return figure.
- **geometric**: ``active = (1 + r_portfolio) / (1 + r_benchmark) - 1`` — the compounding-consistent
  excess return that links cleanly across periods (the GIPS-preferred linking-consistent form).

External oracle (build-gate §A2 hand-verifiable): the arithmetic active return is, by
construction, ``r_portfolio - r_benchmark`` and the geometric is ``(1+r_p)/(1+r_b)-1`` — both
are exact, closed-form identities verified to <= 1 bp against hand-derived figures (no toy
oracle is invented; the identity itself is the oracle).

Honest boundary: an excess return over synthetic component returns is a correct *computation*,
not a GIPS-verified production figure.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ExcessReturnMethod(StrEnum):
    """The declared excess-return method."""

    ARITHMETIC = "arithmetic"
    GEOMETRIC = "geometric"


class BenchmarkRelativeReturnInput(BaseModel):
    """Inputs to the benchmark-relative (active/excess) return for one window."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    portfolio_return: Decimal = Field(
        description="The portfolio's return over the window (a rate)."
    )
    benchmark_return: Decimal = Field(
        description="The benchmark's return over the same window."
    )
    method: ExcessReturnMethod = Field(
        default=ExcessReturnMethod.ARITHMETIC,
        description="arithmetic (r_p - r_b) or geometric ((1+r_p)/(1+r_b)-1).",
    )


class BenchmarkRelativeReturnOutput(BaseModel):
    """The active/excess return plus the method used."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    active_return: Decimal = Field(description="The benchmark-relative (excess/active) return.")
    method: ExcessReturnMethod = Field(description="The excess-return method applied.")
    methodology: str = Field(
        description="The method label — 'arithmetic-excess' or 'geometric-excess'."
    )


def so_09_04_compute_benchmark_relative_return(
    inp: BenchmarkRelativeReturnInput,
) -> BenchmarkRelativeReturnOutput:
    """Compute the benchmark-relative (active/excess) return. SO-09-04.

    Pure and deterministic — a closed-form identity over the two input returns. Raises
    ``ValueError`` for the geometric method when ``1 + benchmark_return`` is zero (the geometric
    excess is undefined when the benchmark return is exactly −100%).
    """
    if inp.method is ExcessReturnMethod.ARITHMETIC:
        return BenchmarkRelativeReturnOutput(
            active_return=inp.portfolio_return - inp.benchmark_return,
            method=ExcessReturnMethod.ARITHMETIC,
            methodology="arithmetic-excess",
        )
    denominator = Decimal(1) + inp.benchmark_return
    if denominator == 0:
        raise ValueError("geometric excess return is undefined when benchmark_return is -100%")
    active = (Decimal(1) + inp.portfolio_return) / denominator - Decimal(1)
    return BenchmarkRelativeReturnOutput(
        active_return=active,
        method=ExcessReturnMethod.GEOMETRIC,
        methodology="geometric-excess",
    )
