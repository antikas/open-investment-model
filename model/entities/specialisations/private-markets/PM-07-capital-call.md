# PM-07 — Capital Call

A drawdown event against a commitment (PM-06) — the fund calling part of the capital the LP pledged.

**Specialises:** E-05 Transaction (`transaction_type = capital_call`), with a Cash Flow Event (E-06) as its cash consequence. PM-07 adds the private-markets structure — the call sequence, the cumulative-called tracking, the relationship to the commitment.

## Purpose

A fund draws committed capital down over its investment period through a sequence of capital calls. Each call is a dated demand for cash the LP must meet, usually within a short notice window. Capital calls are the cash-out side of the J-curve and the direct driver of funding-liquidity requirements.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `call_id` | varchar | Primary key. |
| `fund_id` | varchar (FK → PM-01) | The fund issuing the call. |
| `commitment_id` | varchar (FK → PM-06) | The commitment the call draws against. |
| `call_date` | date | The date of the call notice. |
| `due_date` | date | The date payment is due. |
| `amount_usd` | decimal | The amount called. |
| `call_number` | int | The sequence number of the call within the fund. |
| `cumulative_called_pct` | float | Cumulative capital called as a percentage of commitment, after this call. |
| `purpose` | varchar | What the call funds — investment, management fee, expenses. |
| `source` | varchar | The source document the call was captured from. |

## Notes

- Capital calls are **immutable events** — a call, once issued, is a fact. Corrections are new records.
- The call is processed operationally by SD-12.8; the funding to meet it is arranged by SD-11.6.

## Out of scope

- The generic transaction record a capital call specialises — that is E-05 Transaction of `transaction_type = capital_call`, with a core E-06 Cash Flow Event as its cash consequence.
- The commitment the call draws against — that is PM-06 LP Commitment, referenced through `commitment_id`; PM-07 is the drawdown event, not the commitment.
- The return of capital in the other direction — that is PM-08 Distribution; PM-07 is the cash-out leg only.
- The arrangement of funding to meet a call — that is SD-11.6 Fund Finance & Capital-Call Liquidity; PM-07 records the call, not how it is financed.

## Owned and consumed by

- **Owned by:** SD-12.8 Capital Call & Distribution Processing.
- **Consumed by:** SD-11.6 Fund Finance & Capital-Call Liquidity, SD-09.7 Private-Markets Cash-Flow Forecasting, SD-09.1 Performance Measurement (the cash-out leg of IRR), SD-05.6 Liquidity-Aware Portfolio Management.

## Open extensions

- Recallable distributions — capital returned to the LP that the fund may call again — and how a recall relates to the original call and distribution.
- The split of a call by purpose (investment vs fee vs expense) for fee verification.
