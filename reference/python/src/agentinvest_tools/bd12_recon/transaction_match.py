"""SO-12.10 transaction matching — internal book vs administrator, dual-direction residue.

The SD-12.10 *transaction matching* Service Operation: match the firm's transaction record against
the administrator's, so every settled event is confirmed on both sides. The matching key is the
transaction reference (the internal E-05 ``transaction_id`` ↔ the administrator line's ``ref``).
Emits E-24-shaped transaction-break findings with a deterministic of-record cause.

THE DUAL-INDEPENDENT-PIPELINE here is the **unmatched residue checked BOTH directions** for the
transaction surface:

- **Pipeline A — internal-not-in-external.** A settled internal transaction with no matching
  administrator line (a transaction the firm booked the administrator did not record) → a
  ``missing_transaction`` break on the internal side.
- **Pipeline B — external-not-in-internal.** An administrator line with no matching internal
  transaction (a transaction the administrator recorded the firm did not book) → a
  ``missing_transaction`` break on the external side.

Both directions are emitted — a single-direction match (only checking internal-not-in-external)
would miss the extra administrator transaction entirely; running BOTH directions is the
dual-pipeline
safety property for this surface (a one-direction match is the half-job). A transaction present on
BOTH sides but with a disagreeing amount beyond tolerance is surfaced as a
``pipeline_disagreement`` break (the two sides matched on the key but the pipelines disagree on the
value) — though the synthetic feed injects no amount-mismatch on a matched transaction, the check is
live.

Pure and deterministic: the internal settled transactions and the administrator transaction lines
are read by the data-access layers and passed in; this tool matches both directions, classifies and
surfaces. No I/O.

Honest boundary: a match over **synthetic** records, FINDINGS-ONLY — never a production
transaction reconciliation against a live administrator, never a correcting entry.
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


class InternalTransaction(BaseModel):
    """One settled internal E-05 transaction — the OpenIM-side record (the A-side)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    transaction_id: str = Field(description="The matching key (E-05 transaction id ↔ admin ref).")
    portfolio_id: str = Field(description="The portfolio affected (E-03).")
    amount_usd: Decimal = Field(description="The signed cash amount of the transaction.")


class AdminTransaction(BaseModel):
    """One administrator-statement transaction line — the counter-record (the B-side)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ref: str = Field(description="The administrator's transaction reference (matches E-05 id).")
    portfolio_id: str = Field(description="The portfolio affected (E-03).")
    amount_usd: Decimal = Field(description="The signed cash amount per the administrator.")


class ReconcileTransactionsInput(BaseModel):
    """Inputs to the transaction match — the internal settled transactions + the admin lines."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    as_of_date: date = Field(description="The date the records are matched as of.")
    internal_transactions: tuple[InternalTransaction, ...] = Field(default=())
    admin_transactions: tuple[AdminTransaction, ...] = Field(default=())


class ReconcileTransactionsOutput(BaseModel):
    """The transaction-match result — the break findings, the counts, the dual-direction summary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reconciliation_type: str = Field(default="transaction")
    as_of_date: date = Field(description="The as-of date the match honoured.")
    n_matched: int = Field(description="Transactions present on both sides (the matched set).")
    n_internal_only: int = Field(description="Internal transactions with no administrator line.")
    n_external_only: int = Field(description="Administrator lines with no internal transaction.")
    n_breaks: int = Field(description="The number of break findings emitted (both directions).")
    n_pipeline_disagreements: int = Field(
        description="Matched transactions whose amounts disagreed beyond tolerance (surfaced)."
    )
    breaks: tuple[BreakFinding, ...] = Field(
        description="The E-24-shaped transaction-break findings, ordered by record_a_ref."
    )


def reconcile_transactions(inp: ReconcileTransactionsInput) -> ReconcileTransactionsOutput:
    """Match internal vs administrator transactions BOTH directions — deterministic, surfacing.

    Pipeline A finds internal-not-in-external; Pipeline B finds external-not-in-internal; a matched
    pair with an amount disagreement beyond tolerance is surfaced as a pipeline disagreement. Pure
    and deterministic.
    """
    internal = {t.transaction_id: t for t in inp.internal_transactions}
    admin = {t.ref: t for t in inp.admin_transactions}
    internal_keys = set(internal)
    admin_keys = set(admin)
    matched = sorted(internal_keys & admin_keys)
    internal_only = sorted(internal_keys - admin_keys)
    external_only = sorted(admin_keys - internal_keys)

    findings: list[BreakFinding] = []

    # Pipeline A — internal-not-in-external (a booked transaction the administrator did not record).
    for tid in internal_only:
        t = internal[tid]
        findings.append(
            BreakFinding(
                reconciliation_type="transaction",
                record_a_ref=tid,
                record_b_ref="admin:absent",
                as_of_date=inp.as_of_date,
                difference_amount=t.amount_usd,
                difference_qty=None,
                cause_classification="missing_transaction",
                materiality=materiality_for_amount(t.amount_usd),
                pipeline_disagreement=False,
            )
        )

    # Pipeline B — external-not-in-internal (an administrator line the firm did not book).
    for ref in external_only:
        at = admin[ref]
        findings.append(
            BreakFinding(
                reconciliation_type="transaction",
                record_a_ref=ref,
                record_b_ref="internal:absent",
                as_of_date=inp.as_of_date,
                difference_amount=at.amount_usd,
                difference_qty=None,
                cause_classification="missing_transaction",
                materiality=materiality_for_amount(at.amount_usd),
                pipeline_disagreement=False,
            )
        )

    # A matched pair whose amounts disagree beyond tolerance — the two sides matched on the key but
    # the pipelines disagree on the value: surfaced as a pipeline disagreement (a data_error cause).
    n_disagree = 0
    for tid in matched:
        diff = admin[tid].amount_usd - internal[tid].amount_usd
        if abs(diff) > CASH_TOLERANCE:
            n_disagree += 1
            findings.append(
                BreakFinding(
                    reconciliation_type="transaction",
                    record_a_ref=tid,
                    record_b_ref=f"admin:{tid}",
                    as_of_date=inp.as_of_date,
                    difference_amount=diff,
                    difference_qty=None,
                    cause_classification="data_error",
                    materiality=materiality_for_amount(diff),
                    pipeline_disagreement=True,
                )
            )

    ordered = tuple(sorted(findings, key=lambda b: b.record_a_ref))
    return ReconcileTransactionsOutput(
        as_of_date=inp.as_of_date,
        n_matched=len(matched),
        n_internal_only=len(internal_only),
        n_external_only=len(external_only),
        n_breaks=len(ordered),
        n_pipeline_disagreements=n_disagree,
        breaks=ordered,
    )
