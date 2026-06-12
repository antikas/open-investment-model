# PB-02 — Debt Instrument

A tradable debt security — a government, supranational, agency or corporate bond, a note or a money-market instrument — held directly or through a separately managed account.

**Specialises:** E-02 Instrument / Asset (`instrument_class = debt`). A position in a bond is a Holding (E-04) in an Instrument of class `debt`; PB-02 carries the issue, maturity, coupon and seniority detail behind it. It aligns to the FIBO Securities domain's debt-instrument concepts — OpenIM references FIBO for what a bond *is* and adds only the buy-side operating attributes.

## Purpose

A debt instrument differs from a listed equity in one structural way that the data model must reflect: **the issuer is the credit exposure.** An equity's risk is the company's; a bond's risk is the issuer's ability and willingness to pay, and that risk is shared across every bond the issuer has on issue. The relationship from PB-02 to the issuing Legal Entity (E-01) is therefore load-bearing — it is the join on which issuer-level credit-risk aggregation (SD-07.2) depends. The entity also carries the contractual cash-flow shape — coupon rate, frequency, maturity, amortisation — that distinguishes a bond from an equity, whose return is not contractual.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `instrument_id` | varchar (FK → E-02) | **Golden key.** The core Instrument / Asset record this debt instrument specialises. |
| `issuer_entity_id` | varchar (FK → E-01) | The issuing Legal Entity in the `issuer` role — **the credit.** Issuer-level exposure aggregates on this key. |
| `debt_type` | varchar | `government` / `supranational` / `agency` / `corporate` / `covered` / `securitised` / `money_market`. |
| `seniority` | varchar | `senior_secured` / `senior_unsecured` / `subordinated` / `tier_2` / `at1` — rank in the issuer's capital structure on default. |
| `isin` | varchar | International Securities Identification Number. |
| `cusip` | varchar | CUSIP, where North American. |
| `figi` | varchar | FIGI, where one exists. |
| `face_value` | decimal | Par / nominal value of one unit — the redemption amount per unit at maturity. |
| `currency` | char | Denomination currency. |
| `issue_date` | date | The dated date — when interest begins to accrue. |
| `maturity_date` | date | Scheduled final redemption date; null for a perpetual. |
| `coupon_rate` | float | The stated annual coupon rate; for a floater, the reference-rate spread is held alongside. |
| `coupon_type` | varchar | `fixed` / `floating` / `zero` / `step_up` / `inflation_linked`. |
| `coupon_frequency` | varchar | `annual` / `semi_annual` / `quarterly` / `monthly` — payments per year. |
| `day_count_convention` | varchar | The accrual basis — `30/360`, `ACT/ACT`, `ACT/360`, etc. |
| `reference_rate` | varchar | For a floater — the index the coupon resets against (e.g. SOFR, EURIBOR), null otherwise. |
| `callable` | boolean | Whether the issuer holds an embedded call option. |
| `credit_rating` | varchar (FK → E-11) | Issue-level rating (the in-record view of a Classification, E-12); the issuer-level rating sits on the E-01 issuer role. |
| `amortising` | boolean | Whether principal repays over the life rather than as a bullet at maturity. |
| `status` | varchar | `active` / `matured` / `called` / `defaulted`. |

## Notes

- One issuer (one E-01) is typically behind **many** PB-02 records — a corporate or sovereign with a curve of bonds across maturities and seniorities. Credit-risk aggregation (SD-07.2 Credit & Counterparty Risk) rolls every PB-02 up to the `issuer_entity_id`, and through the issuer's `parent_entity_id` to the group.
- The contractual coupon and redemption schedule is **forward-known** at issue. PB-08 Income Schedule materialises it as dated rows so accrual, income forecasting and fixed-income attribution can compute against it.
- A guarantor — a parent guaranteeing a subsidiary's debt — is a second E-01 relationship; the entity holds it as a note today, with an open extension to model it as a Party Relationship.
- Money-market instruments (T-bills, commercial paper, CDs) are PB-02 records with `coupon_type = zero` or short maturities; they are not a separate entity.

## Out of scope

- The generic instrument record a debt instrument specialises — that is E-02 Instrument / Asset of `instrument_class = debt`; PB-02 carries the issue, maturity, coupon and seniority detail.
- The issuing legal entity — the credit — that is E-01 Legal Entity in the `issuer` role; one issuer is typically behind many PB-02 records, and credit-risk aggregation rolls up to `issuer_entity_id`.
- A share in a company — that is PB-01 Listed Equity; PB-02 is the debt-class instrument only.
- The forward coupon and redemption calendar — that is PB-08 Income Schedule, which materialises PB-02's contractual terms as dated rows.

## Owned and consumed by

- **Owned by:** SD-13.1 Instrument & Security Master.
- **Populated via:** SD-13.4 Market & Reference Data Management.
- **Consumed by:** SD-07.2 Credit & Counterparty Risk Management (issuer-credit aggregation), SD-08.1 Security Pricing, SD-09.2 Performance Attribution (fixed-income attribution), SD-12.6 Corporate Actions Processing, SD-12.7 Income & Distribution Processing, SD-11.8 Securities Finance & Funding.

## Open extensions

- The guarantor relationship modelled as a Party Relationship (paired with the open extension on E-01).
- The full embedded-optionality sub-model — call / put / sink schedules — feeding option-adjusted analytics.
- The relationship between PB-02 and PB-08 Income Schedule for floating-rate reset projection.
- The concrete FIBO Securities (debt instrument) concept mapping.
