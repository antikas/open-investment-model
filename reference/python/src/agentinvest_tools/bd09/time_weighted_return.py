"""SO-09-02 — compute_time_weighted_return (true TWR).

True time-weighted return: the portfolio is revalued at every external cash flow, a return is
computed for each resulting sub-period, and the sub-period returns are **linked geometrically**.
This removes the effect of external-flow timing entirely (each sub-period return is independent
of how much capital was in the portfolio), which is why TWR is the GIPS basis for comparing a
manager against a benchmark and against peers. This realises the SD-09.1 "calculate
time-weighted return" Service Operation and the geometric-linking core of "strike period
returns" (linking sub-period returns to a daily/monthly/quarterly/YTD/since-inception figure).

Method (the published geometric-linking formula):

    r_twr = (1 + r_1)(1 + r_2)...(1 + r_n) - 1

where each ``r_k`` is the sub-period return between two consecutive valuations (struck at each
external flow). A sub-period return is supplied directly, or derived from the sub-period's
beginning value, ending value and any income/flow that accrued to value within it:

    r_k = (V_end - V_begin + income) / V_begin

External oracle: matched in the test suite to the published two-period
worked example in the AnalystPrep CFA Level I "Money-Weighted and Time-Weighted Rates of
Return" notes (sub-period returns 7% and ~4.9057% link to 12.24% as published) to <= 1 bp
absolute. The published figure is the proof, not this tool's own synthetic output.

Honest boundary: a green link over synthetic sub-period returns is a correct *computation*,
not a GIPS-verified production return.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SubPeriod(BaseModel):
    """One sub-period between two consecutive valuations (struck at each external flow).

    Either supply ``sub_period_return`` directly (already computed for the sub-period), or supply
    ``beginning_value`` and ``ending_value`` (and optional ``income``) and the tool derives the
    sub-period return as ``(end - begin + income) / begin``. Exactly one of the two forms is used
    per sub-period — supplying neither, or a direct return alongside values, is rejected so the
    derivation is never silently ambiguous.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    sub_period_return: Decimal | None = Field(
        default=None,
        description="The sub-period return as a rate, where already computed.",
    )
    beginning_value: Decimal | None = Field(
        default=None,
        description="Value at the start of the sub-period (when deriving the return from values).",
    )
    ending_value: Decimal | None = Field(
        default=None,
        description="Value at the end of the sub-period, before the next external flow.",
    )
    income: Decimal = Field(
        default=Decimal(0),
        description="Income that accrued to value within the sub-period (dividend/coupon).",
    )

    @model_validator(mode="after")
    def _exactly_one_form(self) -> SubPeriod:
        has_direct = self.sub_period_return is not None
        has_values = self.beginning_value is not None and self.ending_value is not None
        if has_direct and (self.beginning_value is not None or self.ending_value is not None):
            raise ValueError(
                "supply either sub_period_return OR (beginning_value, ending_value), not both"
            )
        if not has_direct and not has_values:
            raise ValueError(
                "supply sub_period_return, or both beginning_value and ending_value"
            )
        if has_values and self.beginning_value == 0:
            raise ValueError("sub-period return undefined when beginning_value is zero")
        return self

    def realised_return(self) -> Decimal:
        """The sub-period return — supplied directly or derived from the values."""
        if self.sub_period_return is not None:
            return self.sub_period_return
        # _exactly_one_form guarantees both values are present and begin != 0 here.
        assert self.beginning_value is not None and self.ending_value is not None
        return (self.ending_value - self.beginning_value + self.income) / self.beginning_value


class TimeWeightedReturnInput(BaseModel):
    """Inputs to the geometrically-linked time-weighted return for one window."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sub_periods: tuple[SubPeriod, ...] = Field(
        description="The ordered sub-periods between consecutive valuations; at least one.",
    )

    @model_validator(mode="after")
    def _at_least_one_sub_period(self) -> TimeWeightedReturnInput:
        if not self.sub_periods:
            raise ValueError("time-weighted return needs at least one sub-period")
        return self


class TimeWeightedReturnOutput(BaseModel):
    """The geometrically-linked time-weighted return plus the per-sub-period returns."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    time_weighted_return: Decimal = Field(
        description="The geometrically-linked TWR over the whole window (a rate)."
    )
    sub_period_returns: tuple[Decimal, ...] = Field(
        description="The per-sub-period returns that were linked, in order."
    )
    methodology: str = Field(description="The method label — 'true-time-weighted'.")


def so_09_02_compute_time_weighted_return(
    inp: TimeWeightedReturnInput,
) -> TimeWeightedReturnOutput:
    """Compute the geometrically-linked time-weighted return for a window. SO-09-02.

    Pure and deterministic: the link is an ordered product over ``inp.sub_periods``; no I/O,
    clock, RNG or dict-order dependence. A single sub-period links to itself (the boundary case
    where the window has no internal external flow).
    """
    sub_returns = tuple(sp.realised_return() for sp in inp.sub_periods)
    growth = Decimal(1)
    for r in sub_returns:
        growth *= Decimal(1) + r
    return TimeWeightedReturnOutput(
        time_weighted_return=growth - Decimal(1),
        sub_period_returns=sub_returns,
        methodology="true-time-weighted",
    )
