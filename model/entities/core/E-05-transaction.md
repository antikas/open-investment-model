# E-05 — Transaction

The universal investment event — anything that changes a holding. A trade, a fund subscription, a capital call, a distribution, a corporate action, a transfer. The event record from which positions (E-04) are derived and cash flows (E-06) arise.

## Purpose

A holding is a *state* — what is owned as of a date. A transaction is the *event* that moved it there. Every position the investor has results from a sequence of transactions, and the audit trail of "why do we hold this, and how did we come to" is the transaction history. The entity is universal: a market trade in a listed equity, a subscription to a private fund, a capital call against a commitment, a coupon receipt, a stock split, an in-specie transfer — all are Transactions, distinguished by `transaction_type`.

This is the generalised parent of the private-markets cash events. **Capital Call (PM-07)** and **Distribution (PM-08)** are specialised transaction types in the private-markets pack; they are not a separate mechanism, they are Transactions with private-markets-specific structure.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `transaction_id` | varchar | Primary key. |
| `transaction_type` | varchar | `trade` / `subscription` / `redemption` / `capital_call` / `distribution` / `corporate_action` / `transfer` / `fee` / `income`. |
| `portfolio_id` | varchar (FK → E-03) | The portfolio affected. |
| `instrument_id` | varchar (FK → E-02) | The instrument or asset transacted. |
| `trade_date` | date | When the transaction was agreed. |
| `settlement_date` | date | When it settles; null for events without a settlement. |
| `quantity` | decimal | Units transacted, where applicable. |
| `amount_usd` | decimal | The cash amount of the transaction, signed by direction. |
| `counterparty_entity_id` | varchar (FK → E-01) | The legal entity faced in the transaction, in the counterparty role; null for events with no counterparty. |
| `status` | varchar | `pending` / `confirmed` / `settled` / `cancelled`. |
| `source` | varchar | The source the transaction was captured from. |

## Notes

- Transactions are **immutable events** — a transaction that occurred is a fact. A correction is a new transaction, not an edit.
- The transaction is the event; E-06 Cash Flow Event is the cash *consequence* of it; E-04 Holding / Position is the *state* it leaves behind. The three are distinct and all three are kept.
- The trade-lifecycle detail of a market transaction — order, execution, allocation, confirmation, settlement — is the public-markets pack's expansion of the `trade` type. The core entity names the transaction; the lifecycle depth is `PB-NN`.

## Out of scope

- The cash *consequence* of a transaction — that is E-06 Cash Flow Event; not every transaction is a single cash flow and not every cash flow is a discrete transaction.
- The *state* a transaction leaves behind — that is E-04 Holding / Position; E-05 is the event, not the resulting position.
- The trade-lifecycle detail of a market transaction — order, execution, allocation, confirmation, settlement — that is the public-markets pack's expansion (`PB-NN`), with `transaction_type = trade` as the bridge.
- The private-markets cash events and corporate actions in their specialised form — those are PM-07 Capital Call, PM-08 Distribution and PB-07 Corporate Action, which specialise E-05 rather than being separate mechanisms.

## Owned and consumed by

- **Owned by:** SD-12.1 Investment Book of Record (IBOR) — transactions update the book of record.
- **Originated by:** SD-06 Trading & Execution (trades), SD-12.8 Capital Call & Distribution Processing (private-markets cash events), SD-12.6 Corporate Actions Processing.
- **Consumed by:** SD-12.3 Trade Confirmation & Matching, SD-12.4 Trade Settlement, SD-12.10 Reconciliation, SD-09 Performance & Analytics.

## Open extensions

- The trade-lifecycle sub-model — order, execution, allocation, confirmation, settlement — in the public-markets pack.
- The corporate-action sub-model — mandatory and voluntary events and their effect on positions.
- The relationship between a Transaction and the Cash Flow Events (E-06) it generates.
