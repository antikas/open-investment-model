# FO-06 — Fee Accrual

The computed fee figure of record for a fund or share/unit class over a period — the amount that management, performance or expense fees accrued to, as calculated by the fee-and-expense processing function, with full provenance back to the in-force fee definition that produced it. The difference between the gross accrual and the net charge after expense-cap, fee-waiver and reimbursement application makes the disclosed ongoing charges figure (OCF) reconstructable from stored artefacts. The OCF (the UCITS KIID / PRIIPs KID cost-disclosure figure: management fee plus OCF-eligible operating expenses, performance fees and transaction costs excluded) and the TER (total expense ratio, an older and broader disclosure measure with a different scope) are distinct; FO-06 supports reconstruction of both but they are not synonymous.

**Specialises:** E-07 Valuation. Fee Accrual is a computed, provenance-bearing, append-only figure — the fee analogue of a Valuation. It is a stored result (not a recalculation) of applying an in-force fee definition to a period and a subject, for the same governance reason E-07 is stored: the accrued fee is booked into NAV (SD-12.9), disclosed to investors (SD-16.2 / SD-15.14), and must be answerable from a record with full provenance rather than derived from a live recomputation that may no longer reproduce the original. The computed-figure-of-record family — E-07 Valuation, E-19 Risk Measurement, E-20 Performance Result, E-31 Goal Progress Measurement — establishes the pattern; FO-06 is that pattern applied to the fee computation surface.

**Why E-07 Valuation, not E-20 Performance Result.** A fee accrual is a value computation over a period applied to a subject (a fund or class), not a return figure. E-07 is the universal point-in-time computed value — valued at a method, with provenance — and the fee amount is precisely that: a method-stamped computed value, effective-dated, append-only, stored with the reference to the definition that produced it. E-20 is the return-computation analogue; forcing a fee into the return family would obscure the economic nature of the figure. E-07 specialises more cleanly: the fee is what the fund *costs* per period, not how the fund *performed* per period.

**Ownership boundary (resolves the share-class fee-boundary: the schedule lives on the fund-terms / share-class master, the computed amount here).**

