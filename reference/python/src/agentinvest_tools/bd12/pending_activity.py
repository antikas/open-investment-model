"""SO-12.1-03 — read the IBOR pending activity (the unsettled / in-flight trades, as-of).

SD-12.1 IBOR's *pending-activity tracking* Service Operation: the trades that are agreed but not
yet settled (and, in the full model, announced-but-unpaid corporate actions and income), held as
projected adjustments to the current position. These are the E-05 ``pending`` / ``confirmed``
transactions whose ``settlement_date`` is after the read as-of — the in-flight set that drives the
TD/SD-timing divergence between the IBOR book (which carries them on trade date) and the ABOR book
(which recognises them only on settlement). Exposing this read is what lets OIM-162's
transaction-matching leg reason about what the IBOR book holds that the ABOR book does not yet.

Pure and deterministic: the in-flight transactions are read by the data-access layer (filtered to
``settlement_date > as_of`` and ``status in (pending, confirmed)``) and passed in; this tool types,
orders and counts them. No I/O, no clock, no RNG.

Honest boundary: a correct read over the OIM-160 **synthetic** internal book, not a production
pending-activity feed.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PendingStatus = Literal["pending", "confirmed"]


class PendingTransaction(BaseModel):
    """One in-flight E-05 transaction — agreed (pending/confirmed), not yet settled at the as-of."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    transaction_id: str = Field(description="The transaction (E-05).")
    transaction_type: str = Field(description="The transaction type — 'trade', etc.")
    portfolio_id: str = Field(description="The portfolio affected (E-03).")
    instrument_id: str = Field(description="The instrument transacted (E-02).")
    trade_date: date = Field(description="When the transaction was agreed.")
    settlement_date: date = Field(description="When it settles — after the as-of (in-flight).")
    quantity: Decimal | None = Field(default=None, description="Units transacted, where set.")
    amount_usd: Decimal = Field(description="The signed cash amount of the transaction.")
    status: PendingStatus = Field(description="'pending' or 'confirmed' — agreed, not yet settled.")


class ReadPendingActivityInput(BaseModel):
    """Inputs to the IBOR pending-activity read — the portfolio, the as-of, the in-flight rows."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    portfolio_id: str = Field(description="The portfolio whose pending activity to read.")
    as_of_date: date = Field(description="Read the activity in-flight as of this date.")
    transactions: tuple[PendingTransaction, ...] = Field(
        default=(),
        description="The in-flight (settlement after the as-of) E-05 rows from the data layer.",
    )


class ReadPendingActivityOutput(BaseModel):
    """The IBOR pending activity — the in-flight transactions ordered, plus count + cash impact."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    portfolio_id: str = Field(description="The portfolio.")
    as_of_date: date = Field(description="The as-of date the read honoured.")
    n_pending: int = Field(description="The number of in-flight transactions.")
    net_cash_impact_usd: Decimal = Field(
        description="Σ the signed transaction amounts — the net projected cash impact on settle."
    )
    transactions: tuple[PendingTransaction, ...] = Field(
        description="The in-flight transactions, ordered by transaction_id."
    )


def read_ibor_pending_activity(inp: ReadPendingActivityInput) -> ReadPendingActivityOutput:
    """Read the IBOR pending activity — the agreed-but-unsettled trades as of the date. SO-12.1-03.

    Pure and deterministic: orders the in-flight transactions by ``transaction_id`` (stable,
    RNG-free) and sums their signed amounts into the net cash impact. The data-access layer applies
    the in-flight filter (``settlement_date > as_of`` and ``status in (pending, confirmed)``); this
    tool shapes the typed result.
    """
    ordered = tuple(sorted(inp.transactions, key=lambda t: t.transaction_id))
    net = sum((t.amount_usd for t in ordered), Decimal(0))
    return ReadPendingActivityOutput(
        portfolio_id=inp.portfolio_id,
        as_of_date=inp.as_of_date,
        n_pending=len(ordered),
        net_cash_impact_usd=net,
        transactions=ordered,
    )
