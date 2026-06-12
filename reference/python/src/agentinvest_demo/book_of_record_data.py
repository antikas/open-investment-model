"""The book-of-record canonical read — the SD-12.1 IBOR + SD-12.2 ABOR dual book, READ-ONLY.

This is the **data** end the BD-12 read tools draw on. It reads the OIM-160 canonical dual book
from the dbt-built canonical store (the same duckdb file the NAV-strike marts read from) and hands
typed rows to the pure ``bd12`` tools, at a requested as-of date, per book, per portfolio:

- the per-book **position** rows (E-04, key-partitioned by ``book`` — the genuinely-divergent IBOR
  and ABOR views), read from ``int_position_valuation`` (the (position_id, book) grain the holdings
  mart and the NAV roll-up read);
- the **E-05 Transaction** rows and the **E-06 Cash Flow Event** rows (owned by SD-12.1 IBOR),
  read from the realised staging entities;
- the **in-flight** (agreed-but-unsettled) transactions — E-05 ``pending`` / ``confirmed`` with a
  settlement date after the as-of — that drive the TD/SD-timing divergence;
- the latest struck **ABOR book date** (for the derived book-close state).

WHY A SEPARATE READER (not ``marts.py`` / ``nav_marts_read.py`` / ``canonical_inspect.py``). Those
readers are NAV/return/inspector-specific. This is the book-of-record read — the per-book E-04
partition + the E-05/E-06 records — which is a distinct read. It REUSES ``marts.py``'s
store-path resolution + ``_connect`` + the ``MartsUnavailableError`` contract (the SSOT for "where
is the canonical store" and "the data layer is not provisioned"), so there is one store convention,
not four.

READ-ONLY (the load-bearing safety property). The connection is opened ``read_only=True`` (via
``marts._connect``); this module never writes, never mutates, produces no E-24 break record, and
never reads the external comparator feed / ``break_labels`` (that is OIM-162's detector input). It
reads the *internal* dual book only. The as-of is honoured by filtering: positions to ``as_of_date
<= as_of``, transactions to ``trade_date <= as_of`` (with the in-flight set settling after), cash
flows to ``cash_flow_date <= as_of``. All queries are parameterised (the as-of and the portfolio
are bound parameters, never interpolated) — no injection surface.

SYNTHETIC, NOT A PRODUCTION BOOK OF RECORD. The dual book is the OIM-160 synthetic internal book;
a green read proves the typed per-book read + the as-of plumbing + the IBOR/ABOR divergence, NOT a
production book-of-record service or a read against a live custodian.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

# Reuse marts.py's store-path resolution + connect + the unavailable-store contract — the SSOT for
# "where is the canonical store" and "the data layer is not provisioned". One convention.
from agentinvest_demo.marts import (
    MartsUnavailableError,
    _connect,  # the read-only connect helper (lazy duckdb import → catchable error)
    resolve_duckdb_path,
)

# The book discriminator E-04 is key-partitioned by (model/entities/core/E-04-holding-position.md).
Book = str  # 'ibor' | 'abor' — validated against the tool's Literal at the boundary

# The in-flight transaction statuses — agreed but not yet settled (the TD/SD-timing drivers).
_IN_FLIGHT_STATUSES = ("pending", "confirmed")


def _validate_book(book: str) -> str:
    """Reject an unknown book before any read — only 'ibor' / 'abor' are valid E-04 partitions."""
    if book not in ("ibor", "abor"):
        raise MartsUnavailableError(
            f"unknown book {book!r}: E-04 is partitioned into 'ibor' and 'abor' only "
            "(model/entities/core/E-04-holding-position.md)."
        )
    return book


@dataclass(frozen=True)
class BorPositionRow:
    """One E-04 position row on a named book at the as-of — the position-read input grain."""

    position_id: str
    book: str
    portfolio_id: str
    instrument_id: str
    instrument_name: str | None
    asset_class_code: str | None
    as_of_date: date
    quantity: Decimal | None
    commitment_usd: Decimal | None
    cost_basis_usd: Decimal | None
    market_value_usd: Decimal
    accrued_income_usd: Decimal | None
    currency: str


@dataclass(frozen=True)
class BorTransactionRow:
    """One E-05 Transaction row — the transaction-read / pending-activity input grain."""

    transaction_id: str
    transaction_type: str
    portfolio_id: str
    instrument_id: str
    trade_date: date
    settlement_date: date | None
    quantity: Decimal | None
    amount_usd: Decimal
    status: str
    source: str


@dataclass(frozen=True)
class BorCashFlowRow:
    """One E-06 Cash Flow Event row — the cash-flow-read input grain."""

    cash_flow_id: str
    portfolio_id: str
    instrument_id: str | None
    transaction_id: str | None
    cash_flow_date: date
    cash_flow_type: str
    direction: str
    amount: Decimal
    currency: str
    source: str


def _d(value: object) -> Decimal | None:
    """Coerce a numeric cell to an exact ``Decimal`` (no float drift); ``None`` stays ``None``."""
    if value is None:
        return None
    return Decimal(str(value))


def list_portfolios(duckdb_path: Path | None = None) -> list[str]:
    """Return the portfolio ids present in the dual book, ordered — the read candidates."""
    path = duckdb_path or resolve_duckdb_path()
    con = _connect(path)
    try:
        rows = con.execute(
            "select distinct portfolio_id from main_staging.stg_e04_holding_position "
            "order by portfolio_id"
        ).fetchall()
    finally:
        con.close()
    return [str(r[0]) for r in rows]


def read_positions(
    book: str,
    portfolio_id: str,
    as_of_date: str,
    duckdb_path: Path | None = None,
) -> list[BorPositionRow]:
    """Read the E-04 positions on ``book`` for ``portfolio_id`` as of ``as_of_date`` — READ-ONLY.

    Reads ``int_position_valuation`` (the (position_id, book) grain) filtered to the named book +
    portfolio, with ``as_of_date <= the requested as-of`` (the position snapshot up to the read
    date). The book + portfolio + as-of are bound parameters (never interpolated). The IBOR read and
    the ABOR read of the same portfolio return genuinely-different rows on the OIM-160 dual book.
    """
    _validate_book(book)
    path = duckdb_path or resolve_duckdb_path()
    con = _connect(path)
    try:
        rows = con.execute(
            """
            select
                position_id, book, portfolio_id, instrument_id, instrument_name,
                asset_class_code, as_of_date, quantity, commitment_usd, cost_basis_usd,
                e04_market_value_usd, accrued_income_usd, currency
            from main_intermediate.int_position_valuation
            where book = ?
              and portfolio_id = ?
              and as_of_date <= ?
            order by position_id
            """,
            [book, portfolio_id, as_of_date],
        ).fetchall()
    finally:
        con.close()

    return [
        BorPositionRow(
            position_id=str(r[0]),
            book=str(r[1]),
            portfolio_id=str(r[2]),
            instrument_id=str(r[3]),
            instrument_name=None if r[4] is None else str(r[4]),
            asset_class_code=None if r[5] is None else str(r[5]),
            as_of_date=r[6],
            quantity=_d(r[7]),
            commitment_usd=_d(r[8]),
            cost_basis_usd=_d(r[9]),
            market_value_usd=Decimal(str(r[10])),
            accrued_income_usd=_d(r[11]),
            currency=str(r[12]),
        )
        for r in rows
    ]


def read_transactions(
    portfolio_id: str,
    as_of_date: str,
    duckdb_path: Path | None = None,
) -> list[BorTransactionRow]:
    """Read the E-05 Transactions for ``portfolio_id`` with ``trade_date <= as_of`` — READ-ONLY.

    The events the IBOR book is built from up to the read date (SD-12.1 owns E-05). Parameterised.
    """
    path = duckdb_path or resolve_duckdb_path()
    con = _connect(path)
    try:
        rows = con.execute(
            """
            select
                transaction_id, transaction_type, portfolio_id, instrument_id, trade_date,
                settlement_date, quantity, amount_usd, status, source
            from main_staging.stg_e05_transaction
            where portfolio_id = ?
              and trade_date <= ?
            order by transaction_id
            """,
            [portfolio_id, as_of_date],
        ).fetchall()
    finally:
        con.close()

    return [_transaction_row(r) for r in rows]


def read_pending_activity(
    portfolio_id: str,
    as_of_date: str,
    duckdb_path: Path | None = None,
) -> list[BorTransactionRow]:
    """Read the in-flight E-05 transactions (settling after the as-of; not settled). READ-ONLY.

    The IBOR pending-activity set: ``status in ('pending','confirmed')`` AND ``settlement_date >
    as_of`` (agreed but not yet settled at the read date) — the TD/SD-timing drivers the IBOR book
    carries that the ABOR book does not yet. Parameterised.
    """
    path = duckdb_path or resolve_duckdb_path()
    con = _connect(path)
    try:
        rows = con.execute(
            """
            select
                transaction_id, transaction_type, portfolio_id, instrument_id, trade_date,
                settlement_date, quantity, amount_usd, status, source
            from main_staging.stg_e05_transaction
            where portfolio_id = ?
              and status in ('pending', 'confirmed')
              and settlement_date > ?
            order by transaction_id
            """,
            [portfolio_id, as_of_date],
        ).fetchall()
    finally:
        con.close()

    return [_transaction_row(r) for r in rows]


def _transaction_row(r: tuple[object, ...]) -> BorTransactionRow:
    return BorTransactionRow(
        transaction_id=str(r[0]),
        transaction_type=str(r[1]),
        portfolio_id=str(r[2]),
        instrument_id=str(r[3]),
        trade_date=r[4],  # type: ignore[arg-type]
        settlement_date=None if r[5] is None else r[5],  # type: ignore[arg-type]
        quantity=_d(r[6]),
        amount_usd=Decimal(str(r[7])),
        status=str(r[8]),
        source=str(r[9]),
    )


def read_cash_flows(
    portfolio_id: str,
    as_of_date: str,
    duckdb_path: Path | None = None,
) -> list[BorCashFlowRow]:
    """Read the E-06 Cash Flow Events for ``portfolio_id`` (``cash_flow_date <= as_of``). READ-ONLY.

    The realised cash movements up to the read date (SD-12.1 owns E-06). Parameterised.
    """
    path = duckdb_path or resolve_duckdb_path()
    con = _connect(path)
    try:
        rows = con.execute(
            """
            select
                cash_flow_id, portfolio_id, instrument_id, transaction_id, cash_flow_date,
                cash_flow_type, direction, amount, currency, source
            from main_staging.stg_e06_cash_flow_event
            where portfolio_id = ?
              and cash_flow_date <= ?
            order by cash_flow_id
            """,
            [portfolio_id, as_of_date],
        ).fetchall()
    finally:
        con.close()

    return [
        BorCashFlowRow(
            cash_flow_id=str(r[0]),
            portfolio_id=str(r[1]),
            instrument_id=None if r[2] is None else str(r[2]),
            transaction_id=None if r[3] is None else str(r[3]),
            cash_flow_date=r[4],
            cash_flow_type=str(r[5]),
            direction=str(r[6]),
            amount=Decimal(str(r[7])),
            currency=str(r[8]),
            source=str(r[9]),
        )
        for r in rows
    ]


def latest_struck_book_date(book: str, duckdb_path: Path | None = None) -> date:
    """Return the latest E-04 ``as_of_date`` for ``book`` (the struck date for the close-state).

    The canonical layer carries no seeded period-lock state machine; the book-close state is
    derived from this latest struck date (a period is closed/locked iff its as-of <= this date).
    Read-only, parameterised. A book with no rows is a clean ``MartsUnavailableError`` (no fake).
    """
    _validate_book(book)
    path = duckdb_path or resolve_duckdb_path()
    con = _connect(path)
    try:
        row = con.execute(
            "select max(as_of_date) from main_staging.stg_e04_holding_position where book = ?",
            [book],
        ).fetchone()
    finally:
        con.close()
    if row is None or row[0] is None:
        raise MartsUnavailableError(
            f"the {book!r} book carries no positions — is the store built (pnpm dbt:build, from "
            "reference/)? Cannot derive the book-close state with no struck book date."
        )
    return row[0]  # type: ignore[no-any-return]
