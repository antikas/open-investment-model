"""SO-12.2-03 — read the ABOR cost basis / lot (per portfolio, as-of).

SD-12.2 ABOR's *cost-basis and lot accounting* Service Operation: the cost basis of each position
(and, where required, tax-lot detail), so realised and unrealised gain is correctly measured. The
ABOR cost basis is one of the three OIM-160 divergence classes — for some holdings the accounting
book carries a cost basis that differs from the IBOR book's (an accounting reclassification /
restatement the front-office book has not applied). Exposing this read gives OIM-162 a typed view
of the cost-basis the two books differ by, and the unrealised gain the ABOR book measures.

The v0.1 grain is the position-level cost basis (E-04 ``cost_basis_usd``); lot-level detail is an
E-04 open extension (model/entities/core/E-04-holding-position.md "Lot-level detail for tax-lot
accounting") and is not seeded — the tool reports the position-grain cost basis and unrealised gain
honestly, with no fabricated lots.

Pure and deterministic: the per-position cost basis + market value are read by the data-access
layer from the ABOR partition at the as-of and passed in; this tool types, orders and totals them,
and derives the unrealised gain. No I/O, no clock, no RNG.

Honest boundary: a correct read over the OIM-160 **synthetic** internal accounting book, not a
production cost-basis / tax-lot ledger.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CostBasisRow(BaseModel):
    """One position's ABOR cost basis + market value at the as-of (position grain; no lots)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    position_id: str = Field(description="The logical-holding identity.")
    portfolio_id: str = Field(description="The portfolio the position sits in (E-03).")
    instrument_id: str = Field(description="The instrument held (E-02).")
    cost_basis_usd: Decimal = Field(description="The ABOR cost basis of the position.")
    market_value_usd: Decimal = Field(description="The ABOR market value of the position.")
    unrealised_gain_usd: Decimal = Field(
        description="market_value − cost_basis — the unrealised gain the ABOR book measures."
    )
    currency: str = Field(description="The currency.")


class ReadCostBasisInput(BaseModel):
    """Inputs to the ABOR cost-basis read — the portfolio, the as-of, the rows."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    portfolio_id: str = Field(description="The portfolio whose cost basis to read.")
    as_of_date: date = Field(description="Read the cost basis as of this date.")
    rows: tuple[CostBasisRow, ...] = Field(
        default=(),
        description="The ABOR positions' cost basis + market value, from the data-access layer.",
    )


class ReadCostBasisOutput(BaseModel):
    """The ABOR cost basis — the per-position rows ordered, plus the totals + unrealised gain."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    portfolio_id: str = Field(description="The portfolio.")
    as_of_date: date = Field(description="The as-of date the read honoured.")
    n_positions: int = Field(description="The number of positions read.")
    total_cost_basis_usd: Decimal = Field(description="Σ the cost basis over the positions.")
    total_market_value_usd: Decimal = Field(description="Σ the ABOR market value over positions.")
    total_unrealised_gain_usd: Decimal = Field(description="Σ the unrealised gain (MV − cost).")
    positions: tuple[CostBasisRow, ...] = Field(description="The positions, by position_id.")


def read_abor_cost_basis(inp: ReadCostBasisInput) -> ReadCostBasisOutput:
    """Read the ABOR cost basis / unrealised gain for a portfolio as of the date. SO-12.2-03.

    Pure and deterministic: orders the rows by ``position_id`` and totals the cost basis, market
    value and unrealised gain. The data-access layer reads the ABOR partition of E-04 (the position
    grain — lot detail is an unseeded open extension); this tool shapes the typed result.
    """
    ordered = tuple(sorted(inp.rows, key=lambda r: r.position_id))
    total_cost = sum((r.cost_basis_usd for r in ordered), Decimal(0))
    total_mv = sum((r.market_value_usd for r in ordered), Decimal(0))
    total_gain = sum((r.unrealised_gain_usd for r in ordered), Decimal(0))
    return ReadCostBasisOutput(
        portfolio_id=inp.portfolio_id,
        as_of_date=inp.as_of_date,
        n_positions=len(ordered),
        total_cost_basis_usd=total_cost,
        total_market_value_usd=total_mv,
        total_unrealised_gain_usd=total_gain,
        positions=ordered,
    )
