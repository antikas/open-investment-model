"""The SD-12.10 reconciliation engine — the load-bearing characterisation tests.

Drives the four reconcile tools (position · cash · transaction-matching · IBOR/ABOR) against the
canonical store and proves the load-bearing properties:

1. the engine surfaces EVERY engine-reconciled labelled break with its pinned cause — the oracle is
   SEED-LOADED from ``break_labels.json`` (the SSOT), so the pin count tracks the seed and cannot
   drift to a stale hard-coded N; each break is pinned correct / unexplained-by-design /
   KNOWN-MISCLASSIFIED on the enriched feed;
2. the dual-pipeline meta-disagreement is non-vacuous (a constructed A/B disagreement is surfaced),
   and fires ON DATA (``n_pipeline_disagreements > 0``);
3. an explained TD/SD timing diff is NOT a false break;
4. (the append-only insert-only store assertions live in ``test_bd12_recon_break_store``);
5. a rule-miss lands ``unexplained`` (not dropped, not guessed).

The seed-loaded-pin + the cash-B/disagreement-on-data tests are store-gated (skip cleanly when the
canonical store is not provisioned — the ``test_nav_marts_read`` precedent). The dual-pipeline
non-vacuous, the ``unexplained``-on-a-miss and the fx/pricing-split tests drive the PURE tools with
constructed rows, so they need no store.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import cast

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
    ReconcileCashOutput,
    ReconcileIborAborInput,
    ReconcileIborAborOutput,
    ReconcilePositionInput,
    ReconcilePositionOutput,
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
# (1) The engine is CHARACTERISED, not fixed — seed-loaded per-break pins.
#
# The labelled-break oracle is read from reference/dbt/seeds/break_labels.json (the SSOT), and each
# break's expected ENGINE outcome is pinned as an executable expectation — correct /
# unexplained-by-design / KNOWN-MISCLASSIFIED (the deterministic classifier's HONEST behaviour on
# the enriched feed). ZERO breaks may be MISSED (surfacing is rule-independent — a misclassified
# break is still surfaced); a genuinely missed engine-reconciled break is a gating failure, never
# a pin.
# ---------------------------------------------------------------------------

# the seed dir (reference/dbt/seeds) relative to this test file (reference/python/tests).
_SEED_DIR = Path(__file__).resolve().parents[2] / "dbt" / "seeds"

# the engine reconciles these reconciliation types; `nav` (the admin shadow-NAV divergence) is an
# SD-12.16 oversight surface, NOT an SD-12.10 reconcile surface, so the engine correctly does NOT
# surface it.
_ENGINE_RECONCILED_TYPES = {"position", "cash", "transaction", "ibor_abor"}

# Pin types — the executable characterisation of the engine's HONEST per-break behaviour.
_CORRECT = "correct"  # engine cause == oracle (true) cause
_UNEXPLAINED = "unexplained-by-design"  # engine lands `unexplained`; oracle carries the true cause
_MISCLASSIFIED = "KNOWN-MISCLASSIFIED"  # engine cause != true cause (the adversarial shapes)

# The per-break engine-outcome pins, keyed by the oracle record_ref. Each value is
# (engine_cause, pin_type) — the cause the deterministic engine ACTUALLY assigns, and how that
# relates to the oracle's TRUE cause. The KNOWN-MISCLASSIFIED pins are the adversarial fx/pricing
# shapes. Everything else the engine classifies correctly.
_ENGINE_PINS: dict[str, tuple[str, str]] = {
    # --- the original eleven (still correct on the enriched feed) ---
    "POS-0004": ("fx", _CORRECT),
    "POS-0012": ("pricing", _CORRECT),
    "POS-0021": ("timing", _CORRECT),
    "POS-0022": ("timing", _CORRECT),
    "POS-0023": ("fx", _CORRECT),
    "POS-0033": ("data_error", _CORRECT),
    "POS-0034": ("pricing", _CORRECT),
    "POS-0051": ("data_error", _CORRECT),
    "TXN-00046": ("missing_transaction", _CORRECT),
    "ADMIN-TXN-EXTRA-01": ("missing_transaction", _CORRECT),
    "PF-0001": ("data_error", _CORRECT),
    # --- the sound (correctly-classified) additions ---
    "POS-0005": ("fx", _CORRECT),
    "POS-0007": ("fx", _CORRECT),
    "POS-0006": ("pricing", _CORRECT),
    "POS-0009": ("pricing", _CORRECT),
    "POS-0025": ("data_error", _CORRECT),
    "POS-0027": ("data_error", _CORRECT),
    "POS-0030": ("timing", _CORRECT),
    "POS-0031": ("timing", _CORRECT),
    "PF-0002": ("data_error", _CORRECT),
    # the +1 missing/extra-transaction instance: a second extra admin transaction the internal book
    # lacks → the matcher surfaces it `missing_transaction`.
    "ADMIN-TXN-EXTRA-02": ("missing_transaction", _CORRECT),
    # --- the three adversarial fx/pricing shapes — the narrowed direction rule + the honest
    #     demotion:
    # ADV-1 single-holding fx (ratio 0.94 < 1, lone): the narrowed rule has NO cluster + NO
    # direction signal to call it fx → the rule STOPS GUESSING → engine lands `unexplained` (the
    # honest DEMOTION). The true cause `fx` is rule-unreachable in this USD-only feed — it joins the
    # `unexplained` residue (the propose-only LLM sees it).
    "POS-0013": ("unexplained", _UNEXPLAINED),
    # ADV-2 coincidental shared-ratio pricing pair (ratio 1.058 > 1, custodian ABOVE book): the
    # narrowed DIRECTION rule reads an above-book mark as `pricing` (never the downward fx
    # signature) → engine CORRECT.
    "POS-0014": ("pricing", _CORRECT),
    "POS-0015": ("pricing", _CORRECT),
    # ADV-3 pricing ratio (0.965 < 1) COLLIDES EXACTLY with the genuine fx pair's ratio → it
    # clusters with them and stays `fx` (true pricing). The collision is observably UNBREAKABLE in
    # this USD-only feed (no label-independent signal separates it from the real fx members) → it
    # stays KNOWN-MISCLASSIFIED: the documented honest boundary (no force-fit, no label-encoded
    # rule).
    "POS-0016": ("fx", _MISCLASSIFIED),
    # --- the A/B-disagreement case (position-internal): surfaced with pipeline_disagreement=True;
    #     the engine classifies the (zero-amount, custodian-ties-book) surfaced break `pricing`. ---
    "POS-0019": ("pricing", _CORRECT),
    # --- the two rule-unreachable breaks → `unexplained` ---
    "ibor:POS-0019": ("unexplained", _UNEXPLAINED),
    "ibor:POS-0035": ("unexplained", _UNEXPLAINED),
}


def _load_oracle() -> list[dict[str, str]]:
    """Load the labelled-break oracle from the seed SSOT (break_labels.json) — NOT hand-typed."""
    payload = json.loads((_SEED_DIR / "break_labels.json").read_text(encoding="utf-8"))
    breaks: list[dict[str, str]] = payload["breaks"]
    return breaks


def _ref_key(record_a_ref: str) -> str:
    """Normalise a finding's ``record_a_ref`` to the oracle's record_ref.

    Cash findings are ``custodian-cash:PF-0001`` → ``PF-0001``; ibor_abor findings are
    ``ibor:POS-XXXX`` → kept as ``ibor:POS-XXXX`` (the oracle's ibor_abor record_ref carries the
    same prefix); positions/transactions are the bare ref.
    """
    if record_a_ref.startswith("custodian-cash:"):
        return record_a_ref.split(":", 1)[1]
    return record_a_ref


@STORE
def test_engine_pins_every_labelled_break_seed_loaded() -> None:
    """THE LOAD-BEARING TEST: every engine-reconciled labelled break is surfaced and its
    engine outcome matches the SEED-LOADED pin — correct / unexplained-by-design / misclassified.

    Runs all four reconciles over the enriched canonical store (persist=False). The oracle is read
    from break_labels.json (the seed SSOT, NOT a hand-transcribed dict). ZERO engine-reconciled
    breaks may be missed (surfacing is rule-independent — a misclassified break is still surfaced);
    every surfaced break's cause matches its pin; no spurious break beyond the oracle; the `nav`
    shadow-NAV-divergence is correctly NOT surfaced by the engine.
    """
    oracle = _load_oracle()
    # the engine-reconciled subset of the oracle (exclude the nav oversight surface).
    engine_oracle = {
        b["record_ref"]: (b["reconciliation_type"], b["cause_classification"])
        for b in oracle
        if b["reconciliation_type"] in _ENGINE_RECONCILED_TYPES
    }
    nav_refs = {b["record_ref"] for b in oracle if b["reconciliation_type"] == "nav"}

    req = ReconcileRequest(as_of_date=AS_OF_STR, persist=False)
    surfaced: dict[str, tuple[str, str]] = {}
    for fn in (_reconcile_position, _reconcile_cash, _reconcile_transactions, _reconcile_ibor_abor):
        _out, findings = fn(req)
        for b in findings:
            surfaced[_ref_key(b.record_a_ref)] = (b.reconciliation_type, b.cause_classification)

    # (1) ZERO MISSED — every engine-reconciled labelled break is surfaced (rule-independent).
    missed = [ref for ref in engine_oracle if ref not in surfaced]
    assert not missed, f"MISSED engine-reconciled breaks (gating): {missed}"

    # (2) EVERY pin holds — the surfaced reconciliation_type matches the oracle, and the surfaced
    #     cause matches the SEED-LOADED engine pin (correct / unexplained / KNOWN-MISCLASSIFIED).
    pin_failures: dict[str, object] = {}
    for ref, (otype, _ocause) in engine_oracle.items():
        stype, scause = surfaced[ref]
        assert ref in _ENGINE_PINS, f"break {ref} has no engine pin — add it to _ENGINE_PINS"
        pinned_cause, _pin_type = _ENGINE_PINS[ref]
        if (stype, scause) != (otype, pinned_cause):
            pin_failures[ref] = {
                "surfaced": (stype, scause),
                "expected": (otype, pinned_cause),
                "pin_type": _pin_type,
            }
    assert not pin_failures, f"PIN MISMATCH (engine drifted from the pins): {pin_failures}"

    # (3) NO SPURIOUS — every surfaced break is an engine-reconciled oracle break (no phantom).
    spurious = [ref for ref in surfaced if ref not in engine_oracle]
    assert not spurious, f"SPURIOUS breaks not in the oracle: {spurious}"

    # (4) the nav shadow-NAV-divergence is an oversight surface — the engine does NOT surface it
    #     (the engine reconciles position/cash/transaction/ibor_abor, not NAV).
    surfaced_nav = [ref for ref in nav_refs if ref in surfaced]
    assert not surfaced_nav, f"the engine wrongly surfaced a nav break: {surfaced_nav}"

    # the pins cover exactly the engine-reconciled oracle (every break pinned, no orphan pins).
    assert set(_ENGINE_PINS) == set(engine_oracle), (
        f"pin/oracle mismatch — only in pins: {set(_ENGINE_PINS) - set(engine_oracle)}; "
        f"only in oracle: {set(engine_oracle) - set(_ENGINE_PINS)}"
    )


@STORE
def test_flywheel_turn_outcome_pins_are_honest() -> None:
    """The rule-discovery outcome: 2 pins flip to correct, 1 demotes, 1 stays honest.

    The rule-discovery NARROWED the fx/pricing rule (the direction signal) + DEMOTED the
    lone-downward case. This test guards the HONEST outcome over the three adversarial shapes + the
    two ibor residue breaks, re-derived from the live engine + the seed oracle (NOT the pin map):

    - POS-0014 / POS-0015 (true pricing, custodian-above ratio 1.058): the engine now classifies
      `pricing` CORRECTLY (the direction-rule PROMOTE — the pins flipped fx→pricing);
    - POS-0013 (true fx, lone downward ratio 0.94): the engine lands `unexplained` (the honest
      DEMOTION — no observable rule reaches a single-holding fx);
    - POS-0016 (true pricing, downward ratio 0.965 colliding with the fx pair): the engine stays
      `fx` (the documented honest boundary — observably indistinguishable from the fx members);
    - ibor:POS-0019 / ibor:POS-0035: still `unexplained` (the rule-unreachable residue, unchanged).

    The ONLY remaining KNOWN-MISCLASSIFIED pin is POS-0016 (the unbreakable collision).
    """
    oracle_cause = {b["record_ref"]: b["cause_classification"] for b in _load_oracle()}
    req = ReconcileRequest(as_of_date=AS_OF_STR, persist=False)
    engine_cause: dict[str, str] = {}
    for fn in (_reconcile_position, _reconcile_cash, _reconcile_transactions, _reconcile_ibor_abor):
        _out, findings = fn(req)
        for b in findings:
            engine_cause[_ref_key(b.record_a_ref)] = b.cause_classification

    # (1) the PROMOTE: the coincidental shared-ratio pricing pair now classifies CORRECTLY.
    for ref in ("POS-0014", "POS-0015"):
        assert engine_cause[ref] == oracle_cause[ref] == "pricing", (
            f"{ref} should now be correct pricing (the direction-rule promote): "
            f"engine={engine_cause[ref]} oracle={oracle_cause[ref]}"
        )

    # (2) the DEMOTION: the lone-downward fx now lands `unexplained` (the rule stops guessing).
    assert engine_cause["POS-0013"] == "unexplained"
    assert oracle_cause["POS-0013"] == "fx"  # the true cause remains rule-unreachable

    # (3) the honest boundary: the collision case stays misclassified `fx` (true pricing).
    assert engine_cause["POS-0016"] == "fx" != oracle_cause["POS-0016"] == "pricing"

    # (4) the ONLY remaining KNOWN-MISCLASSIFIED pin is the collision case.
    misclassified = {ref for ref, (_c, pt) in _ENGINE_PINS.items() if pt == _MISCLASSIFIED}
    assert misclassified == {"POS-0016"}
    for ref in misclassified:
        assert engine_cause[ref] != oracle_cause[ref], (
            f"{ref} pinned KNOWN-MISCLASSIFIED but engine == oracle — it no longer misclassifies"
        )

    # (5) the unexplained-by-design residue: the engine lands `unexplained`; the oracle carries a
    #     true cause the deterministic rules cannot reach. POS-0013 joins it (the demotion); the two
    #     ibor breaks are coherent with the injected corruption.
    unexplained = {ref for ref, (_c, pt) in _ENGINE_PINS.items() if pt == _UNEXPLAINED}
    assert unexplained == {"POS-0013", "ibor:POS-0019", "ibor:POS-0035"}
    _unexplained_true_cause = {
        "POS-0013": "fx",
        "ibor:POS-0019": "pricing",
        "ibor:POS-0035": "data_error",
    }
    for ref in unexplained:
        assert engine_cause[ref] == "unexplained"
        assert oracle_cause[ref] == _unexplained_true_cause[ref]


@STORE
def test_live_data_exercises_cash_b_and_pipeline_disagreement() -> None:
    """ON DATA: the cash Pipeline-B replay runs (no abstention) and the dual-pipeline disagrees.

    The balance-grade E-06 enrichment makes the cash Pipeline-B `_replay_is_balance_grade`
    gate PASS on the live feed (``n_pipeline_b_abstained == 0``), and the A/B-disagreement
    enrichment makes the dual-pipeline genuinely disagree on data
    (``n_pipeline_disagreements > 0``) — both exercised by the data rather than only by constructed
    test rows.
    """
    req = ReconcileRequest(as_of_date=AS_OF_STR, persist=False)
    cash_raw, _ = _reconcile_cash(req)
    cash_out = cast(ReconcileCashOutput, cash_raw)
    assert cash_out.n_pipeline_b_abstained == 0, (
        f"cash Pipeline-B abstained on data ({cash_out.n_pipeline_b_abstained}) — the "
        f"balance-grade E-06 enrichment should make the replay balance-grade on every fund"
    )

    pos_raw, _ = _reconcile_position(req)
    pos_out = cast(ReconcilePositionOutput, pos_raw)
    ibor_abor_raw, _ = _reconcile_ibor_abor(req)
    ibor_abor_out = cast(ReconcileIborAborOutput, ibor_abor_raw)
    total_disagreements = pos_out.n_pipeline_disagreements + ibor_abor_out.n_pipeline_disagreements
    assert total_disagreements > 0, (
        "no pipeline disagreement on live data — the A/B-disagreement enrichment should make the "
        "dual-pipeline genuinely disagree on the enriched feed"
    )
    # specifically: the position A/B-disagreement case fires on data.
    assert pos_out.n_pipeline_disagreements >= 1, (
        f"the position A/B-disagreement case did not fire on data "
        f"(n_pipeline_disagreements={pos_out.n_pipeline_disagreements})"
    )


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

    The seed is not a balance ledger — the E-06 replay sum is a small opposite-sign delta,
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
    ``ibor_abor`` break classified ``unexplained`` (the of-record residue the LLM annotates),
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
    clean dual book every divergence is so explained → zero ibor_abor breaks.
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
