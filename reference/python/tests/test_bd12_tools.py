"""The BD-12 book-of-record read tools — pure-tool determinism + shaping correctness.

These tests drive the PURE ``bd12`` tools (no I/O): given typed rows in, each tool types, orders and
totals deterministically. They prove the contract the dispatch service relies on — same input →
same output, stable ordering, correct totals — without touching the canonical store (that is the
``test_bd12_service`` integration level, which reads the canonical fixtures). The ``bd09`` pure-tool
test pattern (``test_bd09_total_return`` et al.): determinism + a worked shaping example.

Honest boundary: a green pure-tool test proves the typed shaping; the read of the canonical dual
book and the IBOR-vs-ABOR divergence are proven at the service level over the canonical fixtures.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from agentinvest_tools.bd12 import (
    AccruedIncomeRow,
    CashFlowRow,
    CostBasisRow,
    PendingTransaction,
    PositionRow,
    ReadAccruedIncomeInput,
    ReadBookCloseStateInput,
    ReadCashExposureInput,
    ReadCashFlowsInput,
    ReadCostBasisInput,
    ReadPendingActivityInput,
    ReadPositionInput,
    ReadTransactionsInput,
    TransactionRow,
    UnsettledTradeLeg,
    read_abor_accrued_income,
    read_abor_book_close_state,
    read_abor_cost_basis,
    read_cash_flow_events,
    read_ibor_cash_and_exposure,
    read_ibor_pending_activity,
    read_position,
    read_transactions,
)

AS_OF = date(2026, 3, 31)


def _position(pid: str, book: str, mv: str, accrued: str | None = None) -> PositionRow:
    return PositionRow(
        position_id=pid,
        book=book,  # type: ignore[arg-type]
        portfolio_id="PF-0008",
        instrument_id="INS-0001",
        as_of_date=AS_OF,
        market_value_usd=Decimal(mv),
        accrued_income_usd=None if accrued is None else Decimal(accrued),
        currency="USD",
    )


# --- read_position (SO-12.1-01 / SO-12.2-01) -----------------------------------------------------


def test_read_position_orders_and_totals() -> None:
    """The position read orders by position_id and totals market value + accrued income."""
    out = read_position(
        ReadPositionInput(
            book="abor",
            portfolio_id="PF-0008",
            as_of_date=AS_OF,
            rows=(
                _position("POS-0002", "abor", "200.00", accrued="5.00"),
                _position("POS-0001", "abor", "100.00", accrued="3.00"),
            ),
        )
    )
    assert out.n_positions == 2
    assert out.total_market_value_usd == Decimal("300.00")
    assert out.total_accrued_income_usd == Decimal("8.00")
    # ordered by position_id (POS-0001 first)
    assert [p.position_id for p in out.positions] == ["POS-0001", "POS-0002"]


def test_read_position_is_deterministic() -> None:
    """Same input → same output (pure, no clock / RNG / dict-order dependence)."""
    inp = ReadPositionInput(
        book="ibor",
        portfolio_id="PF-0008",
        as_of_date=AS_OF,
        rows=(_position("POS-0021", "ibor", "13303649.45"),),
    )
    assert read_position(inp) == read_position(inp)


def test_read_position_empty_is_zero_not_error() -> None:
    """An empty portfolio reads as zero positions / zero totals — a clean empty read."""
    out = read_position(
        ReadPositionInput(book="ibor", portfolio_id="PF-0099", as_of_date=AS_OF, rows=())
    )
    assert out.n_positions == 0
    assert out.total_market_value_usd == Decimal(0)


# --- read_ibor_cash_and_exposure (SO-12.1-02) ----------------------------------------------------


def test_cash_and_exposure_projects_unsettled_legs() -> None:
    """Projected cash = settled cash + Σ in-flight legs; gross exposure echoes the position MV."""
    out = read_ibor_cash_and_exposure(
        ReadCashExposureInput(
            portfolio_id="PF-0008",
            as_of_date=AS_OF,
            settled_cash_usd=Decimal("1000.00"),
            gross_market_value_usd=Decimal("50000.00"),
            unsettled_legs=(
                UnsettledTradeLeg(
                    transaction_id="TXN-00001",
                    instrument_id="INS-0021",
                    settlement_date=date(2026, 4, 1),
                    amount_usd=Decimal("-2124187.25"),  # a buy: cash leaves on settlement
                ),
            ),
        )
    )
    assert out.unsettled_cash_impact_usd == Decimal("-2124187.25")
    assert out.projected_cash_usd == Decimal("1000.00") + Decimal("-2124187.25")
    assert out.gross_exposure_usd == Decimal("50000.00")
    assert out.n_unsettled == 1


def test_cash_and_exposure_no_legs_projects_settled_cash() -> None:
    """With no in-flight legs the projection is just the settled cash (the ABOR-equivalent view)."""
    out = read_ibor_cash_and_exposure(
        ReadCashExposureInput(
            portfolio_id="PF-0008",
            as_of_date=AS_OF,
            settled_cash_usd=Decimal("1000.00"),
            gross_market_value_usd=Decimal("50000.00"),
        )
    )
    assert out.projected_cash_usd == Decimal("1000.00")
    assert out.unsettled_cash_impact_usd == Decimal(0)


# --- read_ibor_pending_activity (SO-12.1-03) -----------------------------------------------------


def test_pending_activity_orders_and_nets() -> None:
    """The pending read orders by transaction_id and nets the signed amounts."""
    out = read_ibor_pending_activity(
        ReadPendingActivityInput(
            portfolio_id="PF-0008",
            as_of_date=AS_OF,
            transactions=(
                PendingTransaction(
                    transaction_id="TXN-00002",
                    transaction_type="trade",
                    portfolio_id="PF-0008",
                    instrument_id="INS-0022",
                    trade_date=AS_OF,
                    settlement_date=date(2026, 4, 2),
                    amount_usd=Decimal("238583.47"),
                    status="pending",
                ),
                PendingTransaction(
                    transaction_id="TXN-00001",
                    transaction_type="trade",
                    portfolio_id="PF-0008",
                    instrument_id="INS-0021",
                    trade_date=AS_OF,
                    settlement_date=date(2026, 4, 1),
                    amount_usd=Decimal("2124187.25"),
                    status="pending",
                ),
            ),
        )
    )
    assert out.n_pending == 2
    assert [t.transaction_id for t in out.transactions] == ["TXN-00001", "TXN-00002"]
    assert out.net_cash_impact_usd == Decimal("238583.47") + Decimal("2124187.25")


# --- read_transactions (SO-12.1-04) + read_cash_flow_events (SO-12.1-05) --------------------------


def test_transactions_orders_and_nets() -> None:
    out = read_transactions(
        ReadTransactionsInput(
            portfolio_id="PF-0008",
            as_of_date=AS_OF,
            rows=(
                TransactionRow(
                    transaction_id="TXN-2",
                    transaction_type="trade",
                    portfolio_id="PF-0008",
                    instrument_id="INS-0021",
                    trade_date=AS_OF,
                    amount_usd=Decimal("100.00"),
                    status="settled",
                    source="oms",
                ),
                TransactionRow(
                    transaction_id="TXN-1",
                    transaction_type="trade",
                    portfolio_id="PF-0008",
                    instrument_id="INS-0021",
                    trade_date=AS_OF,
                    amount_usd=Decimal("-50.00"),
                    status="settled",
                    source="oms",
                ),
            ),
        )
    )
    assert [t.transaction_id for t in out.transactions] == ["TXN-1", "TXN-2"]
    assert out.net_amount_usd == Decimal("50.00")


def test_cash_flows_orders_and_nets() -> None:
    out = read_cash_flow_events(
        ReadCashFlowsInput(
            portfolio_id="PF-0010",
            as_of_date=AS_OF,
            rows=(
                CashFlowRow(
                    cash_flow_id="CF-2",
                    portfolio_id="PF-0010",
                    cash_flow_date=AS_OF,
                    cash_flow_type="coupon",
                    direction="inflow",
                    amount=Decimal("10.00"),
                    currency="USD",
                    source="custodian",
                ),
                CashFlowRow(
                    cash_flow_id="CF-1",
                    portfolio_id="PF-0010",
                    cash_flow_date=AS_OF,
                    cash_flow_type="fee",
                    direction="outflow",
                    amount=Decimal("-3.00"),
                    currency="USD",
                    source="admin",
                ),
            ),
        )
    )
    assert [c.cash_flow_id for c in out.cash_flows] == ["CF-1", "CF-2"]
    assert out.net_amount_usd == Decimal("7.00")


# --- read_abor_accrued_income (SO-12.2-02) -------------------------------------------------------


def test_accrued_income_totals() -> None:
    out = read_abor_accrued_income(
        ReadAccruedIncomeInput(
            portfolio_id="PF-0012",
            as_of_date=AS_OF,
            rows=(
                AccruedIncomeRow(
                    position_id="POS-0049",
                    portfolio_id="PF-0012",
                    instrument_id="INS-0049",
                    accrued_income_usd=Decimal("19267.00"),
                    currency="USD",
                ),
                AccruedIncomeRow(
                    position_id="POS-0050",
                    portfolio_id="PF-0012",
                    instrument_id="INS-0050",
                    accrued_income_usd=Decimal("24945.00"),
                    currency="USD",
                ),
            ),
        )
    )
    assert out.n_accruing_positions == 2
    assert out.total_accrued_income_usd == Decimal("44212.00")


# --- read_abor_cost_basis (SO-12.2-03) -----------------------------------------------------------


def test_cost_basis_derives_unrealised_gain() -> None:
    out = read_abor_cost_basis(
        ReadCostBasisInput(
            portfolio_id="PF-0005",
            as_of_date=AS_OF,
            rows=(
                CostBasisRow(
                    position_id="POS-0013",
                    portfolio_id="PF-0005",
                    instrument_id="INS-0013",
                    cost_basis_usd=Decimal("7136356.50"),
                    market_value_usd=Decimal("10060835.39"),
                    unrealised_gain_usd=Decimal("10060835.39") - Decimal("7136356.50"),
                    currency="USD",
                ),
            ),
        )
    )
    assert out.total_cost_basis_usd == Decimal("7136356.50")
    assert out.total_unrealised_gain_usd == Decimal("10060835.39") - Decimal("7136356.50")


# --- read_abor_book_close_state (SO-12.2-04) -----------------------------------------------------


def test_book_close_state_closed_on_or_before_struck() -> None:
    """A period whose as-of is on/before the struck date is closed/locked; a later one is open."""
    struck = date(2026, 3, 31)
    closed = read_abor_book_close_state(
        ReadBookCloseStateInput(as_of_date=date(2026, 3, 31), latest_struck_book_date=struck)
    )
    assert closed.status == "closed"
    assert closed.is_locked is True
    # the derivation is reported honestly (no seeded state machine)
    assert "DERIVED" in closed.derivation

    open_period = read_abor_book_close_state(
        ReadBookCloseStateInput(as_of_date=date(2026, 4, 30), latest_struck_book_date=struck)
    )
    assert open_period.status == "open"
    assert open_period.is_locked is False
