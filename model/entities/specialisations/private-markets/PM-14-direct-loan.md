# PM-14 — Direct Loan

A directly-originated private loan — the borrower, the facility terms, the covenants, the drawn / undrawn position, the interest accrual, the workout state. The post-close lifecycle entity for direct private credit, modelling the loan as it lives between origination and either repayment or recovery.

**Specialises:** E-02 Instrument / Asset (`instrument_class = direct_loan`). PM-14 adds the directly-originated-debt structure — facility terms, covenants, drawn / undrawn position, recovery / workout state — to the generic instrument record. Where PM-01 Fund & Vehicle specialises E-02 for the fund-route private investment, PM-14 specialises E-02 for the directly-originated private credit position. Both share the "private, illiquid, no-universal-identifier" form of holding the private-markets pack covers.

## Purpose

Direct lending — the institutional investor originating a private loan to a borrower (or co-originating with a sponsor) — runs the BD-04 deal chain like any other direct investment: sourced, screened, diligenced, structured, approved and closed. But its post-close phase is neither company stewardship (the buyout post-close discipline, SD-04.8) nor real-asset operations (the real-asset post-close, SD-04.10): it is **credit management** — monitoring the borrower against the covenants, processing the changes the loan needs over its life, and working out the positions that deteriorate. SD-04.12 owns that discipline; PM-14 is the entity it runs on.

The Direct Loan record carries the standing terms (facility type, commitment, currency, rate structure, maturity, covenant package, payment schedule, seniority, collateral pool) and the lifecycle position (drawn vs undrawn, workout state, recovery estimate). The terms move slowly through amendments; the lifecycle position moves continuously through draws, payments, and credit-deterioration events. The record is the substrate the covenant-monitoring, amendment-processing, watch-listing and workout / restructuring operations run over.

