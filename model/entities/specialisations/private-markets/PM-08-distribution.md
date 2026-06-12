# PM-08 — Distribution

A return of capital or gain from a fund (PM-01) to its LPs — the cash-in side of the private-markets relationship.

**Specialises:** E-05 Transaction (`transaction_type = distribution`), with a Cash Flow Event (E-06) as its cash consequence. PM-08 adds the private-markets structure — distribution typing, recallability, the relationship to the waterfall.

## Purpose

As a fund realises investments, it distributes proceeds to its LPs. Distributions are the cash-in leg of the J-curve and of every money-weighted return. The **distribution type** matters: a return of capital, investment income, and a realised gain are economically and often for tax purposes distinct, and performance measurement depends on classifying them correctly. The distribution sequence drives DPI and feeds cash-flow forecasting.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `dist_id` | varchar | Primary key. |
| `fund_id` | varchar (FK → PM-01) | The fund making the distribution. |
| `commitment_id` | varchar (FK → PM-06) | The commitment the distribution is paid against. |
| `dist_date` | date | The date of the distribution. |
| `amount_usd` | decimal | The amount distributed. |
| `dist_type` | varchar | `return_of_capital` / `income` / `gain`. |
| `recallable` | boolean | Whether the fund may recall this distribution as future callable capital. |
| `source` | varchar | The source document the distribution was captured from. |

## Notes

- Distributions are **immutable events**. Corrections are new records.
- A `recallable` distribution restores callable capacity to the related commitment (PM-06) — relevant to unfunded-commitment liquidity modelling.
- `dist_type` classification is consumed by tax processing (SD-17.4) as well as performance.

## Out of scope

- The generic transaction record a distribution specialises — that is E-05 Transaction of `transaction_type = distribution`, with a core E-06 Cash Flow Event as its cash consequence.
- The drawdown of capital in the other direction — that is PM-07 Capital Call; PM-08 is the cash-in leg only.
- The commitment the distribution is paid against — that is PM-06 LP Commitment, referenced through `commitment_id`.
- The distribution waterfall — how a gross distribution splits between LP return, preferred return, catch-up and carry — that is governed by PM-10 Fund Terms and is an open extension.

## Owned and consumed by

- **Owned by:** SD-12.8 Capital Call & Distribution Processing.
- **Consumed by:** SD-09.1 Performance Measurement (the cash-in leg of IRR and DPI), SD-09.7 Private-Markets Cash-Flow Forecasting, SD-12.7 Income & Distribution Processing, SD-17.4 Investment & Portfolio Tax, SD-05.6 Liquidity-Aware Portfolio Management.

## Open extensions

- The distribution waterfall — how a gross distribution splits between LP return, preferred return, GP catch-up and carried interest (see PM-10 Fund Terms).
- In-kind distributions (securities rather than cash) and their valuation.
