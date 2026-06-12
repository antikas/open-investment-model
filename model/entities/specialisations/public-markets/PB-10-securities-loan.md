# PB-10 — Securities Loan

A per-loan record of a lent security — the borrower, the quantity, the fee, the term, the recall status, and the collateral held against it. The loan as a relationship with its own lifecycle, which a holding's lent flag cannot carry.

**Specialises:** E-04 Holding / Position. A securities loan is a condition of a holding — the security is lent — but it is more than a flag: it is a relationship with a borrower, a fee, a term, a recall status and a collateral leg, none of which a position record carries. PB-10 is the lifecycle expansion of the lent state, the way PB-03 Order expands the trade event. Its collateral leg references E-26 Collateral Position. The loan is governed by a GMSLA master agreement — the securities-lending analogue of the ISDA master agreement that governs derivatives.

## Purpose

A securities loan lends a holding to a borrower against collateral, for a fee, until it is recalled or returned. The lent *state* can be read off a holding (E-04) as "lent or not", but the loan itself is a relationship that the holding flag cannot represent: to whom it is lent, at what fee, since when, recallable when, against what collateral, earning what revenue. PB-10 is that per-loan record — the head of the lending relationship that the fee accrual, the borrower exposure, the recall-versus-record-date control and the collateral all hang from.

Modelling the loan distinctly matters because the lending book has economics and controls a holding flag cannot carry: lending revenue must be accrued and accounted, borrower exposure must be aggregated, and a lent security must be recalled in time to vote it or to settle a sale. The collateral held against the loan is not modelled afresh here — it is an E-26 Collateral Position, the shared collateral abstraction, referenced through the loan's collateral leg.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `loan_id` | varchar | Primary key. |
| `position_id` | varchar (FK → E-04) | The holding being lent — the **logical-holding identity** `position_id`, shared across E-04's two books of record, not a single book-row. A loan is one real-world lending relationship against the logical holding, not a per-book record, so the reference is to the logical holding, not to `(position_id, book)`. The lent state on the position is a condition; PB-10 is the loan against it. |
| `instrument_id` | varchar (FK → E-02) | The security on loan. |
| `borrower_entity_id` | varchar (FK → E-01) | The borrower, a Legal Entity in the counterparty role. |
| `lent_quantity` | decimal | The quantity on loan. |
| `fee_rate` | decimal | The lending fee rate the borrower pays. |
| `loan_start_date` | date | When the loan opened. |
| `term` | varchar | `open` (recallable on notice) / a fixed term. |
| `recall_status` | varchar | `none` / `recall_issued` / `recall_pending` / `returned` — the recall lifecycle state. |
| `collateral_position_id` | varchar (FK → E-26) | The collateral held against the loan — an E-26 Collateral Position; the shared collateral abstraction, not modelled afresh here. |
| `revenue_accrued` | decimal | Lending revenue accrued on the loan to date. |
| `loan_status` | varchar | `open` / `recalled` / `returned` / `closed`. |
| `master_agreement_ref` | varchar | The GMSLA master agreement the loan is governed under. |

## Notes

- A securities loan is **public-markets-only** — it is the lending of listed securities; there is no analogue in the fund-investing route.
- **The loan references the logical holding, not a book-row.** E-04's identity is the composite `(position_id, book)`, but a securities loan is one real-world lending relationship — a quantity of a security lent to a borrower under a GMSLA — that attaches to the logical holding, not to a single accounting book. So PB-10's `position_id` FK references the **logical-holding identity** (`position_id`, shared across E-04's two books), book-agnostic by design, the same grain at which a Valuation (E-07) references E-04 — not the composite `(position_id, book)`.
- The collateral leg references E-26 Collateral Position rather than carrying its own collateral model: the collateral against a securities loan is the same kind of fact as collateral against a derivatives margin relationship — an asset, valued, haircut, posted in a direction — and is modelled once, in E-26.
- The recall lifecycle is a control, not just a status: a lent security must be recalled in time to exercise a vote (PB-11) or to settle a sale, and `recall_status` is the state that control runs on.

## Out of scope

- The lent *state* as a condition of the holding — that is a flag on E-04 Holding / Position; PB-10 is the loan relationship the flag points to, not the position itself.
- The collateral held against the loan — that is an E-26 Collateral Position, referenced through `collateral_position_id`; PB-10 does not re-model collateral.
- The lending fee as a cash movement — that is an E-06 Cash Flow Event; PB-10 carries the accrued revenue, the realised cash is the cash-flow record.

## Owned and consumed by

- **Owned by:** SD-12.13 Securities Lending Operations.
- **Consumed by:** SD-07.2 Credit & Counterparty Risk Management (borrower exposure), SD-12.6 Corporate Actions Processing (recall ahead of a corporate action), SD-12.12 Proxy Voting & Stewardship Operations (recall to vote), SD-09.1 Performance Measurement (lending revenue), SD-12.2 Accounting Book of Record (ABOR).

## Open extensions

- The collateral-mark and margining sub-model — the daily mark of the loan's collateral against the lent value, sharing the E-26 / DR-04 collateral machinery.
- The agent-lending model — lending run through a lending agent rather than directly.
- The lending-revenue split between the fund and the lending agent.
