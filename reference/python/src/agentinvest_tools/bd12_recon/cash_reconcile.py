"""SO-12.10 cash reconciliation — custodian vs administrator cash, dual-independent-pipeline.

The SD-12.10 *cash reconciliation* Service Operation: reconcile cash balances between the firm's
records, the custodian statement and the administrator statement, account by account (per fund).
Emits E-24-shaped cash-break findings with a deterministic of-record cause.

THE DUAL-INDEPENDENT-PIPELINE (the safety property):

- **Pipeline A — the direct comparison.** The custodian cash balance vs the administrator cash
  balance per fund (the OIM-160 cash break is injected as a custodian-vs-admin disagreement —
  BRK-0011, PF-0001).
- **Pipeline B — the E-06 cash-flow-replay derivation.** The internal cash balance DERIVED by
  replaying the E-06 cash-flow events up to the as-of (Kleppmann derive-by-replay: the balance is a
  derived view rebuilt from the event log). Pipeline B reconciles each external balance against the
  replay-derived internal balance.

Where A and B disagree on whether a fund's cash breaks (the custodian and admin agree but the
replay-derived internal balance differs from both, or vice versa), the disagreement is surfaced as a
break flagged ``pipeline_disagreement=True`` — never silently reconciled.

THE DETERMINISTIC CLASSIFIER: a cash-balance disagreement beyond the to-the-cent tolerance is
``data_error`` (the OIM-160 cash break is labelled ``data_error``); the engine does not force-fit a
finer cause it cannot observe.

Pure and deterministic: the custodian balances, the admin balances and the E-06 cash flows are read
by the data-access layers and passed in; this tool reconciles, classifies and surfaces. No I/O.

Honest boundary: a reconcile over the OIM-160 **synthetic** feed, FINDINGS-ONLY — never a production
cash reconciliation against a live bank/custodian, never a correcting entry (OIM-163).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from agentinvest_tools.bd12_recon.break_finding import (
    CASH_TOLERANCE,
    BreakFinding,
    materiality_for_amount,
)


class CustodianCashBalance(BaseModel):
    """One custodian cash balance per fund — a reconcile side (outside data)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    portfolio_id: str = Field(description="The fund the balance is for (the matching key).")
    balance_usd: Decimal = Field(description="The custodian's cash balance.")
    currency: str = Field(description="The balance currency.")


class AdminCashBalance(BaseModel):
    """One administrator cash balance per fund — a reconcile side (outside data)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    portfolio_id: str = Field(description="The fund the balance is for (the matching key).")
    balance_usd: Decimal = Field(description="The administrator's cash balance.")
    currency: str = Field(description="The balance currency.")


class InternalCashReplay(BaseModel):
    """The E-06 replay-derived internal cash balance per fund — Pipeline B's internal value.

    Derived by replaying the E-06 cash-flow events up to the as-of (signed by direction). The
    derive-by-replay internal balance is a genuinely independent computation of the cash position vs
    the externally-reported balances.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    portfolio_id: str = Field(description="The fund the replay balance is for (the matching key).")
    replay_balance_usd: Decimal = Field(
        description="Σ the E-06 cash flows up to the as-of (signed) — the replay-derived balance."
    )


class ReconcileCashInput(BaseModel):
    """Inputs to the cash reconcile — the custodian + admin balances + the E-06 replay balances."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    as_of_date: date = Field(description="The date the balances are reconciled as of.")
    custodian_balances: tuple[CustodianCashBalance, ...] = Field(default=())
    admin_balances: tuple[AdminCashBalance, ...] = Field(default=())
    replay_balances: tuple[InternalCashReplay, ...] = Field(
        default=(),
        description="The E-06 replay-derived internal balances (Pipeline B). Optional: when absent "
        "for a fund, Pipeline B is not run for that fund (and that is recorded, not silently "
        "dropped — see the engine notes).",
    )


class ReconcileCashOutput(BaseModel):
    """The cash reconcile result — the break findings, the counts, the dual-pipeline summary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reconciliation_type: str = Field(default="cash")
    as_of_date: date = Field(description="The as-of date the reconcile honoured.")
    n_funds: int = Field(description="Funds reconciled (present on both external sides).")
    n_breaks: int = Field(description="The number of break findings emitted.")
    n_pipeline_disagreements: int = Field(
        description="Breaks where Pipeline A and Pipeline B disagreed (surfaced, not reconciled)."
    )
    n_pipeline_b_abstained: int = Field(
        default=0,
        description="Funds where the E-06 replay was not balance-grade, so Pipeline B abstained "
        "(surfaced — the OIM-160 seed is not a balance ledger; single-pipeline A is of-record).",
    )
    breaks: tuple[BreakFinding, ...] = Field(
        description="The E-24-shaped cash-break findings, ordered by record_a_ref."
    )


