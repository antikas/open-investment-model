"""SO-12.2-02 — read the ABOR accrued income (per portfolio, as-of).

SD-12.2 ABOR's *income and expense accrual* Service Operation: the interest / dividends / fees the
accounting book accrues between cash dates, so the book reflects earned-but-unreceived amounts.
This is one of the three OIM-160 divergence classes — the ABOR book carries an
``accrued_income_usd`` on E-04 that the IBOR book does not (E-04 places accruals on the ABOR
partition). Exposing this read gives OIM-162's reconciliation a typed view of the accrual
divergence.

Pure and deterministic: the per-position accrued amounts are read by the data-access layer from the
ABOR partition of E-04 at the as-of and passed in; this tool types, orders and totals them. No I/O,
no clock, no RNG.

Honest boundary: a correct read over the OIM-160 **synthetic** internal accounting book, not a
production accrual.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class AccruedIncomeRow(BaseModel):
    """One position's ABOR accrued-but-unpaid income at the as-of."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    position_id: str = Field(description="The logical-holding identity.")
    portfolio_id: str = Field(description="The portfolio the position sits in (E-03).")
    instrument_id: str = Field(description="The instrument held (E-02).")
    accrued_income_usd: Decimal = Field(description="The accrued-but-unpaid income (ABOR book).")
    currency: str = Field(description="The currency.")


class ReadAccruedIncomeInput(BaseModel):
    """Inputs to the ABOR accrued-income read — the portfolio, the as-of, the rows."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    portfolio_id: str = Field(description="The portfolio whose accrued income to read.")
    as_of_date: date = Field(description="Read the accruals as of this date.")
    rows: tuple[AccruedIncomeRow, ...] = Field(
        default=(),
        description="The ABOR positions carrying a non-null accrual, from the data layer.",
    )


class ReadAccruedIncomeOutput(BaseModel):
    """The ABOR accrued income — the per-position accruals ordered, plus the portfolio total."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    portfolio_id: str = Field(description="The portfolio.")
    as_of_date: date = Field(description="The as-of date the read honoured.")
    n_accruing_positions: int = Field(description="The number of positions carrying an accrual.")
    total_accrued_income_usd: Decimal = Field(description="Σ the accrued income over positions.")
    accruals: tuple[AccruedIncomeRow, ...] = Field(description="The accruals, by position_id.")


def read_abor_accrued_income(inp: ReadAccruedIncomeInput) -> ReadAccruedIncomeOutput:
    """Read the ABOR accrued income for a portfolio as of the date. SO-12.2-02.

    Pure and deterministic: orders the rows by ``position_id`` and totals the accrued income. The
    data-access layer reads the ABOR partition of E-04 (where ``accrued_income_usd`` is non-null);
    this tool shapes the typed result. The IBOR book carries no accrual — so this read has no IBOR
    twin, which is exactly the accrual divergence class.
    """
    ordered = tuple(sorted(inp.rows, key=lambda r: r.position_id))
    total = sum((r.accrued_income_usd for r in ordered), Decimal(0))
    return ReadAccruedIncomeOutput(
        portfolio_id=inp.portfolio_id,
        as_of_date=inp.as_of_date,
        n_accruing_positions=len(ordered),
        total_accrued_income_usd=total,
        accruals=ordered,
    )
