# PB-05 — Allocation

The apportionment of an executed trade across the portfolios and accounts it was traded for — the step that turns a market fill into per-portfolio positions.

**Specialises:** E-05 Transaction (`transaction_type = trade`). Allocation is the lifecycle stage between Execution (PB-04) and Settlement (PB-06). One execution, or a set of executions on the same order, fans out into one allocation row per portfolio. It corresponds to the FIX *Allocation Instruction* (MsgType J) and *Allocation Report* (MsgType R).

## Purpose

An institutional desk frequently trades a single block in the market on behalf of several portfolios — a model-portfolio rebalance, a multi-mandate buy, a manager running parallel accounts. The block is one or more executions; the portfolios that own the result are determined by allocation. PB-05 is the record of one portfolio's share of a block. It exists because **the execution does not carry a portfolio** — a block fill is portfolio-agnostic by construction — and the fair, policy-driven split across accounts is itself a governed capability (SD-06.5 Trade Allocation), not a clerical detail. Allocation is also where a partial fill must be apportioned: if a block only half-fills, every account's share is scaled, and the allocation policy decides how.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `allocation_id` | varchar | Primary key. |
| `order_id` | varchar (FK → PB-03) | The order the allocation belongs to. |
| `portfolio_id` | varchar (FK → E-03) | The portfolio / account receiving this share of the trade. |
| `instrument_id` | varchar (FK → E-02) | The instrument allocated. |
| `side` | varchar | `buy` / `sell` / `sell_short` / `buy_to_cover`. |
| `allocated_quantity` | decimal | The quantity apportioned to this portfolio. |
| `average_price` | decimal | The volume-weighted average execution price applied to this allocation. |
| `gross_amount` | decimal | Allocated quantity × average price. |
| `commission` | decimal | Commission apportioned to this portfolio. |
| `taxes_and_fees` | decimal | Transaction taxes and fees apportioned to this portfolio. |
| `net_amount` | decimal | The net cash consideration for this portfolio's share. |
| `allocation_method` | varchar | `pro_rata` / `pre_trade` / `model_weight` / `manual` — how the split was derived. |
| `allocation_status` | varchar | `proposed` / `confirmed` / `rejected` — the SD-06.5 / SD-12.3 sign-off state. |
| `custodian_entity_id` | varchar (FK → E-01) | The custodian holding the receiving account, in the `custodian` role. |
| `allocation_datetime` | timestamp | When the allocation was struck. |

## Notes

- Every account on a block receives **one average price** — the volume-weighted average of the executions on the order — so no account is advantaged by the sequence in which the block was worked. This fairness rule is the reason `average_price` lives on the allocation and not on the execution.
- A partial fill is apportioned by `allocation_method`: `pro_rata` scales every account down by the same fill ratio; `pre_trade` honours the account quantities fixed on the order; `model_weight` re-derives the split from current model weights. The method is policy, governed by SD-06.5.
- The allocation is the grain at which the trade reaches the Investment Book of Record — IBOR (E-04) posts per-portfolio positions from PB-05 rows, not from PB-04 executions.
- The sum of `allocated_quantity` across a block's allocations equals the block's `filled_quantity` — a reconciliation invariant checked by SD-12.10.

## Out of scope

- The market fill being apportioned — that is PB-04 Execution; PB-05 turns one or more executions into per-portfolio shares.
- The order the allocation belongs to — that is PB-03 Order, referenced through `order_id`.
- The settlement of each portfolio's share — that is PB-06 Settlement Instruction, which settles at the allocation grain.
- The fair-allocation policy itself modelled as computation-as-data — named as an open extension; the entity carries `allocation_method` as an enumerated discriminator.

## Owned and consumed by

- **Owned by:** SD-06.5 Trade Allocation.
- **Consumed by:** SD-12.3 Trade Confirmation & Matching, SD-12.4 Trade Settlement, SD-12.1 Investment Book of Record (IBOR), SD-12.2 Accounting Book of Record (ABOR), SD-12.10 Reconciliation, SD-10.1 Investment Guideline Monitoring (post-trade sweep).

## Open extensions

- The fair-allocation policy itself modelled as computation-as-data, in the shape PM-10 Fund Terms uses for LPA economics.
- The relationship between an allocation and the multiple executions whose average price it carries.
- Cross-account netting where the same block buys for one account and sells for another.
