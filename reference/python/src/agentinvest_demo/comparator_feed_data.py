"""The external comparator-feed reader — the custodian + administrator records, READ-ONLY.

This is the **outside-data** end of the reconciliation engine (Helland: data-on-the-outside
is immutable, identified, as-of; it crosses the service boundary as a fact the firm reconciles its
*inside* book against). It reads the synthetic external comparator feed from the dbt-built
canonical store:

- the **custodian holdings** (``stg_custodian_holdings`` — one position-id-aligned row per holding,
  the position-reconciliation counter-record);
- the **custodian cash** balances (``stg_custodian_cash`` — one per fund);
- the **administrator statement** lines (``stg_admin_statement`` — transaction lines + cash lines,
  the transaction-matching + cash-reconciliation counter-records).

WHY A SEPARATE READER (not ``book_of_record_data``). ``book_of_record_data`` is the *internal* dual
book reader, and its load-bearing invariant is that it reads the internal book ONLY — never the
comparator feed (the read services must not see the answer side). The reconciliation engine
reconciles the internal book (read via ``book_of_record_data``) AGAINST the outside data (read
here). Keeping the two readers separate keeps that invariant honest: the internal-book read stays
comparator-blind, and this reader is the explicit outside-data seam. It REUSES ``marts.py``'s
store-path resolution + ``_connect`` + the ``MartsUnavailableError`` contract — one store
convention, not two.

READ-ONLY. The connection is opened ``read_only=True`` (via ``marts._connect``); this module never
writes, never mutates. All queries are parameterised (the as-of is a bound parameter, never
interpolated) — no injection surface.

NOT THE ORACLE. This reader reads the *feed* (the custodian/administrator records the engine
reconciles). It deliberately does **not** read ``break_labels.{csv,json}`` (the labelled-break
manifest) — that manifest is the eval's ground truth (the score key), not an engine input.
The engine classifies breaks deterministically from the feed's observable evidence, never by reading
the answer key. (``break_note`` IS a column on ``stg_custodian_holdings``, but the engine's
deterministic classifier does not use it as the cause signal — it derives the cause from neutral
observable evidence: the quantity/value differences, the in-flight trades, and the FX-translation
ratio cluster. See the engine's rule-classifier docstring.)

SYNTHETIC, NOT A LIVE CUSTODIAN. The comparator feed is the synthetic custodian/admin
feed; a green read proves the typed outside-data read + the as-of plumbing, NOT a read against a
live custodian or a production reconciliation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

# Reuse marts.py's store-path resolution + connect + the unavailable-store contract (the SSOT for
# "where is the canonical store" and "the data layer is not provisioned"). One convention.
from agentinvest_demo.marts import (
    MartsUnavailableError,
    _connect,
    resolve_duckdb_path,
)


@dataclass(frozen=True)
class CustodianHoldingRow:
    """One custodian holdings record — the position-reconciliation counter-record (outside data)."""

    custodian_record_id: str
    custodian: str
    position_id: str
    portfolio_id: str
    instrument_id: str
    as_of_date: date
    quantity: Decimal | None
    market_value_usd: Decimal
    currency: str


@dataclass(frozen=True)
class CustodianCashRow:
    """One custodian cash-balance record — one balance per fund (outside data)."""

    custodian_cash_id: str
    custodian: str
    portfolio_id: str
    as_of_date: date
    balance_usd: Decimal
    currency: str


@dataclass(frozen=True)
class AdminStatementRow:
    """One administrator-statement line — a transaction line or a cash line (outside data)."""

    admin_record_id: str
    record_type: str  # 'transaction' | 'cash'
    portfolio_id: str
    instrument_id: str | None
    as_of_date: date
    amount_usd: Decimal
    currency: str
    ref: str | None


def _d(value: object) -> Decimal | None:
    """Coerce a numeric cell to an exact ``Decimal`` (no float drift); ``None`` stays ``None``."""
    if value is None:
        return None
    return Decimal(str(value))


def read_custodian_holdings(
    as_of_date: str,
    duckdb_path: Path | None = None,
) -> list[CustodianHoldingRow]:
    """Read the custodian holdings records as of ``as_of_date`` — READ-ONLY, parameterised.

    The position-reconciliation counter-record: one position-id-aligned row per holding (one
    custodian row per holding). The as-of is a bound parameter. ``break_note`` is NOT
    projected — the engine classifies from neutral observable evidence, not the injected label.
    """
    path = duckdb_path or resolve_duckdb_path()
    con = _connect(path)
    try:
        rows = con.execute(
            """
            select
                custodian_record_id, custodian, position_id, portfolio_id, instrument_id,
                as_of_date, quantity, market_value_usd, currency
            from main_staging.stg_custodian_holdings
            where as_of_date = ?
            order by position_id
            """,
            [as_of_date],
        ).fetchall()
    finally:
        con.close()
    return [
        CustodianHoldingRow(
            custodian_record_id=str(r[0]),
            custodian=str(r[1]),
            position_id=str(r[2]),
            portfolio_id=str(r[3]),
            instrument_id=str(r[4]),
            as_of_date=r[5],
            quantity=_d(r[6]),
            market_value_usd=Decimal(str(r[7])),
            currency=str(r[8]),
        )
        for r in rows
    ]


def read_custodian_cash(
    as_of_date: str,
    duckdb_path: Path | None = None,
) -> list[CustodianCashRow]:
    """Read the custodian cash balances as of ``as_of_date`` — READ-ONLY, parameterised."""
    path = duckdb_path or resolve_duckdb_path()
    con = _connect(path)
    try:
        rows = con.execute(
            """
            select custodian_cash_id, custodian, portfolio_id, as_of_date, balance_usd, currency
            from main_staging.stg_custodian_cash
            where as_of_date = ?
            order by portfolio_id
            """,
            [as_of_date],
        ).fetchall()
    finally:
        con.close()
    return [
        CustodianCashRow(
            custodian_cash_id=str(r[0]),
            custodian=str(r[1]),
            portfolio_id=str(r[2]),
            as_of_date=r[3],
            balance_usd=Decimal(str(r[4])),
            currency=str(r[5]),
        )
        for r in rows
    ]


def read_admin_statement(
    as_of_date: str,
    record_type: str | None = None,
    duckdb_path: Path | None = None,
) -> list[AdminStatementRow]:
    """Read the administrator-statement lines — READ-ONLY, parameterised.

    Optionally filtered to a ``record_type`` ('transaction' / 'cash'). Transaction lines carry the
    trade as-of (not the read as-of), so the transaction read does NOT filter on the read as-of —
    a ``record_type='transaction'`` read returns every transaction line; a ``record_type='cash'``
    read filters on the read as-of (the cash balances are as-of-dated). ``record_type=None`` returns
    all lines unfiltered on date. An invalid ``record_type`` is a clean ``MartsUnavailableError``.
    """
    if record_type is not None and record_type not in ("transaction", "cash"):
        raise MartsUnavailableError(
            f"unknown admin record_type {record_type!r} — expected 'transaction' or 'cash'."
        )
    path = duckdb_path or resolve_duckdb_path()
    con = _connect(path)
    try:
        if record_type == "cash":
            rows = con.execute(
                """
                select admin_record_id, record_type, portfolio_id, instrument_id, as_of_date,
                    amount_usd, currency, ref
                from main_staging.stg_admin_statement
                where record_type = 'cash' and as_of_date = ?
                order by admin_record_id
                """,
                [as_of_date],
            ).fetchall()
        elif record_type == "transaction":
            rows = con.execute(
                """
                select admin_record_id, record_type, portfolio_id, instrument_id, as_of_date,
                    amount_usd, currency, ref
                from main_staging.stg_admin_statement
                where record_type = 'transaction'
                order by admin_record_id
                """
            ).fetchall()
        else:
            rows = con.execute(
                """
                select admin_record_id, record_type, portfolio_id, instrument_id, as_of_date,
                    amount_usd, currency, ref
                from main_staging.stg_admin_statement
                order by admin_record_id
                """
            ).fetchall()
    finally:
        con.close()
    return [
        AdminStatementRow(
            admin_record_id=str(r[0]),
            record_type=str(r[1]),
            portfolio_id=str(r[2]),
            instrument_id=None if r[3] is None else str(r[3]),
            as_of_date=r[4],
            amount_usd=Decimal(str(r[5])),
            currency=str(r[6]),
            ref=None if r[7] is None else str(r[7]),
        )
        for r in rows
    ]