- Fee **definition / schedule** → stays on PM-10 Fund Terms (closed-end LPA shape) and FO-02 Share / Unit Class `class_fee_schedule` (open-ended shape). FO-06 reads these; it does not duplicate the formula.
- Fee **computed amount** → FO-06, owned by **SD-12.11 Expense, Fee & Carry Processing** (the calculator and verifier: "SD-12.11 produces and checks the amount").
- **NAV booking** of the accrual → **SD-12.9 Fund Accounting & NAV** consumes FO-06 and books the accrued fee into the struck NAV (SD-12.11's own text: "SD-12.9 accrues … SD-12.11 calculates … SD-12.9 books it"). No formula is duplicated; no figure is double-owned.

## Purpose

A fund manager that operates collective investment vehicles accrues fees against the fund continuously — daily, weekly or at the dealing cycle — and crystallises them periodically into actual charges. The accrued management fee reduces the fund's NAV as it builds; the performance fee crystallises on the relevant crystallisation event (anniversary, quarter-end, dealing point or high-water mark crossing). A retail fund's ongoing charges figure (OCF) — the UCITS KIID / PRIIPs KID cost disclosure — is the sum of management fees and OCF-eligible operating expenses (administration, audit, depositary, legal, registration, regulatory) expressed as a percentage of average NAV over the period; performance fees and transaction costs are excluded from the OCF and disclosed separately or at a different reporting grain. The investor and regulator need to know that the disclosed charge is reconstructable from stored records.

FO-06 is that stored record. It captures, for each fund or class and each period, the gross fee amount, the formula-version provenance, and the expense-cap / fee-waiver / reimbursement chain that nets the gross amount down to the charge that flows into NAV and into the regulatory disclosure. With FO-06 in place, the OCF reconstruction chain is: sum `net_charge` for `fee_type = management` plus `net_charge` for `fee_type = expense` (OCF-eligible operating/service expenses — administration, audit, depositary, legal, registration, regulatory — excluding transaction costs) over the period → divide by average class-grain NAV over the period → the published OCF. Performance fees (`fee_type = performance`) are excluded from the OCF and disclosed separately. Transaction costs are trade-level costs, excluded from the OCF by the ESMA ongoing-charges methodology. Every step traces to a stored FO-06 row and class-grain E-07 record, not a recalculation. TER (total expense ratio) is an older, broader measure with a different scope; the reconstruction stated here produces the OCF as defined under the UCITS KIID / PRIIPs KID lineage.

FO-06 is distinct from:

- **FO-02 `class_fee_schedule`** — the static fee *terms* record (the rate, the formula type, the performance-fee terms). FO-06 is the *computed result* of applying those terms to a period. PM-10 Fund Terms is the analogous static terms record for the closed-end LPA shape; FO-06 reads both, duplicates neither.
- **E-06 Cash Flow Event (`cash_flow_type = fee` / `expense`)** — the cash event when the fee is *paid*. FO-06 is the accrual record; E-06 is the settlement event. The two coexist: the accrual builds in FO-06 rows; the payment crystallises into an E-06 row and zeroes the accrual.
- **SD-12.9 Fund Accounting & NAV** — SD-12.9 *books* the accrued fee into the NAV; FO-06 is the amount it books. SD-12.9 consumes FO-06.

## Attribute schema

### Identity and relationship

| Column | Type | Definition |
|---|---|---|
| `fee_accrual_id` | varchar | **Golden key.** The OpenIM-assigned canonical identifier for this fee accrual record. |
| `fund_product_id` | varchar (FK → FO-01) | The fund to which this fee accrual applies. Required — every fee accrual attaches to an issued fund. |
| `share_class_id` | varchar (FK → FO-02) | The share or unit class to which this fee accrual applies, where the fee is class-specific (management fee, OCF, performance fee). Null only for a fund-level expense that is not yet allocated to classes. Where `share_class_id` is populated, `fund_product_id` may be derived from `FO-02.fund_product_id`. |
| `asset_class` | int (FK → E-09) | The asset class of the class or fund, as an integer foreign key following the integer-FK discipline. Inherited via `FO-02.asset_class` → `FO-01.asset_class` → `E-09`. |

### Period and grain

| Column | Type | Definition |
|---|---|---|
| `period_start` | date | The start of the accrual period (inclusive). |
| `period_end` | date | The end of the accrual period (inclusive). The accrual covers this period. |
| `fee_type` | varchar | The type of fee accrued: `management` (the annual management charge, accrued daily or per-period from the rate in the fee schedule) / `performance` (carried interest or performance fee, accruing against the hurdle and HWM) / `expense` (OCF-eligible operating/service expenses — administration, audit, depositary, legal, registration, regulatory costs charged at fund or class level). Transaction costs (brokerage, taxes, market impact) are excluded from `expense`: they are trade-level costs at the public-markets dealing grain (E-05), not fund-operating charges, and the ESMA ongoing-charges methodology excludes them from the OCF. The `fee_type` value partitions the accrual: `management` + `expense` form the OCF numerator; `performance` is disclosed separately. |

### Computed amounts

| Column | Type | Definition |
|---|---|---|
| `accrued_amount` | decimal | The gross fee amount accrued for this period, in `currency`, before any waiver, cap or reimbursement. This is the amount that would be booked into NAV in the absence of any reduction. |
| `crystallised_amount` | decimal | The fee amount that has crystallised in this period — i.e. has moved from an accrual to a payable. For management fees this is typically the periodic charge; for performance fees this is the amount crystallised on the crystallisation event (anniversary, quarter-end, or high-water-mark crossing as defined in the fee schedule). Null where the fee has accrued but not yet crystallised. |
| `currency` | char(3) | The currency of the fee amounts, ISO 4217. Derived from `FO-02.class_currency`. |

### Expense-cap / fee-waiver / reimbursement chain (OCF reconstruction support)

| Column | Type | Definition |
|---|---|---|
| `waiver_cap_amount` | decimal | The amount by which the gross accrued fee is reduced by an expense cap or fee waiver applying to this class or fund in this period. An expense cap sets a maximum OCF percentage; if the gross accrual would produce an OCF above the cap, the difference is the cap reduction. A fee waiver is a manager's discretionary reduction of the gross fee. Both are stored here as a non-negative amount. Null where no cap or waiver applies. |
| `reimbursement_amount` | decimal | The amount reimbursed to the fund (from the manager or from a third party) in this period, reducing the net charge below the gross-minus-cap amount. A management-company reimbursement of fund-level operating costs is a common form. Stored as a non-negative amount. Null where no reimbursement applies. |
| `net_charge` | decimal | The net fee charge booked into the fund's NAV and carried to the investor disclosure for this period and this `fee_type`: `net_charge = accrued_amount − waiver_cap_amount − reimbursement_amount`. This is the figure SD-12.9 books; for `fee_type = management` and `fee_type = expense`, it is the figure that flows into the OCF reconstruction. Stored as a derived field (not recomputable from live rates without provenance). |

**OCF reconstruction chain (explicit).** Given FO-06 rows for a fund/class and a year:
1. Sum `net_charge` for `fee_type = management` plus `net_charge` for `fee_type = expense` (OCF-eligible operating/service expenses; transaction costs excluded) over the period. Do NOT include `fee_type = performance` in this sum — performance fees are excluded from the OCF by the ESMA ongoing-charges methodology and are disclosed separately.
2. Divide by average NAV over the period (the average of class-grain E-07 `value_usd` records for the class, denominated in class currency).
3. The result is the **OCF** (ongoing charges figure) for the period, as defined under the UCITS KIID / PRIIPs KID regulatory lineage. TER (total expense ratio) is an older, broader disclosure measure with a different scope; they are not the same figure and should not be used interchangeably. Each step traces to stored FO-06 rows and class-grain E-07 records — no recomputation from live rates is needed. The NAV-per-unit KIID/KID design note (SD-12.9) applies here symmetrically — the disclosed OCF is the rendering of these FO-06 figures of record, not an independently maintained number.

### Formula provenance (computation-as-data)

| Column | Type | Definition |
|---|---|---|
| `definition_type` | varchar | `FIXED` (the fee was computed from a scalar rate) or `COMPUTED` (the fee was computed from a structured formula specification). Mirrors the `definition_type` vocabulary on PM-10 Fund Terms and FO-02 `class_fee_schedule`. |
| `formula_spec_ref` | varchar | A reference identifier to the in-force fee definition that produced this accrual — either a `PM-10.terms_id` (closed-end LPA shape: references the specific PM-10 FundTerms version in force during the period) or a `FO-02.share_class_id` + schedule version token (open-ended shape: references the FO-02 class fee schedule version in force). FO-06 reads the formula; it does not duplicate it. The formula lives on PM-10 or FO-02; FO-06 records which version produced this figure. |
| `methodology_version` | varchar | The version of the calculation methodology applied (e.g. the fee-calculation engine version or the OCF calculation basis), for audit traceability. |

### Performance-fee mechanics

| Column | Type | Definition |
|---|---|---|
| `hwm_applied` | decimal | The high-water mark value applied in computing the performance fee for this period, where `fee_type = performance` and the fee schedule uses a high-water mark construct. Null for management and expense fee types, and for performance fee types that do not use a HWM (e.g. a hurdle-only structure). Derived from the PM-10 HurdleDefinition or FO-02 `class_fee_schedule` performance-fee terms. |
| `hurdle_applied` | decimal | The hurdle rate applied in computing the performance fee for this period, where `fee_type = performance` and a hurdle applies. Null where no hurdle applies. |
| `crystallisation_trigger` | varchar | The event that triggered crystallisation for this record, where `crystallised_amount` is non-null: `anniversary` / `quarter_end` / `dealing_point` / `hwm_crossing` / `fund_close`. Null where the fee has not yet crystallised. |

### Effective-dating and append-only discipline

| Column | Type | Definition |
|---|---|---|
| `effective_from` | date | The date from which this FO-06 record is the authoritative accrual for this period and `fee_type`. |
| `effective_to` | date | The date this record was superseded by a correcting or restated record; null while current. |
| `record_created_at` | timestamp | The timestamp at which this record was created in the system of record. The append-only discipline: a correction or restatement is a new FO-06 row with a new `effective_from`, not an overwrite. Prior rows are never deleted or amended. |
| `provenance` | varchar | The source or trigger of this accrual record — `calculated` (produced by SD-12.11 at the accrual run), `verified` (SD-12.11 independently verified a manager-billed figure against this accrual), `corrected` (a restating record that supersedes a prior accrual). |

## Notes

- **Append-only.** FO-06 follows the computed-figure-of-record discipline: once created, a row is never overwritten. A correction inserts a new row with `effective_from` set to the correction date; `effective_to` on the prior row is set to the same date. The set of FO-06 rows for a (fund, class, period, fee_type) is the accrual history.
- **Class-grain is the primary grain.** The fee accrual attaches at share/unit-class grain wherever the fee schedule is per-class (which is the standard for registered open-ended funds). Fund-level expenses that have not yet been allocated to classes are carried with `share_class_id = null` and are a transitional state pending allocation.
- **Two-component OCF reconstruction (management + OCF-eligible expense).** The OCF is not a stored scalar; it is reconstructed from the sum of `net_charge` for `fee_type = management` plus `net_charge` for `fee_type = expense` (excluding performance fees and transaction costs), divided by average NAV. This reconstruction is deterministic from stored records and carries the audit trail that disclosure standards require. Performance fees are stored in FO-06 as `fee_type = performance` and are disclosed separately, not included in the OCF. TER (total expense ratio) is a related but distinct, broader disclosure measure; FO-06 supports reconstruction of both if needed, but they are not the same figure.
- **FK targets resolve without cross-pack complications.** `fund_product_id` → FO-01 and `share_class_id` → FO-02 are within the fund-operations pack; `asset_class` → E-09 is a core-entity FK. The `formula_spec_ref` is a provenance pointer, not a formal FK, because it references either a PM-10 or a FO-02 schedule-version token depending on the fund structure — noted as a generator-rendered pack-level reference, not requiring a hand-edited core ERD edge.

## Out of scope

- The fee *terms* (the rate, the formula, the performance-fee construct) — those are PM-10 Fund Terms (closed-end LPA) and FO-02 `class_fee_schedule` (open-ended). FO-06 is the computed result of applying those terms, not the terms themselves.
- The cash *payment* of the fee — that is an E-06 Cash Flow Event (`cash_flow_type = fee`). FO-06 is the accrual; the cash movement when the fee is settled is E-06.
- The booking of the fee into the NAV — that is SD-12.9's operation, consuming FO-06. FO-06 is the amount; SD-12.9 is the booking.
- The closed-end fund's carried-interest and waterfall calculation at fund level (the GP / LP carry distribution) — that is the SD-12.11 carry-and-waterfall service operation consuming PM-10. FO-06 covers the fund-level fee accrual that flows into a registered or closed-end fund's expense ratio; the detailed LP-level carry distribution is a PM-10-consuming operation, not a per-class accrual.
- The tax consequence of a fee accrual — that is SD-17.4 Investment & Portfolio Tax, which consumes the fee amounts but is not the accrual record.

## Owned and consumed by

- **Owned by:** SD-12.11 Expense, Fee & Carry Processing — the fee-and-expense processing function calculates and verifies the accrued fee amount for each class and period; FO-06 is the record it produces and signs off. SD-12.11 is the sole authoritative source.
- **Consumed by:** SD-12.9 Fund Accounting & NAV (books the `net_charge` into the struck NAV — the fee accrual reduces NAV per unit each period; SD-12.9 consumes FO-06 to accrue and book the fee); SD-09.1 Performance Measurement (the `net_charge` amount is the fee deduction used when computing net-of-fee return — gross return minus the accrued fee gives the investor's net return); SD-15.14 Client & Investor Reporting (the fee amounts and the OCF reconstruction chain feed class-level client report fee-disclosure sections); SD-16.2 Owner & Investor Reporting (the `net_charge` by `fee_type` and the reconstruction chain are the source for the UCITS KIID / PRIIPs KID ongoing-charges disclosure, fund factsheet fee tables, and the ILPA fee-and-expense line items in LP reports).

## FIBO alignment

**Partial — structural alignment at the fee-computation level; the OCF reconstruction chain and performance-fee mechanics are OpenIM.**

- The ongoing-charges figure (OCF) aligns to the **UCITS KIID** and **PRIIPs KID** lineage for investor-disclosure cost figures. The total expense ratio (TER) is an older, broader disclosure measure with a different scope; OCF is the successor figure under UCITS KIID / PRIIPs KID and they are not synonymous. These are regulatory constructs under the UCITS Directive / PRIIPs Regulation (EU) and the FCA's successor UK-PRIIPs rules; the KID/KII document is the rendering of the figures this entity stores. OpenIM references this lineage without asserting a FIBO class for OCF or TER: FIBO's published Funds ontology does not define an `OngoingChargesFigure` or `TotalExpenseRatio` class; the alignment is to the regulatory lineage, not to a named FIBO RDF class. The NAV-per-unit KIID/KID design note (SD-12.9) establishes the same pattern for the NAV-per-unit figure of record; FO-06 follows it symmetrically for the fee figure of record.

What FIBO does not model, and what FO-06 adds:

- The **computed fee amount with formula provenance** — which fee-schedule version produced this accrual figure, so the accrual is auditable even after the schedule version changes.
- The **expense-cap / fee-waiver / reimbursement chain** that nets the gross accrual to the disclosed charge — the three-step reduction that makes the OCF reconstructable from stored records.
- The **append-only accrual history** — the full trail of corrections and restatements for audit, governance and dispute resolution.
- The **performance-fee mechanics** (HWM applied, hurdle applied, crystallisation trigger) — the computation-bearing attributes that record what the fee-calculation engine applied, not just the resulting amount.

## Open extensions

- The sub-period daily accrual ledger — for funds that accrue daily and crystallise monthly, the per-day accrual sub-records linking to the period FO-06 row.
- The `formula_spec_ref` formalisation as a typed union FK (PM-10 `terms_id` | FO-02 schedule-version token) rather than a varchar provenance pointer, when the model's FK grammar is extended.
- The ILPA-granular fee-and-expense breakdown — the ILPA Reporting Template (v2.0, January 2025) carries a detailed fee, expense and carried-interest schedule; the `fee_type` enum could be extended with ILPA-specific line-item sub-types.
- The hedge-fund equalisation sub-model for performance fees — where investors subscribe mid-period and receive a performance-fee equalisation credit, the per-investor equalisation amount.
