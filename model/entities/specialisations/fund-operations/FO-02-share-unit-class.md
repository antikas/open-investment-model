# FO-02 — Share / Unit Class

The class grain at which a fund's economics attach — one FO-01 fund issues many classes. Each class carries its own ISIN, fee schedule, distribution policy, currency and investor category. FO-02 is the authoritative reference record of a share or unit class as the issuing manager maintains it: the class the investor subscribes to, the class the NAV per unit is struck for, the class whose fee is accrued and disclosed, and the class whose currency-hedging programme — for a hedged class — is configured.

**Specialises:** E-02 Instrument / Asset. A share or unit class is a holdable, ISIN-bearing instrument in its own right. Investors subscribe to and redeem from a class (not the fund directly); the class carries its own ISIN, its own NAV per unit, and its own regulatory disclosure obligations. This is the same E-02 lineage as FO-01 Fund Product (the fund-as-issued-product) and PM-01 Fund & Vehicle (the fund-as-held-investment) — a collective-investment interest is an instrument however it is viewed. FO-02 refines the lineage one step further: it is the specific dealing and pricing *class* within a fund, the grain at which the investor actually transacts and is reported to.

E-03 Portfolio / Mandate was considered as the specialisation target — each class has its own capital pool and dealing identity. However the decisive characteristic of a share or unit class is that it is *identifiable and tradeable* — it carries an ISIN, prices at a NAV per unit, and is subscribed to and redeemed by investors as a financial instrument. The instrument lineage (E-02) captures that characteristic faithfully; the portfolio-container framing (E-03) does not. E-03 remains the right parent for the fund-as-capital-container surface (PM-13's domain); E-02 is the right parent for the fund-as-holdable-instrument surface (FO-01 and FO-02).

## Purpose

A fund commonly issues many classes, each differing in fee schedule, distribution policy, currency or investor category. The **fund grain** (FO-01) is insufficient for NAV per unit, because the divisor — units in issue — is a per-class figure. It is insufficient for the fee, because management and ongoing-charges rates differ by class. It is insufficient for the investor holding, because investors hold *a class* not the fund. FO-02 is the grain that resolves this: the governed reference record of each class within an issued fund, from which NAV per unit, the fee and the investor's holding are downstream.

The class is also the grain at which **currency-hedged classes** are configured. When a fund offers a currency-hedged class, the `hedged` flag and the static class attributes identify it as such; the FX execution and hedging function (SD-11.3) reads this configuration to operate the hedge programme. FO-02 holds the static class configuration that governs the hedge; the per-period hedge P&L produced by the programme is an operating-state input that feeds the SD-12.9 class-NAV strike each NAV cycle.

## Attribute schema

### Identity and relationship

| Column | Type | Definition |
|---|---|---|
| `share_class_id` | varchar | **Golden key.** The OpenIM-assigned canonical identifier for this share or unit class. |
| `fund_product_id` | varchar (FK → FO-01) | The issued fund this class belongs to. One fund issues many classes; this is the parent-product link. |
| `class_name` | varchar | The canonical class name as registered and disclosed (e.g. "Accumulation GBP-Hedged Institutional"). |
| `class_code` | varchar | The short code used in dealing and reporting (e.g. "Acc GBP-H Inst", "Class I GBP"). |

### Class characteristics

| Column | Type | Definition |
|---|---|---|
| `distribution_policy` | varchar | How the class handles income: `accumulation` (income reinvested into NAV) / `income` (income paid out to unitholders). An umbrella fund typically issues both forms as separate classes. |
| `class_currency` | char(3) | The dealing and pricing currency of this class (ISO 4217). May differ from the fund's `base_currency` (FO-01) — a USD base fund may offer GBP, EUR or JPY classes. |
| `hedged` | boolean | Whether this class runs a currency-hedging programme to limit FX exposure between the class currency and the fund base currency. A `true` value identifies the class as hedged for the downstream capabilities (SD-11.3 hedge execution; SD-12.9 NAV strike) that consume this flag. |
| `investor_category` | varchar | The investor eligibility category the class is restricted to: `institutional` / `retail` / `founder` / `seed` / `clean` / `super_clean` / `all`. Governs minimum investment and distribution-channel eligibility. |

### Fee schedule

| Column | Type | Definition |
|---|---|---|
| `class_fee_schedule` | document (JSON) | The per-class fee schedule, carrying the management fee rate, the ongoing-charges figure (OCF) / total-expense-ratio components, and any performance-fee terms applicable to this class. Follows the computation-as-data pattern: a `definition_type` of `FIXED` (a scalar rate) or `COMPUTED` (a structured `formula_spec` the calculation engine interprets). The accrual of these terms into NAV is the mandate of the fee and expense processing function; FO-02 carries the terms, not the accrued amounts. |

### Dealing minimums

| Column | Type | Definition |
|---|---|---|
| `min_investment` | decimal | The minimum initial subscription amount for this class, in `class_currency`. |
| `min_subsequent_investment` | decimal | The minimum subsequent subscription amount, in `class_currency`. Null where no minimum applies beyond the initial. |

### Identifiers

| Column | Type | Definition |
|---|---|---|
| `isin` | varchar | The ISIN of this share or unit class. Per-class ISINs are the standard practice for multi-class UCITS and registered funds: each class is a separately-identifiable instrument for dealing and reporting purposes. |

Identifier canonicality: the canonical identifier record for this class — its ISIN, SEDOL, Bloomberg code, and any data-vendor identifiers — is held in E-13 Entity Alias and E-14 External Identifier. The `isin` field above is a declared denormalised read-cache, derivable from E-14 and regenerated from it, not an independent source. This is the same pattern FO-01 and PM-01 carry; the identifier-canonicality principle applies equally here.

### Asset class

| Column | Type | Definition |
|---|---|---|
| `asset_class` | int (FK → E-09) | The asset class of this share or unit class, as an integer foreign key referencing E-09 Asset Class. In most cases a class inherits the primary mandate asset class of its parent FO-01 fund product — `asset_class` is nullable to allow derivation from `FO-01.asset_class` where the class does not differ. A multi-asset or fund-of-funds class carries the primary or dominant mandate class, or null where no single class applies. Typed as `int (FK → E-09)` following the entity-model integer-FK discipline — not a varchar. |

## Notes

- **NAV per unit attaches here, not at the fund.** The fund's NAV (FO-01) is the total assets minus liabilities; the class NAV is the fund NAV allocated to this class; the NAV per unit is the class NAV divided by units in issue for this class. Accumulation and income classes of the same fund will diverge as income is reinvested into the former and distributed from the latter. Hedged classes will further diverge from unhedged siblings by the hedge P&L applied at NAV strike. The class is the irreducible grain.
- **Fee schedule as computation-as-data.** The `class_fee_schedule` carries the terms, not the accrued amounts. The accrual — the term applied to a period to produce the accrued management fee or OCF — is the mandate of a downstream capability. FO-02 is the terms record; the computation over those terms is downstream.
- **Umbrella / sub-fund structures.** In an umbrella SICAV or ICVC, each sub-fund is a separate FO-01 row; within that sub-fund, each class is a separate FO-02 row. The parent-child chain is `umbrella FO-01 → sub-fund FO-01 → share class FO-02`.
- **Dormant for a pure allocator.** This entity activates only when the institution operates as a fund issuer or manager, registering and distributing its own funds. A pure LP allocator that commits to externally-managed funds leaves the fund-operations pack dormant; the allocator's commitment and interest are carried by PM-01 / PM-06. Most large asset managers operate as both allocator and issuer and carry both facets.

## Out of scope

- The investor's *unitholding* — the holding of units in this class by a specific investor — is FO-03 Investor Unitholding (built; see the fund-operations pack); owned by SD-12.15 Transfer Agency & Investor Dealing.
- The investor-reported NAV per unit is the class-grain E-07 Valuation record (see E-07 Valuation); FO-02 carries only the static class reference data. The NAV per unit is built as a typed E-07 at the share/unit-class grain — the grain exists; this item is closed.
- The management-fee and ongoing-charges accrual as computation-bearing entities — built as FO-06 Fee Accrual, owned by SD-12.11 Expense, Fee & Carry Processing; FO-02 carries the fee schedule (the terms); FO-06 carries the computed accrual amounts.
- The ETF authorised-participant create/redeem mechanism — a distinct dealing path applicable only to ETF classes; a later extension.
- DC / retirement-plan recordkeeping at participant grain — deliberately excluded from this pack, as scoped by the fund-operations pack design.

## Owned and consumed by

- **Owned by:** SD-13.3 Investment Vehicle & Fund Master — the golden-record owner for funds, vehicles and the classes within them. SD-13.3 maintains the class reference record as part of the manager / issuer facet of the fund master, including the static dealing-terms and class configuration that govern each class.
- **Consumed by:** SD-12.9 Fund Accounting & NAV (strikes the class NAV, using `share_class_id` to anchor each class-level NAV record and `hedged` to identify which classes require the hedge P&L applied at strike); SD-12.15 Transfer Agency & Investor Dealing (reads the class dealing terms — `class_currency`, `distribution_policy`, `min_investment`, `investor_category` — to govern order eligibility and processing); SD-12.11 Expense, Fee & Carry Processing (computes and verifies the management fee and OCF/TER for this class from `class_fee_schedule`; the accrual flows to SD-12.9); SD-11.3 FX Execution & Share-Class Hedging (reads `hedged` and `class_currency` to identify which classes require the hedge programme; operates the programme and produces the per-period P&L that SD-12.9 applies at NAV strike); SD-15.11 Client & Investor Onboarding (reads `investor_category`, `min_investment` and `class_fee_schedule` to govern class eligibility and onboarding terms); SD-15.14 Client & Investor Reporting (reads class ISIN, distribution policy, `class_currency` and `class_fee_schedule` to populate class-level report headers and fee disclosures); SD-16.2 Owner & Investor Reporting (reads class ISIN, distribution policy and `class_fee_schedule` for UCITS KIID / PRIIPs KID, fund factsheets and shareholder reports).

## FIBO alignment

**Partial — reuse at the structural / identifier level; operating and economic layer is OpenIM.**

- FIBO's collective-investment-vehicle framework — a share or unit class aligns to FIBO's treatment of the legal structure in which an investor can purchase part of an investment pool, defined by investor type, minimum size of investment, distribution type, fee and currency. FIBO's Funds ontology does not define a FundShareClassUnit class in its published RDF; the alignment is to FIBO's collective-investment-vehicle and fund-unit concepts at the structural level.
- `fibo-fbc-fi-fi:FinancialInstrumentIdentifier` — the per-class ISIN aligns to FIBO's instrument-identifier model, consistent with E-14 External Identifier and the identifier-canonicality principle.

What FIBO does not model, and what FO-02 adds:

- The **per-class fee schedule** as computation-as-data — the management rate, OCF and performance-fee terms at class grain, following the computation-as-data pattern.
- The **static hedged-class configuration** — the `hedged` flag and `class_currency` that parameterise the currency-hedge programme operated by SD-11.3.
- The **dealing lifecycle governance** — minimum investment thresholds, investor eligibility categories and the dealing-terms that govern the transfer-agency workflow.
- The **class-grain NAV attribution** — the economic fact that accumulation, income and hedged classes of the same fund require the class as the irreducible record grain.

## Open extensions

- **Units in issue** (the NAV-per-unit divisor) — carried at the class-grain E-07 Valuation record (the NAV-per-unit strike grain), produced by SD-12.9 Fund Accounting & NAV at each dealing cycle as subscriptions create and redemptions cancel units. This is a dealing-cycle figure, not static class reference data; it is not on FO-02 by design.
- **Hedge programme operating state** — the target hedge ratio, currency pair and per-period P&L contribution are produced each NAV cycle by SD-11.3 FX Execution & Share-Class Hedging. These are dynamic, period-level figures produced by the FX operating domain; they are not static class configuration. The per-period P&L feeds the SD-12.9 class-NAV strike for currency-hedged classes; an SD-11.3-owned hedge-programme operating record for the full operating state is a later extension if warranted. FO-02 carries only the static `hedged` flag that identifies a class as hedged.
- The investor unitholding — FO-03 Investor Unitholding is built (see the fund-operations pack); it is the per-investor, per-class register position, owned by SD-12.15 Transfer Agency & Investor Dealing.
- The management-fee and OCF accrual as computation-bearing entities applying `class_fee_schedule` to a period — FO-06 Fee Accrual is built (see the fund-operations pack); it is the computed fee figure of record that reads `class_fee_schedule` as provenance, owned by SD-12.11, consumed by SD-12.9 for NAV booking.
- The ETF create/redeem mechanism — the authorised-participant dealing path, applicable only to ETF classes.
- The `class_fee_schedule` document grammar — the typed vocabulary a `COMPUTED` fee term is expressed in, following the PM-10 Fund Terms `formula_spec` pattern.