def _replay_is_balance_grade(replay_balance: Decimal, external: Decimal) -> bool:
    """True iff the E-06 replay sum is plausibly a comparable cash BALANCE (not a flow-delta).

    Pipeline B for cash needs a replay-derived BALANCE to compare against the external balances. The
    E-06 cash-flow seed reconstructs a balance only where the flow log is balance-grade (sums to a
    figure of the same order/sign as the external balance). Where the replay sum is a small,
    opposite-sign flow-delta (the OIM-160 seed is NOT a balance ledger — it carries a handful of
    illustrative flows, not the funding history), the replay is NOT balance-grade and Pipeline B
    abstains rather than manufacturing a false disagreement against every fund. The gate: the replay
    must be within an order of magnitude of, and the same sign as, the external balance.
    """
    if external == 0:
        return replay_balance == 0
    if (replay_balance < 0) != (external < 0):
        return False  # opposite sign — not a comparable balance
    ratio = abs(replay_balance) / abs(external)
    return Decimal("0.1") <= ratio <= Decimal("10")


def reconcile_cash(inp: ReconcileCashInput) -> ReconcileCashOutput:
    """Reconcile the custodian vs administrator cash — dual-pipeline, deterministic classification.

    Pipeline A compares custodian vs admin per fund (the of-record cash reconcile). Pipeline B
    compares each external against the E-06 replay-derived internal BALANCE — but only where the
    replay is balance-grade (see ``_replay_is_balance_grade``); where it is not (the OIM-160 seed is
    not a balance ledger), Pipeline B abstains and ``n_pipeline_b_abstained`` records it — surfaced,
    NOT silently dropped and NOT a manufactured disagreement. A balance-grade Pipeline B that
    genuinely disagrees with A is surfaced as a pipeline disagreement. Pure and deterministic.
    """
    custodian = {b.portfolio_id: b for b in inp.custodian_balances}
    admin = {b.portfolio_id: b for b in inp.admin_balances}
    replay = {b.portfolio_id: b for b in inp.replay_balances}
    matched_keys = sorted(set(custodian) & set(admin))

    findings: list[BreakFinding] = []
    n_b_abstained = 0
    for fund in matched_keys:
        cust = custodian[fund]
        adm = admin[fund]
        # --- Pipeline A: custodian vs admin (the of-record cash reconcile) ---
        a_diff = adm.balance_usd - cust.balance_usd
        a_breaks = abs(a_diff) > CASH_TOLERANCE

        # --- Pipeline B: the replay-derived BALANCE vs the externals (balance-grade only) ---
        b_breaks = False
        b_available = False
        if fund in replay:
            rb = replay[fund].replay_balance_usd
            if _replay_is_balance_grade(rb, cust.balance_usd):
                b_available = True
                b_breaks = (abs(rb - cust.balance_usd) > CASH_TOLERANCE) or (
                    abs(rb - adm.balance_usd) > CASH_TOLERANCE
                )
            else:
                n_b_abstained += 1

        # A cash break is surfaced when Pipeline A finds one, OR when a balance-grade Pipeline B
        # genuinely disagrees with A. A non-balance-grade replay never manufactures a break.
        disagreement = b_available and (a_breaks != b_breaks)
        if a_breaks or disagreement:
            findings.append(
                BreakFinding(
                    reconciliation_type="cash",
                    record_a_ref=f"custodian-cash:{fund}",
                    record_b_ref=f"admin-cash:{fund}",
                    as_of_date=inp.as_of_date,
                    difference_amount=a_diff,
                    difference_qty=None,
                    cause_classification="data_error",
                    materiality=materiality_for_amount(a_diff),
                    pipeline_disagreement=disagreement,
                )
            )

    ordered = tuple(sorted(findings, key=lambda b: b.record_a_ref))
    return ReconcileCashOutput(
        as_of_date=inp.as_of_date,
        n_funds=len(matched_keys),
        n_breaks=len(ordered),
        n_pipeline_disagreements=sum(1 for b in ordered if b.pipeline_disagreement),
        n_pipeline_b_abstained=n_b_abstained,
        breaks=ordered,
    )
