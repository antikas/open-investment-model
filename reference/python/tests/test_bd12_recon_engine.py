"""The SD-12.10 reconciliation engine — the five load-bearing tests (OIM-162 cycle-1).

Drives the four reconcile tools (position · cash · transaction-matching · IBOR/ABOR) against the
OIM-160 canonical store and proves the cycle's load-bearing properties:

1. the engine surfaces every one of the OIM-160 N=11 labelled breaks with the CORRECT cause;
2. the dual-pipeline meta-disagreement is non-vacuous (a constructed A/B disagreement is surfaced);
3. an explained TD/SD timing diff is NOT a false break;
4. (the append-only insert-only store assertions live in ``test_bd12_recon_break_store``);
5. a rule-miss lands ``unexplained`` (not dropped, not guessed).

The N=11 surfacing + the timing + the data-gap tests are store-gated (skip cleanly when the
canonical store is not provisioned — the ``test_nav_marts_read`` precedent). The dual-pipeline
non-vacuous, the ``unexplained``-on-a-miss and the fx/pricing-split tests drive the PURE tools with
constructed rows, so they need no store.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from agentinvest_demo.marts import MartsUnavailableError
from agentinvest_tools.bd12_recon import (
    AdminCashBalance,
    AdminTransaction,
    BookPositionRow,
    CustodianCashBalance,
    CustodianPositionRow,
    IborAborInFlightTrade,
    InFlightTrade,
    InternalCashReplay,
    InternalPositionRow,
    InternalTransaction,
    ReconcileCashInput,
    ReconcileIborAborInput,
    ReconcilePositionInput,
    ReconcileTransactionsInput,
    reconcile_cash,
    reconcile_ibor_abor,
    reconcile_position,
    reconcile_transactions,
)
from agentinvest_tools.bd12_recon_service import (
    ReconcileRequest,
    _reconcile_cash,
    _reconcile_ibor_abor,
    _reconcile_position,
    _reconcile_transactions,
)

AS_OF = date(2026, 3, 31)
AS_OF_STR = "2026-03-31"


def _store_available() -> bool:
    try:
        from agentinvest_demo.comparator_feed_data import read_custodian_holdings

        read_custodian_holdings(AS_OF_STR)
    except MartsUnavailableError:
        return False
    return True


STORE = pytest.mark.skipif(not _store_available(), reason="canonical store not provisioned")


# ---------------------------------------------------------------------------
# (1) The engine surfaces every OIM-160 N=11 labelled break with the correct of-record cause.
# ---------------------------------------------------------------------------

# The OIM-160 labelled-break oracle (reference/dbt/seeds/break_labels.csv), keyed by record_ref →
# (reconciliation_type, cause). The engine must surface EXACTLY these, each with the correct cause.
_ORACLE: dict[str, tuple[str, str]] = {
    "POS-0004": ("position", "fx"),
    "POS-0012": ("position", "pricing"),
    "POS-0021": ("position", "timing"),
    "POS-0022": ("position", "timing"),
    "POS-0023": ("position", "fx"),
    "POS-0033": ("position", "data_error"),
    "POS-0034": ("position", "pricing"),
    "POS-0051": ("position", "data_error"),
    "TXN-00046": ("transaction", "missing_transaction"),
    "ADMIN-TXN-EXTRA-01": ("transaction", "missing_transaction"),
    "PF-0001": ("cash", "data_error"),
}


def _ref_key(record_a_ref: str) -> str:
    """Normalise a finding's ``record_a_ref`` to the oracle's record_ref (strip the side prefix)."""
    # cash findings are 'custodian-cash:PF-0001'; positions/transactions are the bare ref.
    if record_a_ref.startswith("custodian-cash:"):
        return record_a_ref.split(":", 1)[1]
    return record_a_ref


@STORE
def test_engine_surfaces_all_n11_labelled_breaks_with_correct_cause() -> None:
    """THE LOAD-BEARING TEST: every OIM-160 labelled break is surfaced with the correct cause.

    Runs all four reconciles over the canonical store (persist=False — a pure surfacing check) and
    asserts the surfaced break set is EXACTLY the N=11 oracle, each with the correct cause. ZERO
    missed breaks AND zero spurious breaks (the dual-pipeline produces no phantom false positives).
    """
    req = ReconcileRequest(as_of_date=AS_OF_STR, persist=False)
    surfaced: dict[str, tuple[str, str]] = {}
    for fn in (_reconcile_position, _reconcile_cash, _reconcile_transactions, _reconcile_ibor_abor):
        _out, findings = fn(req)
        for b in findings:
            surfaced[_ref_key(b.record_a_ref)] = (b.reconciliation_type, b.cause_classification)

    # Every oracle break is surfaced with the correct (type, cause).
    missed = [ref for ref in _ORACLE if ref not in surfaced]
    assert not missed, f"MISSED breaks: {missed}"
    miscaused = {
        ref: (surfaced[ref], _ORACLE[ref]) for ref in _ORACLE if surfaced[ref] != _ORACLE[ref]
    }
    assert not miscaused, f"MIS-CLASSIFIED (surfaced vs oracle): {miscaused}"

    # No spurious breaks beyond the oracle (the dual-pipeline manufactures no false positives).
    spurious = [ref for ref in surfaced if ref not in _ORACLE]
    assert not spurious, f"SPURIOUS breaks not in the oracle: {spurious}"

    assert len(surfaced) == 11, f"expected exactly N=11 breaks, got {len(surfaced)}"


# ---------------------------------------------------------------------------
# (2) The dual-pipeline meta-disagreement is non-vacuous — a constructed A/B disagreement surfaces.
# ---------------------------------------------------------------------------


def test_dual_pipeline_disagreement_is_surfaced_not_dropped() -> None:
    """A constructed A/B disagreement (book agrees with custodian, E-07 mark does not) surfaces.

    Pipeline A (book value) agrees with the custodian (no break); Pipeline B (the E-07 mark)
    diverges beyond the band. There is NO in-flight trade to explain the book-vs-mark gap, so the
    disagreement is genuine and UNEXPLAINED — it must surface as a break flagged
    ``pipeline_disagreement=True``, never silently reconciled to "A says clean".
    """
    out = reconcile_position(
        ReconcilePositionInput(
            as_of_date=AS_OF,
            internal_rows=(
                InternalPositionRow(
                    position_id="POS-X",
                    instrument_id="INS-X",
                    quantity=Decimal("100"),
                    book_market_value_usd=Decimal("1000000"),  # Pipeline A: agrees with custodian
                    mark_value_usd=Decimal("1100000"),  # Pipeline B: 10% above — disagrees
                    currency="USD",
                ),
            ),
            custodian_rows=(
                CustodianPositionRow(
                    position_id="POS-X",
                    instrument_id="INS-X",
                    quantity=Decimal("100"),
                    market_value_usd=Decimal("1000000"),  # agrees with the book value (Pipeline A)
                    currency="USD",
                ),
            ),
            in_flight_trades=(),  # nothing explains the book-vs-mark gap → genuine disagreement
        )
    )
    assert out.n_breaks == 1, out.breaks
    assert out.n_pipeline_disagreements == 1
    assert out.breaks[0].pipeline_disagreement is True


def test_dual_pipeline_does_not_fire_on_a_clean_holding() -> None:
    """NEGATIVE CONTROL: when A and B agree the holding is clean, no break and no disagreement.

    Proves the disagreement test above fires on the DISAGREEMENT, not on the machinery: a holding
    where the book value, the E-07 mark and the custodian all agree produces zero breaks.
    """
    out = reconcile_position(
        ReconcilePositionInput(
            as_of_date=AS_OF,
            internal_rows=(
                InternalPositionRow(
                    position_id="POS-Y",
                    instrument_id="INS-Y",
                    quantity=Decimal("50"),
                    book_market_value_usd=Decimal("500000"),
                    mark_value_usd=Decimal("500000"),
                    currency="USD",
                ),
            ),
            custodian_rows=(
                CustodianPositionRow(
                    position_id="POS-Y",
                    instrument_id="INS-Y",
                    quantity=Decimal("50"),
                    market_value_usd=Decimal("500000"),
                    currency="USD",
                ),
            ),
            in_flight_trades=(),
        )
    )
    assert out.n_breaks == 0
    assert out.n_pipeline_disagreements == 0


def test_cash_dual_pipeline_disagreement_surfaces_with_balance_grade_replay() -> None:
    """A balance-grade E-06 replay that disagrees with Pipeline A is surfaced (cash dual-pipeline).

    Custodian and admin agree (Pipeline A clean), but a balance-grade replay-derived balance
    differs from both beyond tolerance → Pipeline B disagrees with A → surfaced as a disagreement.
    """
    out = reconcile_cash(
        ReconcileCashInput(
            as_of_date=AS_OF,
            custodian_balances=(
                CustodianCashBalance(
                    portfolio_id="PF-Z", balance_usd=Decimal("1000000"), currency="USD"
                ),
            ),
            admin_balances=(
                AdminCashBalance(
                    portfolio_id="PF-Z", balance_usd=Decimal("1000000"), currency="USD"
                ),
            ),
            replay_balances=(
                # balance-grade (same sign, within an order of magnitude) but differs → B disagrees.
                InternalCashReplay(portfolio_id="PF-Z", replay_balance_usd=Decimal("1500000")),
            ),
        )
    )
    assert out.n_breaks == 1
    assert out.n_pipeline_disagreements == 1
    assert out.n_pipeline_b_abstained == 0


def test_cash_pipeline_b_abstains_on_a_non_balance_grade_replay() -> None:
    """A non-balance-grade replay (a small opposite-sign flow-delta) makes Pipeline B abstain.

    The OIM-160 seed is not a balance ledger — the E-06 replay sum is a small opposite-sign delta,
    not a balance. Pipeline B abstains (recorded in ``n_pipeline_b_abstained``) rather than
    manufacturing a false disagreement on a fund the externals agree on. No phantom break.
    """
    out = reconcile_cash(
        ReconcileCashInput(
            as_of_date=AS_OF,
            custodian_balances=(
                CustodianCashBalance(
                    portfolio_id="PF-W", balance_usd=Decimal("5000000"), currency="USD"
                ),
            ),
            admin_balances=(
                AdminCashBalance(
                    portfolio_id="PF-W", balance_usd=Decimal("5000000"), currency="USD"
                ),
            ),
            replay_balances=(
                InternalCashReplay(portfolio_id="PF-W", replay_balance_usd=Decimal("-200000")),
            ),
        )
    )
    assert out.n_breaks == 0
    assert out.n_pipeline_b_abstained == 1


# ---------------------------------------------------------------------------
# (3) An explained TD/SD timing diff is NOT a false break.
# ---------------------------------------------------------------------------


def test_explained_timing_diff_is_classified_timing_not_a_false_break() -> None:
    """A quantity lag exactly explained by an in-flight trade is a single ``timing`` break, low mat.

    The custodian lags the internal book by exactly the in-flight trade quantity (the trade is
    booked trade-date internally, not yet settlement-date by the custodian). The engine reads it
    trade and classifies the lag ``timing`` — NOT a ``data_error`` hard break, and NOT two breaks.
    """
    out = reconcile_position(
        ReconcilePositionInput(
            as_of_date=AS_OF,
            internal_rows=(
                InternalPositionRow(
                    position_id="POS-T",
                    instrument_id="INS-T",
                    quantity=Decimal("10000"),
                    book_market_value_usd=Decimal("2000000"),
                    mark_value_usd=Decimal("2000000"),
                    currency="USD",
                ),
            ),
            custodian_rows=(
                CustodianPositionRow(
                    position_id="POS-T",
                    instrument_id="INS-T",
                    quantity=Decimal("9300"),  # lags by 700 — exactly the in-flight trade
                    market_value_usd=Decimal("2000000"),
                    currency="USD",
                ),
            ),
            in_flight_trades=(
                InFlightTrade(
                    transaction_id="TXN-T", instrument_id="INS-T", quantity=Decimal("700")
                ),
            ),
        )
    )
    assert out.n_breaks == 1
    assert out.breaks[0].cause_classification == "timing"
    assert out.breaks[0].materiality == "low"
    assert out.breaks[0].pipeline_disagreement is False


def test_unexplained_qty_lag_is_data_error_not_timing() -> None:
    """A quantity lag NOT explained by any in-flight trade is ``data_error``, not ``timing``.

    NEGATIVE CONTROL for the timing rule: the same shape but with NO in-flight trade → the engine
    must NOT call it timing (it would be a false explanation); it is a genuine ``data_error``.
    """
    out = reconcile_position(
        ReconcilePositionInput(
            as_of_date=AS_OF,
            internal_rows=(
                InternalPositionRow(
                    position_id="POS-D",
                    instrument_id="INS-D",
                    quantity=Decimal("10000"),
                    book_market_value_usd=Decimal("2000000"),
                    mark_value_usd=Decimal("2000000"),
                    currency="USD",
                ),
            ),
            custodian_rows=(
                CustodianPositionRow(
                    position_id="POS-D",
                    instrument_id="INS-D",
                    quantity=Decimal("9300"),
                    market_value_usd=Decimal("2000000"),
                    currency="USD",
                ),
            ),
            in_flight_trades=(),  # nothing explains the lag
        )
    )
    assert out.n_breaks == 1
    assert out.breaks[0].cause_classification == "data_error"


# ---------------------------------------------------------------------------
# (5) A rule-miss lands ``unexplained`` (not dropped, not guessed) — the IBOR/ABOR residual.
# ---------------------------------------------------------------------------


def test_ibor_abor_unexplained_residual_lands_unexplained() -> None:
    """An IBOR/ABOR divergence NO known class explains lands ``unexplained``, surfaced not dropped.

    Two books differ in market value with NO in-flight trade (timing), NO accrual and NO cost-basis
    class to explain it — the residual is genuinely unexplained. The engine surfaces a single
    ``ibor_abor`` break classified ``unexplained`` (the of-record residue cycle-2's LLM annotates),
    never silently dropped and never force-fit to a known class.
    """
    out = reconcile_ibor_abor(
        ReconcileIborAborInput(
            as_of_date=AS_OF,
            ibor_rows=(
                BookPositionRow(
                    position_id="POS-U",
                    instrument_id="INS-U",
                    quantity=Decimal("100"),
                    market_value_usd=Decimal("1000000"),
                    accrued_income_usd=None,
                    cost_basis_usd=Decimal("900000"),
                ),
            ),
            abor_rows=(
                BookPositionRow(
                    position_id="POS-U",
                    instrument_id="INS-U",
                    quantity=Decimal("100"),  # qty agrees (no timing)
                    market_value_usd=Decimal("1200000"),  # MV differs, unexplained
                    accrued_income_usd=None,  # no accrual class
                    cost_basis_usd=Decimal("900000"),  # no cost-basis divergence
                ),
            ),
            in_flight_trades=(),  # no timing explanation
        )
    )
    assert out.n_breaks == 1
    assert out.breaks[0].cause_classification == "unexplained"
    assert out.breaks[0].pipeline_disagreement is True


def test_ibor_abor_explained_divergence_emits_zero_breaks_on_the_clean_book() -> None:
    """A timing-explained IBOR/ABOR divergence emits ZERO breaks (the divergence is accounted for).

    NEGATIVE CONTROL: the ABOR book lags the IBOR by exactly an in-flight trade quantity — a known
    timing class. The engine accounts for it (n_explained=1) and emits NO ibor_abor break. On the
    clean OIM-160 dual book every divergence is so explained → zero ibor_abor breaks.
    """
    out = reconcile_ibor_abor(
        ReconcileIborAborInput(
            as_of_date=AS_OF,
            ibor_rows=(
                BookPositionRow(
                    position_id="POS-E",
                    instrument_id="INS-E",
                    quantity=Decimal("10000"),
                    market_value_usd=Decimal("2000000"),
                    accrued_income_usd=None,
                    cost_basis_usd=Decimal("1800000"),
                ),
            ),
            abor_rows=(
                BookPositionRow(
                    position_id="POS-E",
                    instrument_id="INS-E",
                    quantity=Decimal("9300"),  # lags by 700 = the in-flight trade
                    market_value_usd=Decimal("1860000"),
                    accrued_income_usd=None,
                    cost_basis_usd=Decimal("1800000"),
                ),
            ),
            in_flight_trades=(
                IborAborInFlightTrade(
                    transaction_id="TXN-E", instrument_id="INS-E", quantity=Decimal("700")
                ),
            ),
        )
    )
    assert out.n_divergent == 1
    assert out.n_explained == 1
    assert out.n_breaks == 0


def test_transaction_matching_runs_both_directions() -> None:
    """Transaction matching surfaces BOTH internal-only AND external-only residue (dual-direction).

    A one-direction match would miss the extra administrator transaction. Both directions run: an
    internal-only transaction and an external-only administrator line are BOTH surfaced as
    ``missing_transaction`` breaks.
    """
    out = reconcile_transactions(
        ReconcileTransactionsInput(
            as_of_date=AS_OF,
            internal_transactions=(
                InternalTransaction(
                    transaction_id="TXN-A", portfolio_id="PF-1", amount_usd=Decimal("-100")
                ),
                InternalTransaction(
                    transaction_id="TXN-INT-ONLY", portfolio_id="PF-1", amount_usd=Decimal("-200")
                ),
            ),
            admin_transactions=(
                AdminTransaction(ref="TXN-A", portfolio_id="PF-1", amount_usd=Decimal("-100")),
                AdminTransaction(
                    ref="TXN-EXT-ONLY", portfolio_id="PF-1", amount_usd=Decimal("-300")
                ),
            ),
        )
    )
    assert out.n_internal_only == 1
    assert out.n_external_only == 1
    assert out.n_breaks == 2
    refs = {b.record_a_ref for b in out.breaks}
    assert refs == {"TXN-INT-ONLY", "TXN-EXT-ONLY"}
    assert all(b.cause_classification == "missing_transaction" for b in out.breaks)


def test_fx_pricing_split_by_ratio_cluster() -> None:
    """The fx/pricing split is the of-record ratio cluster — NOT the custodian's break_note label.

    Three qty-agree value differences: two share an identical ratio (a systematic FX translation
    factor) → ``fx``; one has an idiosyncratic ratio (a single mismarked holding) → ``pricing``.
    Derived purely from the observable values.
    """
    out = reconcile_position(
        ReconcilePositionInput(
            as_of_date=AS_OF,
            internal_rows=(
                InternalPositionRow(
                    position_id="P1",
                    instrument_id="I1",
                    book_market_value_usd=Decimal("1000000"),
                    mark_value_usd=Decimal("1000000"),
                    currency="USD",
                ),
                InternalPositionRow(
                    position_id="P2",
                    instrument_id="I2",
                    book_market_value_usd=Decimal("2000000"),
                    mark_value_usd=Decimal("2000000"),
                    currency="USD",
                ),
                InternalPositionRow(
                    position_id="P3",
                    instrument_id="I3",
                    book_market_value_usd=Decimal("3000000"),
                    mark_value_usd=Decimal("3000000"),
                    currency="USD",
                ),
            ),
            custodian_rows=(
                CustodianPositionRow(
                    position_id="P1",
                    instrument_id="I1",
                    market_value_usd=Decimal("980000"),
                    currency="USD",
                ),  # ratio 0.98
                CustodianPositionRow(
                    position_id="P2",
                    instrument_id="I2",
                    market_value_usd=Decimal("1960000"),
                    currency="USD",
                ),  # ratio 0.98 (shared → fx)
                CustodianPositionRow(
                    position_id="P3",
                    instrument_id="I3",
                    market_value_usd=Decimal("3150000"),
                    currency="USD",
                ),  # ratio 1.05 (unique → pricing)
            ),
            in_flight_trades=(),
        )
    )
    cause = {b.record_a_ref: b.cause_classification for b in out.breaks}
    assert cause == {"P1": "fx", "P2": "fx", "P3": "pricing"}
