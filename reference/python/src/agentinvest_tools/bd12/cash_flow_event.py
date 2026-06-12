"""SO-12.1-05 — read the E-06 Cash Flow Event records (per portfolio, as-of).

SD-12.1 IBOR owns E-06 Cash Flow Event (model/entities/core/E-06-cash-flow-event.md: "the granular
event and cash records the book is built from"). This tool reads the dated cash movements — the
coupon / dividend / fee / contribution / distribution / principal legs — at an as-of date, for a
portfolio. Reconciliation's cash leg (OIM-162) consumes this read: the IBOR cash-flow set is one
side of the cash reconciliation against the external comparator feed's cash statement.

"As-of" for a cash-flow read means the events whose ``cash_flow_date`` is on or before the as-of
(the realised cash movements up to the read date). The data-access layer applies the filter; this
tool types, orders and summarises the rows.

Pure and deterministic: no I/O, no clock, no RNG.

Honest boundary: a correct read over the OIM-160 **synthetic** internal book, not a production
cash-flow feed.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CashFlowRow(BaseModel):
    """One E-06 Cash Flow Event row — column-faithful to the E-06 attribute schema."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cash_flow_id: str = Field(description="Primary key.")
    portfolio_id: str = Field(description="The portfolio the cash flow occurs in (E-03).")
    instrument_id: str | None = Field(
        default=None, description="The instrument the flow relates to; null for a portfolio flow."
    )
    transaction_id: str | None = Field(
        default=None, description="The transaction that generated this flow, where there is one."
    )
    cash_flow_date: date = Field(description="The date of the cash movement.")
    cash_flow_type: str = Field(
        description="'contribution' / 'distribution' / 'coupon' / 'dividend' / 'fee' / 'expense' / "
        "'income' / 'principal' / 'tax'."
    )
    direction: str = Field(description="'inflow' or 'outflow', from the investor's perspective.")
    amount: Decimal = Field(description="The amount, signed by direction.")
    currency: str = Field(description="The cash-flow currency.")
    source: str = Field(description="The source the cash flow was captured from.")


class ReadCashFlowsInput(BaseModel):
    """Inputs to the E-06 Cash Flow Event read — the portfolio, the as-of, the rows."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    portfolio_id: str = Field(description="The portfolio whose cash flows to read.")
    as_of_date: date = Field(description="Read cash flows with cash_flow_date on or before this.")
    rows: tuple[CashFlowRow, ...] = Field(
        default=(),
        description="The E-06 rows for the portfolio at the as-of, from the data layer.",
    )


class ReadCashFlowsOutput(BaseModel):
    """The E-06 Cash Flow Event read — the rows ordered, plus the count + net signed amount."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    portfolio_id: str = Field(description="The portfolio.")
    as_of_date: date = Field(description="The as-of date the read honoured.")
    n_cash_flows: int = Field(description="The number of cash flows read.")
    net_amount_usd: Decimal = Field(description="Σ the signed cash-flow amounts.")
    cash_flows: tuple[CashFlowRow, ...] = Field(
        description="The cash flows, ordered by cash_flow_id."
    )


def read_cash_flow_events(inp: ReadCashFlowsInput) -> ReadCashFlowsOutput:
    """Read the E-06 Cash Flow Event records for a portfolio as of the date. SO-12.1-05.

    Pure and deterministic: orders the rows by ``cash_flow_id`` and sums the signed amounts. The
    data-access layer applies the as-of filter (``cash_flow_date <= as_of``); this tool shapes them.
    """
    ordered = tuple(sorted(inp.rows, key=lambda r: r.cash_flow_id))
    net = sum((r.amount for r in ordered), Decimal(0))
    return ReadCashFlowsOutput(
        portfolio_id=inp.portfolio_id,
        as_of_date=inp.as_of_date,
        n_cash_flows=len(ordered),
        net_amount_usd=net,
        cash_flows=ordered,
    )