It shares the private-markets form-of-holding properties the pack covers — private, illiquid, no universal identifier (a direct loan has no ISIN), structured monitoring against borrower reports — which is the pack's organising shape: the private, illiquid, no-universal-identifier holdings an institutional investor takes, whether through the fund route or directly originated.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `direct_loan_id` | varchar (FK → E-02) | Primary key and foreign key to E-02 Instrument / Asset; the loan is an instrument of `instrument_class = direct_loan`. |
| `borrower_entity_id` | varchar (FK → E-01) | The borrower, in the borrower role of Legal Entity. |
| `originator_entity_id` | varchar (FK → E-01) | The originator — the firm itself, or a co-lender / sponsor on a participated facility, in the originator role of Legal Entity. |
| `facility_type` | varchar | The facility type — `unitranche` / `senior_secured` / `mezzanine` / `subordinated` / `revolver` / `term_loan` / `delayed_draw`. |
| `facility_commitment_amount` | decimal | The total committed facility amount. |
| `currency` | char | The currency the facility is denominated in. |
| `drawn_amount` | decimal | The currently drawn balance. |
| `undrawn_amount` | decimal | The currently undrawn commitment available to the borrower. |
| `interest_rate_structure` | document (JSON) | The interest-rate structure — floating-index-plus-spread (e.g. SOFR + 600bps), or fixed; the PIK-toggle terms; the default-rate trigger. |
| `maturity_date` | date | The contractual maturity date — the date the facility's outstanding balance is due. |
| `covenants` | document (JSON) | The maintenance covenants and their thresholds — financial covenants (leverage, interest coverage, fixed-charge coverage), reporting covenants (the borrower's required reporting cadence), event-of-default triggers. |
| `payment_schedule` | document (JSON) | The contractual payment schedule — the interest cadence, amortisation schedule and any holiday / step-up structure. |
| `seniority_rank` | varchar | The seniority rank in the borrower's capital structure (1L senior secured, 2L, mezzanine, sub). |
| `collateral_pool_ref` | varchar | A reference to the collateral pool securing the facility, where one exists; null for unsecured facilities. |
| `workout_status` | varchar | The credit-lifecycle state — `performing` / `watch` / `non_accrual` / `restructured` / `default` / `recovered`. |
| `recovery_estimate` | decimal | The estimated recovery on the position, where the facility is in workout or default; null for performing facilities. |

## Notes

- **The instrument record carries the terms; the holding records the position.** PM-14 is the loan's *terms and lifecycle state*; the position the firm holds in the loan is E-04 Holding / Position (`book = ibor` for the live front-office view, `book = abor` for the accounting view). The same separation E-02 / E-04 maintains for listed instruments holds for direct loans.
- **`workout_status` is the load-bearing lifecycle field.** A loan moves through `performing` → `watch` → (in deterioration) `non_accrual` / `restructured` / `default` → ultimately `recovered` or written off. SD-04.12's watch-list and workout / restructuring operations turn on this field; mandate-compliance constraints often read on it (typical mandate: limits on the share of the book in `non_accrual` or `default`).
- **`covenants` is structured data, not free text.** The covenants document encodes the maintenance covenants and their thresholds so the covenant-compliance monitoring operation can run against the borrower's reported financials, not against a manually-read indenture. The full grammar — the typed financial-covenant set and the threshold-test sub-model — is an open extension.
- **The PIK toggle and default-rate trigger sit inside the interest-rate structure.** Direct loans commonly carry PIK (payment-in-kind) options where the borrower may capitalise interest under stress, and default rates that activate on covenant breach; both are part of the rate structure, not separate fields.

## Out of scope

- The position the firm holds in the loan — that is E-04 Holding / Position; PM-14 is the loan instrument's terms and lifecycle, not the position record.
- The transactions against the loan — draws, repayments, interest payments, fee receipts — those are E-05 Transaction with the appropriate `transaction_type`; PM-14 carries the drawn / undrawn aggregate, not the individual events.
- The cash flows the loan produces — those are E-06 Cash Flow Event records; PM-14 carries the payment schedule, not the realised cash record.
- The credit *rating* of the borrower — that is E-38 Internal Credit Rating, owned by SD-02.3 Credit Research & Analysis; PM-14 is the loan facility, not the borrower's standing creditworthiness.
- The fund-route private-credit investment — that is a fund interest (PM-01) the firm holds via a private-credit fund's LP commitment; PM-14 is the *directly-originated* loan, not the fund-invested-through alternative.
- The credit-agreement legal document itself — that is recorded via E-15 Document Metadata; PM-14 references the agreement, the agreement is not stored on the loan record.

## Owned and consumed by

- **Owned by:** SD-04.12 Loan Monitoring & Workout — the post-close credit-management capability that monitors the borrower against the covenants, processes the amendments, watch-lists deteriorating credits and runs the workout / restructuring operations.
- **Consumed by:** SD-04.7 Co-Investment Management (where the firm has co-originated a direct-credit position alongside a sponsor — the co-invest record references the loan), SD-11.4 Margin & Collateral Operations (the cash-flow accounting on the facility), SD-11.5 Collateral Optimisation (where the loan's collateral pool sits in the firm-wide collateral inventory), SD-12.8 Capital Call & Distribution Processing (where the loan sits inside a private-credit fund vehicle the firm operates — the fund-route case), SD-09.1 Performance Measurement (the realised return on the loan), SD-07.2 Credit & Counterparty Risk Management (the credit-risk view of the position).

## Open extensions

- The structured grammar for `covenants` — the typed financial-covenant set, the threshold-test sub-model and the covenant-compliance monitoring contract with SD-04.12.
- The amendment-and-waiver sub-model — how amendments to the facility (covenant amendments, maturity extensions, structure changes) flow through the loan record without losing the original terms.
- The collateral-pool entity for secured facilities — whether the collateral pool warrants its own first-class record alongside PM-14, or is referenced through E-26 Collateral Position.
- The workout / restructuring sub-model — the typed structure of a restructured facility, including the relationship between the original loan record and a restructured replacement.
- The cross-mode boundary with PB-02 Debt Instrument — PB-02 is the listed-debt instrument (a bond, a syndicated note); PM-14 is the directly-originated private loan. Where a privately-originated loan is later syndicated and listed, the boundary case is open.
