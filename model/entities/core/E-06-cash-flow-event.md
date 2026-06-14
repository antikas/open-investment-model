# E-06 — Cash Flow Event

A dated movement of cash between the investor and a portfolio, instrument, fund, vehicle or counterparty. The granular cash record that performance is computed from.

## Purpose

Performance — and especially money-weighted return — is a function of the timing, sign and size of every cash movement. The Cash Flow Event is that record: each dated cash movement, captured at the grain performance needs it. It is universal across asset classes — a dividend received on an equity, a coupon on a bond, a fee paid to a manager, a contribution into a fund, a distribution from one, the cash leg of a settled trade — all are Cash Flow Events.

A Cash Flow Event is the cash *consequence* of a Transaction (E-05); the two are kept separate because not every cash flow is a discrete transaction (an accrual, a fee sweep) and not every transaction is a single cash flow (a trade with separate principal and commission legs).

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `cash_flow_id` | varchar | Primary key. |
| `portfolio_id` | varchar (FK → E-03) | The portfolio the cash flow occurs in. |
| `instrument_id` | varchar (FK → E-02) | The instrument or asset the cash flow relates to; null for a portfolio-level flow. |
| `transaction_id` | varchar (FK → E-05) | The transaction that generated this cash flow, where there is one. |
| `cash_flow_date` | date | The date of the cash movement. |
| `cash_flow_type` | varchar | `contribution` / `distribution` / `coupon` / `dividend` / `fee` / `expense` / `income` / `principal` / `tax`. |
| `direction` | varchar | `inflow` or `outflow`, from the investor's perspective. |
| `amount` | decimal | The amount, signed by direction. |
| `currency` | char | The cash-flow currency. |
| `source` | varchar | The source the cash flow was captured from. |

## Notes

- Cash Flow Events are **immutable**. A correction is a new event.
- The signed, dated series of cash flows for a holding or portfolio is the direct input to internal rate of return.
- In the private-markets pack, cash flows arising from a fund are recorded at Legal Vehicle / SPV grain (PM-05) and roll up to the investment and the fund — the deal-level granularity private-markets performance needs. The core entity is the same; the private-markets pack adds the vehicle-grain rollup.

## Out of scope

- The investment event a cash flow arises from — that is E-05 Transaction; E-06 is the cash consequence, kept separate because the two grains do not always coincide.
- The *state* of what is owned — that is E-04 Holding / Position; E-06 is a dated cash movement, not a position.
- The capital-call and distribution structure of private-markets cash events — call sequencing, recallability, the waterfall — that is PM-07 Capital Call and PM-08 Distribution; E-06 records only the cash leg.
- The forward calendar of expected income payments — that is PB-08 Income Schedule; E-06 is the realised cash movement, not its projection.

## Owned and consumed by

- **Owned by:** SD-12.1 Investment Book of Record (IBOR).
- **Consumed by:** SD-09.1 Performance Measurement (the IRR input series), SD-09.8 Private-Markets Performance Analytics, SD-11.1 Cash Management, SD-12.7 Income & Distribution Processing, SD-12.10 Reconciliation, SD-12.15 Transfer Agency & Investor Dealing (the subscription and redemption settlement cash flows), SD-17.4 Investment & Portfolio Tax.

## Open extensions

- The `cash_flow_type` enumeration completed and reconciled across asset classes.
- The vehicle-grain → investment-grain → fund-grain aggregation rule (private-markets pack).
- The split of a flow into principal / income / fee / tax components for tax-lot and fee-verification use.
