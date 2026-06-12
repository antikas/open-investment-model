"""SO-12.1-01 / SO-12.2-01 — read the book-of-record position (per book, per portfolio, as-of).

The shared **position read** tool for both books of record. SD-12.1 IBOR's *position keeping* /
*position-data distribution* and SD-12.2 ABOR's *accounting-basis position keeping* are the same
shape of read — "what does this portfolio hold, on this book, as of this date" — over the E-04
Holding / Position entity, which is key-partitioned by ``book`` (``(position_id, book)`` is the
identity). The same logical holding carries an IBOR row and an ABOR row that genuinely diverge
(model/entities/core/E-04-holding-position.md), so the ``book`` discriminator is a required input,
not an afterthought: the IBOR read and the ABOR read of the same portfolio return different
quantities, market values, cost bases and accruals on the OIM-160 dual book.

Pure and deterministic: the rows are read by the book-of-record data-access layer
(``book_of_record_data``) at the requested as-of and passed in; this tool only types,
orders and totals them. No I/O, no clock, no RNG — the output is a function of the input alone.

Honest boundary: this is a *correct read* over the OIM-160 **synthetic** internal dual book (the
dbt canonical layer), never a production book-of-record service and never a read against a live
custodian. A green read proves the typed per-book read + the as-of plumbing, not a fiduciary
position.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# The two books of record E-04 is partitioned by (model/entities/core/E-04-holding-position.md).
# ``ibor`` is the real-time front-office book; ``abor`` is the accounting-basis book.
Book = Literal["ibor", "abor"]


class PositionRow(BaseModel):
    """One E-04 Holding / Position row on a named book, at the as-of date.

    Column-faithful to the E-04 attribute schema (the position grain the data-access layer reads
    from the canonical ``int_position_valuation`` / ``stg_e04_holding_position``).
    ``accrued_income_usd`` is carried because it is an ABOR-book attribute (null on the IBOR book)
    and is one of the three OIM-160 divergence classes; ``quantity`` and ``market_value_usd`` carry
    the TD/SD-timing divergence; ``cost_basis_usd`` the cost-basis divergence.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    position_id: str = Field(description="The logical-holding identity (shared across both books).")
    book: Book = Field(description="The book of record this row belongs to — 'ibor' or 'abor'.")
    portfolio_id: str = Field(description="The portfolio the position sits in (E-03).")
    instrument_id: str = Field(description="The instrument or asset held (E-02).")
    instrument_name: str | None = Field(
        default=None, description="The instrument's display name, where the layer carries it."
    )
    asset_class_code: str | None = Field(
        default=None, description="The asset-class code (E-09), where resolved."
    )
    as_of_date: date = Field(description="The date the position is as of.")
    quantity: Decimal | None = Field(
        default=None, description="Units held, where the instrument is quantity-denominated."
    )
    commitment_usd: Decimal | None = Field(
        default=None, description="Committed amount, where the instrument is a fund interest."
    )
    cost_basis_usd: Decimal | None = Field(default=None, description="The position's cost basis.")
    market_value_usd: Decimal = Field(description="The position's market value on this book.")
    accrued_income_usd: Decimal | None = Field(
        default=None, description="Accrued-but-unpaid income — an ABOR attribute (null on IBOR)."
    )
    currency: str = Field(description="The position's currency.")


class ReadPositionInput(BaseModel):
    """Inputs to a book-of-record position read — the book, the portfolio, the as-of, the rows."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    book: Book = Field(description="Which book of record to read — 'ibor' or 'abor'.")
    portfolio_id: str = Field(description="The portfolio whose positions to read.")
    as_of_date: date = Field(description="Read the positions as of this date.")
    rows: tuple[PositionRow, ...] = Field(
        default=(),
        description="The E-04 rows for this (book, portfolio) at the as-of, from the data layer.",
    )


class ReadPositionOutput(BaseModel):
    """The typed per-book position read — the rows ordered, plus the book-level totals."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    book: Book = Field(description="The book this read is for.")
    portfolio_id: str = Field(description="The portfolio read.")
    as_of_date: date = Field(description="The as-of date the read honoured.")
    n_positions: int = Field(description="The number of positions on this book for the portfolio.")
    total_market_value_usd: Decimal = Field(description="Σ market value over the positions (book).")
    total_accrued_income_usd: Decimal = Field(
        description="Σ accrued income (zero on the IBOR book; the ABOR accrual on the ABOR book)."
    )
    positions: tuple[PositionRow, ...] = Field(description="The positions, ordered by position_id.")


def read_position(inp: ReadPositionInput) -> ReadPositionOutput:
    """Type, order and total the book-of-record position rows for one (book, portfolio, as-of).

    SO-12.1-01 (IBOR) / SO-12.2-01 (ABOR) — the same read shape over E-04, by ``book``.
    Pure and deterministic: it sums the market value and accrued income and orders the rows by
    ``position_id`` (a stable, RNG-free order). The rows themselves are read by the data-access
    layer at the requested as-of; this tool does not query — it shapes the typed result.

    The book-divergence is structural: the IBOR read of a portfolio and the ABOR read of the same
    portfolio at the same as-of return different totals on the OIM-160 dual book (the TD/SD-timing,
    accrual and cost-basis classes), because the data-access layer reads the ``book``-specific E-04
    partition. This tool does not reconcile the two — that is a later cycle; it exposes each book.
    """
    ordered = tuple(sorted(inp.rows, key=lambda r: r.position_id))
    total_mv = sum((r.market_value_usd for r in ordered), Decimal(0))
    total_accrued = sum(
        (r.accrued_income_usd for r in ordered if r.accrued_income_usd is not None), Decimal(0)
    )
    return ReadPositionOutput(
        book=inp.book,
        portfolio_id=inp.portfolio_id,
        as_of_date=inp.as_of_date,
        n_positions=len(ordered),
        total_market_value_usd=total_mv,
        total_accrued_income_usd=total_accrued,
        positions=ordered,
    )
