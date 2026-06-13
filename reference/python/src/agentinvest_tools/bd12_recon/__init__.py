"""BD-12 SD-12.10 reconciliation engine — the dual-independent-pipeline reconcile.

The deterministic reconciliation engine: the four SD-12.10 reconcile tools (position · cash ·
transaction-matching · IBOR/ABOR) that consume the internal book read surface + the external
comparator feed and emit **E-24 Reconciliation Break** findings with a deterministic
of-record cause, persisted append-only to an engine-owned break store. The ``bd12`` read precedent:
one pure, deterministic, Pydantic-in/out tool per Service Operation.

The four reconcile tools (mapping SD-12.10's Service Operations 1:1):

- ``reconcile_position`` (SO-12.10 position reconciliation)        — internal book vs custodian.
- ``reconcile_cash`` (SO-12.10 cash reconciliation)                — custodian vs admin cash.
- ``reconcile_transactions`` (SO-12.10 transaction matching)       — internal vs admin, both
  directions.
- ``reconcile_ibor_abor`` (SO-12.10 IBOR/ABOR reconciliation)      — the two internal books.

THE LOAD-BEARING PROPERTIES:

1. **The dual-independent-pipeline** — each reconcile computes its result two independent ways and
   surfaces any meta-disagreement (never silently reconciles).
2. **Deterministic of-record cause-classification → ``unexplained`` on a miss** — rules over neutral
   observable evidence, NO LLM (the propose-only LLM operates over the ``unexplained`` residue,
   downstream of the rules).
3. **Append-only, insert-only, immutable break persistence** — breaks are appended at ``status =
   open``; there is no update / no status-transition / no correcting-entry path (those live behind
   the breach gate).

Honest boundary: these are reconciles over **synthetic** data (the real internal dual
book vs a synthetic custodian/admin feed with labelled breaks), FINDINGS-ONLY — never a production
reconciliation against a live custodian, never a resolved/gated correcting entry.
"""

from __future__ import annotations

from agentinvest_tools.bd12_recon.break_finding import (
    CASH_TOLERANCE,
    PRICE_TOLERANCE_BPS,
    QTY_TOLERANCE,
    BreakFinding,
    CauseClassification,
    Materiality,
    ReconciliationType,
    classify_value_diffs,
    materiality_for_amount,
    price_diff_exceeds_band,
)
from agentinvest_tools.bd12_recon.break_store import (
    BreakStoreUnavailableError,
    StoredBreak,
    append_breaks,
    count_breaks,
    read_breaks,
    resolve_break_store_path,
)
from agentinvest_tools.bd12_recon.cash_reconcile import (
    AdminCashBalance,
    CustodianCashBalance,
    InternalCashReplay,
    ReconcileCashInput,
    ReconcileCashOutput,
    reconcile_cash,
)
from agentinvest_tools.bd12_recon.evidence_bundle import (
    EvidenceBundle,
    assemble_bundle,
    assemble_value_context,
)
from agentinvest_tools.bd12_recon.ibor_abor_reconcile import (
    BookPositionRow,
    IborAborInFlightTrade,
    ReconcileIborAborInput,
    ReconcileIborAborOutput,
    reconcile_ibor_abor,
)
from agentinvest_tools.bd12_recon.position_reconcile import (
    CustodianPositionRow,
    InFlightTrade,
    InternalPositionRow,
    ReconcilePositionInput,
    ReconcilePositionOutput,
    reconcile_position,
)
from agentinvest_tools.bd12_recon.proposal_store import (
    ProposalStoreUnavailableError,
    StoredProposal,
    append_proposals,
    count_proposals,
    read_proposals,
    resolve_proposal_store_path,
)
from agentinvest_tools.bd12_recon.proposer import (
    CauseProposal,
    CauseProposalSchema,
    ProposerDeterministicError,
    ProposerTransientError,
    build_proposer_prompt,
    propose_cause,
)
from agentinvest_tools.bd12_recon.transaction_match import (
    AdminTransaction,
    InternalTransaction,
    ReconcileTransactionsInput,
    ReconcileTransactionsOutput,
    reconcile_transactions,
)

__all__ = [
    "CASH_TOLERANCE",
    "PRICE_TOLERANCE_BPS",
    "QTY_TOLERANCE",
    "AdminCashBalance",
    "AdminTransaction",
    "BookPositionRow",
    "BreakFinding",
    "BreakStoreUnavailableError",
    "CauseClassification",
    "CauseProposal",
    "CauseProposalSchema",
    "CustodianCashBalance",
    "CustodianPositionRow",
    "EvidenceBundle",
    "IborAborInFlightTrade",
    "InFlightTrade",
    "InternalCashReplay",
    "InternalPositionRow",
    "InternalTransaction",
    "Materiality",
    "ProposalStoreUnavailableError",
    "ProposerDeterministicError",
    "ProposerTransientError",
    "ReconcileCashInput",
    "ReconcileCashOutput",
    "ReconcileIborAborInput",
    "ReconcileIborAborOutput",
    "ReconcilePositionInput",
    "ReconcilePositionOutput",
    "ReconcileTransactionsInput",
    "ReconcileTransactionsOutput",
    "ReconciliationType",
    "StoredBreak",
    "StoredProposal",
    "append_breaks",
    "append_proposals",
    "assemble_bundle",
    "assemble_value_context",
    "build_proposer_prompt",
    "classify_value_diffs",
    "count_breaks",
    "count_proposals",
    "materiality_for_amount",
    "price_diff_exceeds_band",
    "propose_cause",
    "read_breaks",
    "read_proposals",
    "reconcile_cash",
    "reconcile_ibor_abor",
    "reconcile_position",
    "reconcile_transactions",
    "resolve_break_store_path",
    "resolve_proposal_store_path",
]
