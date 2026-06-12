"""SO-09-01 — compute_total_return (Modified Dietz).

Total return over a window with day-weighted external cash flows — the Modified Dietz
method. The numerator is the gain (ending − beginning − net external flow); the denominator
is the beginning value plus each external flow weighted by the fraction of the period it was
in the portfolio. This is the SD-09.1 "strike period returns" / total-return capability at
the single-window grain, and the day-weighting is what distinguishes Modified Dietz from the
simple Dietz approximation (a flow's impact is weighted by how long it was invested).

Method (the published Modified Dietz formula):

    r = (V_end - V_begin - sum(CF_i)) / (V_begin + sum(CF_i * w_i))

where ``w_i = (period_days - day_of_flow_i) / period_days`` is the fraction of the period the
flow ``CF_i`` was in the portfolio (a flow on day 0 carries full weight 1; a flow on the last
day carries ~0). Flows are signed: a contribution is positive, a withdrawal negative.

External oracle (build-gate §A2): matched in the test suite to the published worked example in
the Wikipedia "Modified Dietz method" article (A=100, B=300, F=+50 at mid-period weight 0.5 →
gain 150 / average capital 125 = 120%) to <= 1 bp absolute, and cross-checked against the
Corporate Finance Institute worked example. The external published figure is the proof; a
match against this tool's own synthetic data would be self-referential.

Honest boundary: this computes the Modified Dietz return correctly over the inputs given. Over
synthetic inputs that is a correct *computation*, not a GIPS-verified production return.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class WeightedCashFlow(BaseModel):
    """One dated external cash flow within the window.

    ``day`` is the day-of-period the flow occurred on (0 = the start of the period, i.e. the
    valuation date the beginning value is as of; ``period_days`` = the end). The Modified Dietz
    weight is derived from ``day`` and the window's ``period_days`` — the flow is not pre-weighted
    so the same flow record can be reused across windows of different length.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    day: int = Field(
        ge=0,
        description="Day-of-period the flow occurred on (0 = period start, period_days = end).",
    )
    amount: Decimal = Field(
        description="Signed external flow in the portfolio currency — contribution > 0, "
        "withdrawal < 0. An income/expense that is an external cash movement only.",
    )


class TotalReturnInput(BaseModel):
    """Inputs to the Modified-Dietz total return for one portfolio over one window."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    beginning_value: Decimal = Field(
        description="Portfolio market value at the start of the period (as-of the period start)."
    )
    ending_value: Decimal = Field(
        description="Portfolio market value at the end of the period (as-of the period end)."
    )
    period_days: int = Field(
        gt=0, description="Length of the measurement period in days (the weighting denominator)."
    )
    cash_flows: tuple[WeightedCashFlow, ...] = Field(
        default=(),
        description="Dated external cash flows within the window; empty for a no-flow window.",
    )

    @model_validator(mode="after")
    def _flows_within_period(self) -> TotalReturnInput:
        for cf in self.cash_flows:
            if cf.day > self.period_days:
                raise ValueError(
                    f"cash flow on day {cf.day} is outside the {self.period_days}-day period"
                )
        return self


class TotalReturnOutput(BaseModel):
    """The computed Modified-Dietz total return plus provenance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    total_return: Decimal = Field(description="The Modified-Dietz return over the period (a rate).")
    average_capital: Decimal = Field(
        description="The denominator — beginning value plus day-weighted net flow."
    )
    net_external_flow: Decimal = Field(description="Sum of the signed external cash flows.")
    methodology: str = Field(description="The method label — 'modified-dietz'.")


def so_09_01_compute_total_return(inp: TotalReturnInput) -> TotalReturnOutput:
    """Compute the Modified-Dietz total return for a portfolio over a window. SO-09-01.

    Pure and deterministic: the output is a function of the input alone (no I/O, no clock, no
    RNG, no dict-order dependence — flows are summed associatively over an ordered tuple).

    Raises ``ValueError`` when the weighted average capital is zero (the return is undefined —
    e.g. a zero beginning value with no offsetting weighted inflow), so the caller sees an
    explicit error rather than a divide-by-zero or a silent ``nan``.
    """
    period_days = Decimal(inp.period_days)
    net_flow = sum((cf.amount for cf in inp.cash_flows), Decimal(0))
    weighted_flow = sum(
        (
            cf.amount * (period_days - Decimal(cf.day)) / period_days
            for cf in inp.cash_flows
        ),
        Decimal(0),
    )
    average_capital = inp.beginning_value + weighted_flow
    if average_capital == 0:
        raise ValueError(
            "modified-dietz return is undefined when the weighted average capital is zero"
        )
    gain = inp.ending_value - inp.beginning_value - net_flow
    return TotalReturnOutput(
        total_return=gain / average_capital,
        average_capital=average_capital,
        net_external_flow=net_flow,
        methodology="modified-dietz",
    )
