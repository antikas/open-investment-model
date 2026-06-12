"""BD-12 Investment Operations & Servicing read tools — the SD-12.1 IBOR + SD-12.2 ABOR dual book.

The reconciliation-relevant **read** surface of the two books of record, exposed as typed, pure,
per-Service-Operation tools (the ``bd09/`` precedent: one pure, deterministic, Pydantic-in/out
function per Service Operation). These tools turn the OIM-160 canonical dual book into a consumable
read surface so OIM-162's reconciliation engine has two typed pipelines to compare. They read; they
do not reconcile, and they write nothing (strictly read-only this cycle).

SD-12.1 IBOR — the real-time front-office book (E-04 ``book = ibor``, E-05, E-06):

- ``read_position`` (SO-12.1-01)                — the IBOR position per portfolio, as-of.
- ``read_ibor_cash_and_exposure`` (SO-12.1-02)  — projected cash + exposure incl. unsettled trades.
- ``read_ibor_pending_activity`` (SO-12.1-03)   — the unsettled / in-flight E-05 trades.
- ``read_transactions`` (SO-12.1-04)            — the E-05 Transaction records.
- ``read_cash_flow_events`` (SO-12.1-05)        — the E-06 Cash Flow Event records.

SD-12.2 ABOR — the accounting-basis book (E-04 ``book = abor``):

- ``read_position`` (SO-12.2-01)                — the accounting-basis position per portfolio, as-of
  (the SAME read shape over E-04, discriminated by ``book = abor``).
- ``read_abor_accrued_income`` (SO-12.2-02)     — the ABOR accrued income (an accrual divergence).
- ``read_abor_cost_basis`` (SO-12.2-03)         — the ABOR cost basis / unrealised gain.
- ``read_abor_book_close_state`` (SO-12.2-04)   — the derived period-lock status.

Shape (so the ``bd12`` dispatch service can wrap each as ``tool(input_model)`` and a journaled
step): each function takes exactly one Pydantic input model and returns one Pydantic output model.
The pure tools take the rows in (read by the ``book_of_record_data`` from the canonical
layer at the as-of) — they do not query.

Honest boundary: these are read services over the OIM-160 **synthetic** internal dual book (the dbt
canonical layer). A green read proves the typed per-book read + the as-of plumbing + the
IBOR-vs-ABOR divergence; it is **not** a production book-of-record service and **not** a read
against a live custodian.
"""

from __future__ import annotations

from agentinvest_tools.bd12.accrued_income import (
    AccruedIncomeRow,
    ReadAccruedIncomeInput,
    ReadAccruedIncomeOutput,
    read_abor_accrued_income,
)
from agentinvest_tools.bd12.book_close_state import (
    ReadBookCloseStateInput,
    ReadBookCloseStateOutput,
    read_abor_book_close_state,
)
from agentinvest_tools.bd12.cash_exposure import (
    ReadCashExposureInput,
    ReadCashExposureOutput,
    UnsettledTradeLeg,
    read_ibor_cash_and_exposure,
)
from agentinvest_tools.bd12.cash_flow_event import (
    CashFlowRow,
    ReadCashFlowsInput,
    ReadCashFlowsOutput,
    read_cash_flow_events,
)
from agentinvest_tools.bd12.cost_basis import (
    CostBasisRow,
    ReadCostBasisInput,
    ReadCostBasisOutput,
    read_abor_cost_basis,
)
from agentinvest_tools.bd12.pending_activity import (
    PendingTransaction,
    ReadPendingActivityInput,
    ReadPendingActivityOutput,
    read_ibor_pending_activity,
)
from agentinvest_tools.bd12.position import (
    Book,
    PositionRow,
    ReadPositionInput,
    ReadPositionOutput,
    read_position,
)
from agentinvest_tools.bd12.transaction import (
    ReadTransactionsInput,
    ReadTransactionsOutput,
    TransactionRow,
    read_transactions,
)

__all__ = [
    "AccruedIncomeRow",
    "Book",
    "CashFlowRow",
    "CostBasisRow",
    "PendingTransaction",
    "PositionRow",
    "ReadAccruedIncomeInput",
    "ReadAccruedIncomeOutput",
    "ReadBookCloseStateInput",
    "ReadBookCloseStateOutput",
    "ReadCashExposureInput",
    "ReadCashExposureOutput",
    "ReadCashFlowsInput",
    "ReadCashFlowsOutput",
    "ReadCostBasisInput",
    "ReadCostBasisOutput",
    "ReadPendingActivityInput",
    "ReadPendingActivityOutput",
    "ReadPositionInput",
    "ReadPositionOutput",
    "ReadTransactionsInput",
    "ReadTransactionsOutput",
    "TransactionRow",
    "UnsettledTradeLeg",
    "read_abor_accrued_income",
    "read_abor_book_close_state",
    "read_abor_cost_basis",
    "read_cash_flow_events",
    "read_ibor_cash_and_exposure",
    "read_ibor_pending_activity",
    "read_position",
    "read_transactions",
]
