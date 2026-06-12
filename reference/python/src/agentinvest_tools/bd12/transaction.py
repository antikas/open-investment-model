"""SO-12.1-04 — read the E-05 Transaction records (per portfolio, as-of).

SD-12.1 IBOR owns E-05 Transaction (model/entities/core/E-05-transaction.md: "transactions update
the book of record"); its *transaction posting* Service Operation applies each event to the book.
This tool reads the E-05 records the IBOR book is built from — the trade / subscription /
capital-call / income events — at an as-of date, for a portfolio. Reconciliation's
transaction-matching leg (OIM-162) consumes this read: the IBOR transaction set is one side of the
match against the external comparator feed.

"As-of" for an event read means the events whose ``trade_date`` is on or before the as-of (the book
is built from the events captured up to the read date). The data-access layer applies the filter;
this tool types, orders and summarises the rows.

Pure and deterministic: no I/O, no clock, no RNG.

Honest boundary: a correct read over the OIM-160 **synthetic** internal book, not a production
transaction feed.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class TransactionRow(BaseModel):
    """One E-05 Transaction row — column-faithful to the E-05 attribute schema."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    transaction_id: str = Field(description="Primary key.")
    transaction_type: str = Field(
        description="'trade' / 'subscription' / 'redemption' / 'capital_call' / 'distribution' / "
        "'corporate_action' / 'transfer' / 'fee' / 'income'."
    )
    portfolio_id: str = Field(description="The portfolio affected (E-03).")
    instrument_id: str = Field(description="The instrument or asset transacted (E-02).")
    trade_date: date = Field(description="When the transaction was agreed.")
    settlement_date: date | None = Field(
        default=None, description="When it settles; null for events without a settlement."
    )
    quantity: Decimal | None = Field(default=None, description="Units transacted, where set.")
    amount_usd: Decimal = Field(description="The cash amount of the transaction, signed.")
    status: str = Field(description="'pending' / 'confirmed' / 'settled' / 'cancelled'.")
    source: str = Field(description="The source the transaction was captured from.")


class ReadTransactionsInput(BaseModel):
    """Inputs to the E-05 Transaction read — the portfolio, the as-of, the rows."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    portfolio_id: str = Field(description="The portfolio whose transactions to read.")
    as_of_date: date = Field(description="Read the events with trade_date on or before this date.")
    rows: tuple[TransactionRow, ...] = Field(
        default=(),
        description="The E-05 rows for the portfolio at the as-of, from the data-access layer.",
    )


class ReadTransactionsOutput(BaseModel):
    """The E-05 Transaction read — the rows ordered, plus the count + net signed amount."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    portfolio_id: str = Field(description="The portfolio.")
    as_of_date: date = Field(description="The as-of date the read honoured.")
    n_transactions: int = Field(description="The number of transactions read.")
    net_amount_usd: Decimal = Field(description="Σ the signed transaction amounts.")
    transactions: tuple[TransactionRow, ...] = Field(
        description="The transactions, ordered by transaction_id."
    )


def read_transactions(inp: ReadTransactionsInput) -> ReadTransactionsOutput:
    """Read the E-05 Transaction records for a portfolio as of the date. SO-12.1-04.

    Pure and deterministic: orders the rows by ``transaction_id`` and sums the signed amounts. The
    data-access layer applies the as-of filter (``trade_date <= as_of``); this tool shapes the rows.
    """
    ordered = tuple(sorted(inp.rows, key=lambda r: r.transaction_id))
    net = sum((r.amount_usd for r in ordered), Decimal(0))
    return ReadTransactionsOutput(
        portfolio_id=inp.portfolio_id,
        as_of_date=inp.as_of_date,
        n_transactions=len(ordered),
        net_amount_usd=net,
        transactions=ordered,
    )
