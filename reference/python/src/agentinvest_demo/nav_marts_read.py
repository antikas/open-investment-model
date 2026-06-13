"""The NAV-strike workflow's marts read — the per-fund NAV components from ``mart_fund_nav``.

This is the **data** end the ``navCalculation`` workflow reads. The workflow journals a
NAV strike as durable steps (load-positions → price → apply-fees → roll-up → gate →
publish); each step is a checkpoint over a COMPONENT of the canonical fund NAV, and the
components are read HERE from the published ``mart_fund_nav`` mart so the workflow's
struck NAV **is** the mart's NAV, not a re-implementation:

    nav_usd = gross_market_value + accrued_income − fees          (the NAV identity)

The mart is the single source: ``gross_market_value`` (Σ each held position's mark),
``accrued_income`` (Σ abor accrued income), ``fees`` (structurally present, zero on this
synthetic seed), ``nav_usd`` (the published identity). The reader returns each as a string
(exact decimal, no float drift across the language boundary) plus the position count, so
the TS workflow can checkpoint each component AND assert its own roll-up equals the
mart's published ``nav_usd`` to the penny.

WHY A SEPARATE READER (not ``marts.py``). ``marts.py`` (the return read path) derives a
return over a *window* (two dates), reading the valuation *series*. The NAV strike needs a
single point-in-time **current strike** — the mart's own per-fund NAV row — which is a
different, smaller read. This module is that read; it does not duplicate the window
derivation. It reuses ``marts.py``'s store-path resolution + the ``MartsUnavailableError``
contract (the SSOT for "where is the canonical store" and "the data layer is not
provisioned"), so there is one store-resolution convention, not two.

THE STRIKE IS CURRENT-AS-OF ONLY (bounded, not silently struck).
``mart_fund_nav`` is as-of-capable on the valuation axis, but its HOLDINGS set is the
latest period-end only (E-04 carries no holding history), so a PAST-as-of strike on the
latest-holdings path has an unbounded constituent-set error. This reader therefore reads
the CURRENT strike (``nav_knowledge_date is null``) and refuses a past-as-of date with a
clear error — a correct past strike needs an as-of-holdings (holding-history) view, which
is a forward item. The default current strike is unaffected.

SYNTHETIC, NOT A STRUCK PRODUCTION NAV. A NAV read here proves the data-layer arithmetic
and the as-of plumbing; it is NOT a fiduciary published NAV (that is oracle-anchored,
shadow-pipeline-matched, GIPS/CFA-calibrated production work — the named arc). Treat the
components as the synthetic data foundation, never as a published NAV.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

# Reuse marts.py's store-path resolution + the unavailable-store contract — the SSOT for
# "where is the canonical store" and "the data layer is not provisioned". One convention.
from agentinvest_demo.marts import (
    MartsUnavailableError,
    _connect,  # the read-only connect helper (lazy duckdb import → catchable error)
    resolve_duckdb_path,
)


@dataclass(frozen=True)
class FundNavComponents:
    """The per-fund NAV components read from ``mart_fund_nav`` — the workflow's step inputs.

    Every money figure is an exact ``Decimal`` (no float). ``nav_usd`` is the mart's
    PUBLISHED identity value; ``gross_market_value + accrued_income - fees`` recomputes it
    and must equal it to the penny (the NAV invariant the workflow asserts at roll-up).
    """

    fund_id: str
    fund_name: str
    share_class: str | None
    n_positions: int
    gross_market_value: Decimal
    accrued_income: Decimal
    fees: Decimal
    nav_usd: Decimal


@dataclass(frozen=True)
class FundHoldingsGross:
    """The fund's gross market value re-derived INDEPENDENTLY from ``mart_portfolio_holdings``.

    The workflow's load-positions step rolls up the held positions' market values from the
    HOLDINGS mart — a DIFFERENT mart, built by a DIFFERENT SQL path than ``mart_fund_nav``'s
    gross (which sums the E-07 mark over the fund via a window-function selection). Summing
    the holdings mart's ``market_value_usd`` over the fund and reconciling it against
    ``mart_fund_nav.gross_market_value`` is the genuine, FALSIFIABLE cross-mart check
    (the ``assert_marts_reconcile_holdings_to_nav`` invariant): two marts, two paths,
    so a divergence (a dropped position, a double-counted book, a mis-summed mark) shows up.
    It is NOT the within-row ``X == X`` tautology of reading gross + nav from one row.
    """

    fund_id: str
    fund_name: str
    n_positions: int
    holdings_gross_market_value: Decimal


def list_fund_ids(duckdb_path: Path | None = None) -> list[str]:
    """Return the fund ids present in ``mart_fund_nav``, ordered — the strike candidates."""
    path = duckdb_path or resolve_duckdb_path()
    con = _connect(path)
    try:
        rows = con.execute(
            "select fund_id from main_marts.mart_fund_nav order by fund_id"
        ).fetchall()
    finally:
        con.close()
    return [str(r[0]) for r in rows]


def read_fund_nav_components(
    fund_id: str,
    *,
    nav_knowledge_date: str | None = None,
    duckdb_path: Path | None = None,
) -> FundNavComponents:
    """Read the per-fund NAV components for a CURRENT strike from ``mart_fund_nav``.

    The workflow checkpoints each returned component as a durable step and asserts its own
    roll-up (``gross_market_value + accrued_income - fees``) equals the mart's published
    ``nav_usd`` to the penny — proving the struck NAV IS the mart's NAV.

    A ``nav_knowledge_date`` other than None is REFUSED: the
    latest-holdings path cannot soundly strike a PAST as-of NAV (unbounded constituent-set
    error on real holding history); a correct past strike needs the as-of-holdings view
    (forward). The current strike is read from the default-built ``mart_fund_nav`` row
    (``nav_knowledge_date is null``).
    """
    if nav_knowledge_date is not None:
        raise MartsUnavailableError(
            f"a past-as-of NAV strike (nav_knowledge_date={nav_knowledge_date}) is NOT "
            "production-safe on the latest-holdings path (E-04 carries no holding history; "
            "the constituent set would be the latest set, not the as-of set — an unbounded "
            "error). Strike the CURRENT NAV (nav_knowledge_date=None); a past-as-of strike "
            "needs the as-of-holdings (holding-history) view, a forward item."
        )

    path = duckdb_path or resolve_duckdb_path()
    con = _connect(path)
    try:
        row = con.execute(
            """
            select
                fund_id,
                fund_name,
                share_class,
                n_positions,
                gross_market_value,
                accrued_income,
                fees,
                nav_usd
            from main_marts.mart_fund_nav
            where fund_id = ?
              and nav_knowledge_date is null
            """,
            [fund_id],
        ).fetchone()
    finally:
        con.close()

    if row is None:
        raise MartsUnavailableError(
            f"fund {fund_id} is not present in mart_fund_nav (current strike). Is the fund "
            f"id correct and the store built (pnpm dbt:build, from reference/)?"
        )

    return FundNavComponents(
        fund_id=str(row[0]),
        fund_name=str(row[1]),
        share_class=None if row[2] is None else str(row[2]),
        n_positions=int(row[3]),
        gross_market_value=Decimal(str(row[4])),
        accrued_income=Decimal(str(row[5])),
        fees=Decimal(str(row[6])),
        nav_usd=Decimal(str(row[7])),
    )


def read_fund_holdings_gross(
    fund_id: str,
    *,
    duckdb_path: Path | None = None,
) -> FundHoldingsGross:
    """Roll up the fund's gross market value from ``mart_portfolio_holdings`` — INDEPENDENTLY.

    Sums each held (abor) position's ``market_value_usd`` over the fund from the HOLDINGS
    mart. This is a DIFFERENT mart and a DIFFERENT SQL path from ``mart_fund_nav``'s
    ``gross_market_value`` (which the fund-NAV mart derives by a window-function mark
    selection rolled to the fund). The workflow's load-positions step uses THIS to derive the
    gross, then reconciles it against the fund-NAV mart's gross — the genuine cross-mart
    reconciliation (the ``assert_marts_reconcile_holdings_to_nav`` invariant, here
    exercised live in the workflow), NOT a within-row ``X == X`` re-read.

    The fund must be present in the holdings mart (a missing fund is a clean
    ``MartsUnavailableError``, not a silent zero — a zero-gross fund would otherwise mask a
    fund whose holdings did not load).
    """
    path = duckdb_path or resolve_duckdb_path()
    con = _connect(path)
    try:
        row = con.execute(
            """
            select
                fund_id,
                any_value(fund_name)        as fund_name,
                count(*)                    as n_positions,
                sum(market_value_usd)       as holdings_gross_market_value
            from main_marts.mart_portfolio_holdings
            where fund_id = ?
            group by fund_id
            """,
            [fund_id],
        ).fetchone()
    finally:
        con.close()

    if row is None or row[3] is None:
        raise MartsUnavailableError(
            f"fund {fund_id} has no holdings in mart_portfolio_holdings — is the fund id "
            f"correct and the store built (pnpm dbt:build, from reference/)? A NAV strike "
            f"cannot roll up positions for a fund absent from the holdings mart."
        )

    return FundHoldingsGross(
        fund_id=str(row[0]),
        fund_name=str(row[1]),
        n_positions=int(row[2]),
        holdings_gross_market_value=Decimal(str(row[3])),
    )
