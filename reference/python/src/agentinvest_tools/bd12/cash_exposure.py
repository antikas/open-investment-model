"""SO-12.1-02 — read the IBOR projected cash + exposure (per portfolio, as-of).

SD-12.1 IBOR's *cash and exposure projection* Service Operation: the projected cash balance and
gross exposure for a portfolio, **including the cash impact of unsettled trades**, so the desk
trades against an accurate available-cash figure. The distinguishing IBOR property is that the
projection includes in-flight (agreed-but-unsettled) activity — the front office sees the cash
effect of its own committed trades before they settle, which is precisely the TD/SD-timing
divergence that the ABOR book (which recognises on settlement) does not yet carry.

Pure and deterministic: the settled position market value, the realised cash flows and the
unsettled-trade legs are read by the data-access layer at the as-of and passed in; this tool sums
them into the projected cash + exposure. No I/O, no clock, no RNG.

Honest boundary: a correct projection over a **synthetic** internal book, not a
production cash projection and not a live-custodian read.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class UnsettledTradeLeg(BaseModel):
    """One in-flight (agreed-but-unsettled) trade's cash leg — the IBOR cash-projection adjustment.

    ``amount_usd`` is signed by direction (a buy is a negative cash impact — cash leaves on
    settlement; a sell is positive). ``settlement_date`` is after the as-of (that is what makes it
    in-flight). These are the E-05 ``pending`` / ``confirmed`` transactions whose settlement lands
    after the read date — the IBOR book projects their cash impact; the ABOR book does not yet.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    transaction_id: str = Field(description="The in-flight transaction (E-05).")
    instrument_id: str = Field(description="The instrument transacted (E-02).")
    settlement_date: date = Field(description="When it settles (after the as-of; in-flight).")
    amount_usd: Decimal = Field(description="The signed cash impact on settle (buy < 0, sell > 0).")


class ReadCashExposureInput(BaseModel):
    """Inputs to the IBOR cash + exposure projection for one portfolio at an as-of."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    portfolio_id: str = Field(description="The portfolio whose projected cash + exposure to read.")
    as_of_date: date = Field(description="Project as of this date.")
    settled_cash_usd: Decimal = Field(
        description="The realised (settled) cash balance for the portfolio at the as-of."
    )
    gross_market_value_usd: Decimal = Field(
        description="Σ the IBOR position market values — the gross long exposure at the as-of."
    )
    unsettled_legs: tuple[UnsettledTradeLeg, ...] = Field(
        default=(),
        description="The in-flight trade cash legs (settlement after the as-of) the IBOR projects.",
    )


class ReadCashExposureOutput(BaseModel):
    """The IBOR projected cash + exposure — settled cash, the in-flight adjustment, projection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    portfolio_id: str = Field(description="The portfolio.")
    as_of_date: date = Field(description="The as-of date the projection honoured.")
    settled_cash_usd: Decimal = Field(description="The realised (settled) cash at the as-of.")
    unsettled_cash_impact_usd: Decimal = Field(
        description="Σ the in-flight trade cash legs — the IBOR-only projection adjustment."
    )
    projected_cash_usd: Decimal = Field(
        description="settled_cash + unsettled_cash_impact — the available cash the desk trades on."
    )
    gross_exposure_usd: Decimal = Field(description="The gross long exposure (IBOR market value).")
    n_unsettled: int = Field(description="The number of in-flight legs in the projection.")


def read_ibor_cash_and_exposure(inp: ReadCashExposureInput) -> ReadCashExposureOutput:
    """Project the IBOR cash + exposure including the cash impact of unsettled trades. SO-12.1-02.

    Pure and deterministic: the projected cash is the settled cash plus the signed sum of the
    in-flight trade cash legs (the IBOR-only adjustment — the ABOR book recognises these only on
    settlement). The gross exposure is the Σ IBOR position market value passed in. No I/O, no clock.
    """
    unsettled = sum((leg.amount_usd for leg in inp.unsettled_legs), Decimal(0))
    return ReadCashExposureOutput(
        portfolio_id=inp.portfolio_id,
        as_of_date=inp.as_of_date,
        settled_cash_usd=inp.settled_cash_usd,
        unsettled_cash_impact_usd=unsettled,
        projected_cash_usd=inp.settled_cash_usd + unsettled,
        gross_exposure_usd=inp.gross_market_value_usd,
        n_unsettled=len(inp.unsettled_legs),
    )
