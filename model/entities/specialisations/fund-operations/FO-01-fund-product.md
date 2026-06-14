# FO-01 — Fund Product

The fund as a product the manager *issues* — the collective investment vehicle the manager registers, prices and distributes. FO-01 is the golden record of an issued fund from the issuer's perspective, the manager-side complement to PM-01 Fund & Vehicle (which models the same fund from the *allocator's* commitment view). Where PM-01 records `committed_capital_usd` — the investor's commitment to a specific vehicle — FO-01 records the product-lifecycle, dealing-terms and regulatory-authorisation attributes that govern how the fund operates as an offered, priced and distributed product.

**Specialises:** E-02 Instrument / Asset. An issued fund is a holdable, identifier-bearing instrument — a collective investment vehicle with a legal form (OEIC, SICAV, unit trust, ETF, LP) whose interests are subscribed to and redeemed. FO-01 specifies the issued fund behind that instrument from the issuing manager's perspective. This is the same lineage as PM-01 (which also specialises E-02 as a `fund_interest` instrument), viewed from the opposite side of the issuance boundary: PM-01 is the allocator's view of the fund's commitment vehicle; FO-01 is the manager's view of the fund's issued product.

A portfolio or mandate container (E-03) was considered as the specialisation target — the operated fund is a capital container the manager keeps books for. The fund-as-container framing is accurate for the bookkeeping function (PM-13 Investor Capital Account already specialises E-03 for the per-investor capital account). But FO-01's defining characteristic is that it is *issued and identifiable* — it carries an ISIN, trades with a NAV, and is subscribed to by investors as a financial instrument. The instrument lineage (E-02) is more faithful to that characteristic and is consistent with PM-01's existing placement. E-03 remains the right parent for the fund-as-portfolio-container surface (PM-13's domain); E-02 is the right parent for the fund-as-issued-instrument surface (FO-01).

A generic firm-offering "Product" entity has been discussed in the model as a candidate anchored in the product-governance cluster. FO-01 is the fund-form issued product — it is not a specialisation of that generic product entity, which does not yet exist in the model. This record is explicit: the generic product entity is a separate, future modelling question. FO-01 stands on E-02 directly, without requiring the intermediate generic entity.

## Purpose

When the institution operates as a fund manager — registering, launching, pricing and distributing collective investment vehicles to investors — it must maintain each fund's **product record**: the governance and lifecycle state of the fund, the legal and regulatory structure it is authorised under, the dealing terms that govern when and how investors can transact, and the reference identifiers that place it in the world. FO-01 is that product record.

It is genuinely distinct from PM-01 Fund & Vehicle, and the distinction is the issuance boundary. PM-01 is the **allocator side** — the institution as an LP or outside investor committing capital to a fund someone else operates; the key allocator attribute is `committed_capital_usd`, the investor's own obligation to the fund. FO-01 is the **manager side** — the institution operating and issuing the fund for outside investors; the key product attributes are the authorisation status, the regulatory wrapper, the dealing terms and the units in issue (the issued side, not the committed side). An institution that both invests in funds (PM-01) and operates its own carries both; most large asset managers do.

## Attribute schema

### Identity and structure

| Column | Type | Definition |
|---|---|---|
| `fund_product_id` | varchar | **Golden key.** The OpenIM-assigned canonical identifier for the issued fund. |
| `fund_name` | varchar | Canonical product name as registered. |
| `legal_structure` | varchar | The legal form of the vehicle: `oeic` / `sicav` / `icvc` / `unit_trust` / `mutual_fund_40act` / `etf` / `lp` / `llc` / `fcp` / `other`. |
| `fund_form` | varchar | The dealing form: `open_ended` / `closed_ended` / `semi_liquid`. |
| `regulatory_wrapper` | varchar | The regulatory regime under which the fund is authorised: `ucits` / `aif` / `40act` / `cit` / `none` / `other`. |
| `domicile` | varchar | The fund's registered domicile (jurisdiction). |
| `base_currency` | char(3) | The fund's base / accounting currency (ISO 4217). |
| `launch_date` | date | The date the fund was registered and opened to investors. |
| `status` | varchar | Lifecycle state: `in_registration` / `open` / `soft_closed` / `closed` / `terminated`. |
| `umbrella_fund_id` | varchar (FK → FO-01) | For sub-funds of an umbrella / SICAV structure: the parent umbrella's `fund_product_id`. Null for standalone funds. |
| `manager_entity_id` | varchar (FK → E-01) | The legal entity (management company, AIFM, adviser or GP) that holds regulatory responsibility for the fund — the E-01 Legal Entity in the manager / ManCo role. |

### Dealing terms

The dealing terms govern when and how units price and deal. They are product-level parameters, set at launch and updated through the product-governance lifecycle. For multi-class funds, dealing terms may be set at the share-class level — that granularity belongs to FO-02 Share / Unit Class; FO-01 carries the fund-level defaults.

| Column | Type | Definition |
|---|---|---|
| `dealing_frequency` | varchar | How often the fund deals: `daily` / `weekly` / `fortnightly` / `monthly` / `quarterly` / `at_discretion`. |
| `dealing_cut_off` | varchar | The cut-off time and timezone for dealing orders (e.g. `12:00 London`). |
| `pricing_basis` | varchar | Whether dealing is priced on the next NAV after the order (`forward`) or the last struck NAV before the order (`historic`). UCITS funds are predominantly forward-priced. |
| `settlement_cycle` | varchar | Settlement terms for subscription and redemption cash (e.g. `T+3`, `T+5`). |
| `lock_up` | varchar | Any initial lock-up period before investors may redeem. Null for fully liquid funds. |
| `redemption_gate` | varchar | The gate provision: maximum percentage of NAV that can be redeemed in any dealing period before a gate is applied. Null where no gate applies. |
| `swing_pricing` | boolean | Whether the fund applies swing pricing or a dilution levy as its primary anti-dilution mechanism. |

### Identifiers

| Column | Type | Definition |
|---|---|---|
| `lei` | varchar | The Legal Entity Identifier of the fund legal vehicle, where one has been registered. |
| `external_ids` | map | Data-vendor and exchange identifiers for the fund (e.g. Bloomberg ticker for an ETF, Morningstar fund ID). |

Identifier canonicality: the canonical identifier record for this fund's legal entity is held in E-13 Entity Alias and E-14 External Identifier. The `lei` and `external_ids` fields above are a declared denormalised read-cache — derivable from E-13 / E-14 and regenerated from them, not an independent source. This is the same pattern PM-01 carries; the identifier-canonicality principle applies equally here.

### Asset class

| Column | Type | Definition |
|---|---|---|
| `asset_class` | int (FK → E-09) | The fund's *primary mandate* asset class, as an integer foreign key referencing E-09 Asset Class. A multi-asset fund carries the primary or dominant mandate class; funds with no single primary class carry null. |

The `asset_class` column is typed as `int (FK → E-09)` following the entity-model integer-FK discipline — not PM-01's legacy `varchar` field, which pre-dates that reconciliation. PM-01's `varchar` asset_class field carries the same latent inconsistency this column corrects; that is tracked separately as a same-class observation.

## Notes

- **The figure-of-record thesis.** The numbers a manager is accountable for — NAV per unit, the fee calculation, investor positions — are assembled across system seams. FO-01 is the stable product anchor those figures attach to: every downstream entity (share/unit class, investor unitholding, NAV-per-unit, fee accrual) references FO-01 by `fund_product_id`. The identity of the product must not change under computation.
- **Umbrella / sub-fund structures.** The `umbrella_fund_id` self-FK handles umbrella SICAVs and ICVC umbrella funds where sub-funds share a legal shell. Each sub-fund is a separate FO-01 row; the parent umbrella is also an FO-01 row (or a null `umbrella_fund_id` for standalone funds).
- **Units in issue is not here.** `units_in_issue` — the divisor in `NAV per unit = NAV ÷ units_in_issue` — is a share/unit-class grain figure carried at the class-grain E-07 Valuation record (produced by SD-12.9 at the NAV strike). FO-01 is the product; the class (FO-02) is the dealing and NAV grain; FO-02 and the class-grain E-07 are the built entities for this layer.

## Out of scope

- The investor's *unitholding* — the holding of fund units by an investor — is FO-03 Investor Unitholding (built; see the fund-operations pack); owned by SD-12.15 Transfer Agency & Investor Dealing.
- The share or unit class — the ISIN, fee schedule and NAV grain below the fund level — is FO-02 Share / Unit Class (built; see the fund-operations pack).
- The NAV-per-unit figure — the struck value at class grain — is the class-grain E-07 Valuation record, produced by SD-12.9 Fund Accounting & NAV at each NAV strike.
- The management-fee and performance-fee accrual as computation-bearing entities — FO-06 Fee Accrual is built (see the fund-operations pack); it is the computed fee figure of record per class and period, owned by SD-12.11 Expense, Fee & Carry Processing, consumed by SD-12.9 for NAV booking.
- The manager/ManCo entity as a structural object with delegation relationships — modelled at the E-01 Legal Entity level; the ManCo/AIFM role and the `delegates_to_entity_id` delegation edge are now first-class on FO-08 Service-Provider Appointment (built; see the fund-operations pack).

## Owned and consumed by

- **Owned by:** SD-13.3 Investment Vehicle & Fund Master — the same Service Domain that owns PM-01, and the closest precedent. SD-13.3 is the golden-record owner for funds and vehicles across both the allocator view (PM-01) and the manager / issuer view (FO-01).
- **Product-lifecycle contributions by:** SD-15.2 Product Development & Launch (launches the fund and contributes its initial reference record) and SD-15.3 Product Governance & Lifecycle Management (governs the fund through its life, updating the product register and lifecycle state).
- **Consumed by:** SD-12.9 Fund Accounting & NAV (strikes the NAV of the operated vehicle; `fund_product_id` is the product anchor for every NAV record); SD-12.15 Transfer Agency & Investor Dealing (maintains the investor register and processes dealing orders; references FO-01 for the dealing terms that govern order processing); SD-12.11 Expense, Fee & Carry Processing (calculates management fees and ongoing charges allocated to the fund); SD-15.11 Client & Investor Onboarding (the fund product the investor is onboarding into); SD-15.14 Client & Investor Reporting (the fund product the investor reporting references); SD-16.2 Owner & Investor Reporting (the fund product the accountability reports cover).

## FIBO alignment

**Partial — reuse plus operating-layer extension.** FIBO models collective investment vehicles well as structural and legal nouns:
- `fibo-sec-fund-fund:CollectiveInvestmentVehicle` — the FIBO apex for the fund as a legal entity and a financial instrument. FO-01 aligns here.
- `fibo-sec-fund-fund:FundManager` — the E-01 Legal Entity in the manager role (referenced by `manager_entity_id`).
- `fibo-be-le-lei:LegalEntityIdentifier` — the LEI field aligns to FIBO's LEI model.

What FIBO does not model, and what FO-01 adds:
- The **product lifecycle** — registration, launch, authorisation status, regulatory-wrapper enum, soft-close / terminated lifecycle states.
- The **dealing-terms governance layer** — dealing frequency, cut-off, pricing basis, settlement cycle, lock-up, redemption gate, swing-pricing flag. These are operational governance objects that FIBO's structural/legal ontology does not capture.
- The **issued-product manager-side view** — PM-01 is the allocator's commitment-vehicle view; FO-01 is the manager's issued-product view. FIBO models the fund as a structural noun; neither view of the fund-as-product-being-managed is present.

## Open extensions

- Umbrella-fund sub-fund hierarchies deeper than one level.
- The open-ended fund distribution event as an extension of the investor unitholding dealing model.
