# FO-10 — ETF Creation/Redemption Order

The primary-market dealing event in which an authorised participant (AP) creates or redeems a block of ETF shares by exchanging an in-kind basket of underlying securities (FO-11 ETF Creation Basket) for fund shares, or the reverse. One order record per creation or redemption instruction submitted by an AP against a specific ETF share class.

**Specialises:** E-05 Transaction. An ETF creation/redemption order is an investment event: it changes the number of shares outstanding and results in an in-kind securities exchange and a residual cash settlement (E-06). FO-10 adds the primary-market AP-dealing structure — the creation-unit mechanics (block size, in-specie composition, settlement basis), the AP counterparty identity, and the read-cache struck-NAV and iNAV references — on top of the E-05 immutability principle.

FO-10 is distinct from:

- **FO-04 Dealing Order** — the transfer-agent dealing window for secondary-market cash subscriptions, redemptions, transfers and switches by registered fund investors at a forward NAV price. FO-10 is the *primary-market* dealing path: only authorised participants access it; the mechanism is in-specie (securities for shares), not cash; settlement is at the creation-unit block size; the AP is a capital-markets counterparty, not a registered investor. FO-04's own open extensions name this path explicitly as "in-specie subscription and redemption … used in ETF authorised-participant create/redeem."
- **PB-03 Order** — the exchange order book for secondary-market listed-equity trades, including the AP's secondary-market hedging trades executed on-exchange. PB-03 is the brokered-market order; FO-10 is the primary-market creation/redemption instruction submitted directly to the fund.
- **PM-07 Capital Call** / **PM-08 Distribution** — commitment-based cash events in a closed-end private-markets fund. Those are drawn against PM-06 LP Commitment; FO-10 is an in-specie primary-market event in an open-ended listed fund.

## Purpose

An ETF operates two dealing markets simultaneously. In the secondary market, ordinary investors buy and sell ETF shares on an exchange — those are exchange-order-book events (PB-03) settled against the prevailing market price. In the primary market, the AP creates or redeems *creation units* — standardised large blocks of shares (typically 50,000 shares per unit) — by exchanging the ETF's prescribed basket of underlying securities for newly issued shares, or tendering shares in exchange for the basket. This in-kind exchange is the arbitrage mechanism that keeps the ETF's secondary-market price close to its net asset value.

FO-10 is the authoritative record of each primary-market creation or redemption event. It records the AP's identity, the agreement under which the AP is authorised (FO-12 AP Agreement), the number of creation units, the composition basket referenced (FO-11), the settlement basis (in-kind, cash-in-lieu, or custom), the iNAV and struck NAV at which the order was priced, and the final settled status.

Without FO-10, the audit trail "on what basis were ETF shares created or redeemed, at what price, with which AP, and against which basket?" is unanswerable. FO-10 is the immutable primary-market event record; FO-03 Investor Unitholding carries the intermediary-level register position the AP holds in omnibus; FO-09 Omnibus Account records the AP's account at the register.

## Attribute schema

### Identity and relationship

| Column | Type | Definition |
|---|---|---|
| `creation_redemption_order_id` | varchar | **Golden key.** The OpenIM-assigned canonical identifier for this creation/redemption order. |
| `share_class_id` | varchar (FK → FO-02) | The ETF share or unit class the order is against — the class being created into or redeemed from. The ETF applicability is declared on the class and the fund product, not on the entity. |
| `ap_entity_id` | varchar (FK → E-01) | The authorised participant — the broker-dealer or market-maker executing the creation or redemption. |
| `ap_agreement_id` | varchar (FK → FO-12) | The standing AP Agreement under which this order is authorised. Every FO-10 must trace to a current FO-12. |
| `basket_id` | varchar (FK → FO-11) | The ETF Creation Basket — the daily composition file specifying the securities and cash the AP must deliver (creation) or will receive (redemption). |

### Order classification

| Column | Type | Definition |
|---|---|---|
| `order_type` | varchar | `creation` (AP delivers the basket and receives ETF shares) / `redemption` (AP delivers ETF shares and receives the basket). |
| `num_creation_units` | integer | The number of creation units the AP is creating or redeeming. One creation unit = `creation_unit_size` shares. |
| `creation_unit_size` | integer | The number of ETF shares in one creation unit for this share class and dealing date, as published by the fund (from FO-02 / FO-01). |
| `settlement_basis` | varchar | `in_kind` (the full basket of securities is exchanged), `cash_in_lieu` (one or more basket securities are substituted with a cash equivalent, at the fund's discretion), `custom` (a bespoke settlement arrangement agreed between the AP and the fund for a specific order). |

### Dealing mechanics

| Column | Type | Definition |
|---|---|---|
| `order_date` | date | The date the creation/redemption order was submitted by the AP. |
| `valuation_date` | date | The date the NAV per unit used to price any cash component or residual is struck. For in-kind creations, this is the date the basket composition and the struck NAV are agreed. |
| `struck_nav_per_unit` | decimal | **Read-cache reference to the class-grain E-07 Valuation record** (`unit_class_id = share_class_id`, `method = manager_mark`) owned by SD-12.9 for the valuation date. The struck NAV per ETF share used to price any cash-in-lieu component and residual cash settlement. This is a read-cache field: the authoritative figure of record is the class-grain E-07 owned by SD-12.9; `struck_nav_per_unit` carries it on the order for audit completeness and is derivable from E-07 at the same `(unit_class_id, valuation_date)`. |
| `inav_ref` | decimal | The indicative NAV (iNAV) at or around the time the order was submitted — the intraday estimate of fair value published continuously during the trading day. The iNAV is a reference figure used by the AP to gauge the arbitrage opportunity; it is not a figure of record. The authoritative valuation is `struck_nav_per_unit` (the official end-of-day class-grain E-07 record). |
| `total_shares` | integer | The total ETF shares created or redeemed: `num_creation_units × creation_unit_size`. |

### Settlement

| Column | Type | Definition |
|---|---|---|
| `settlement_date` | date | The date the in-kind securities exchange and any residual cash settle (typically T+2 for ETF primary-market transactions in most markets). |
| `cash_residual` | decimal | The net residual cash amount payable by the AP to the fund (creation) or by the fund to the AP (redemption), arising from the difference between the basket value and the exact creation-unit NAV, plus any cash-in-lieu substitutions. Signed by direction: positive = AP pays the fund; negative = fund pays the AP. |
| `status` | varchar | Full lifecycle: `draft` → `submitted` → `accepted` \| `rejected` → `validated` → `settling` → `settled` \| `failed`. See status lifecycle note below. |
| `basket_leg_settlement_status` | varchar | Settlement status of the in-kind basket leg: `pending` \| `settling` \| `settled` \| `failed` \| `partial`. The basket leg (AP delivers securities on creation; AP receives securities on redemption) may settle independently of the creation-units leg. |
| `basket_leg_settlement_date` | date (nullable) | Actual settlement date of the basket leg. Null until settled or failed. |
| `units_leg_settlement_status` | varchar | Settlement status of the creation-units leg: `pending` \| `settling` \| `settled` \| `failed`. The creation-units leg (ETF shares issued on creation; ETF shares cancelled on redemption) may settle on a different cycle from the basket leg. |
| `units_leg_settlement_date` | date (nullable) | Actual settlement date of the creation-units leg. Null until settled or failed. |
| `partial_settlement_flag` | boolean | True when one or more basket names have not fully settled and a partial settlement has been accepted; the remaining names are either pending, subject to cash-in-lieu substitution, or carrying a fail position. |
| `cash_in_lieu_names` | varchar[] | The instrument identifiers (FK → E-02) for basket names substituted with a cash-in-lieu amount for this order — where a basket constituent could not be delivered and the fund accepted a cash equivalent at the fund's discretion or per the AP agreement terms. |

## Notes

- **FO-10 is an immutable event.** A creation/redemption order that settled is a fact; corrections are new records (a reversal paired with a correcting order), not edits. The E-05 immutability principle applies at the primary-market grain.
- **Struck NAV is a read-cache, not a duplicate figure of record.** The `struck_nav_per_unit` field carries the NAV at which the order priced, for audit and completeness on the dealing record. The authoritative, provenance-bearing figure of record is the class-grain E-07 Valuation owned by SD-12.9. `struck_nav_per_unit` is a declared read-cache on the order, derivable from E-07 at the same `(unit_class_id, valuation_date)` — the same pattern as FO-04 Dealing Order.
- **Creation-unit block size.** The AP must submit in whole multiples of the creation unit. Partial creation units are not accepted. The creation unit size is a fund-level parameter set by the ETF issuer (visible on FO-01 / FO-02) and published daily as part of the basket composition file.
- **In-kind vs cash-in-lieu.** The default is in-kind: the AP delivers or receives the exact basket constituents. Cash-in-lieu is used where a basket security cannot be delivered (e.g., restricted securities, foreign-market settlement timing). A custom settlement is agreed case-by-case. The `settlement_basis` field records which applies.
- **The AP's secondary-market hedge trades** — the exchange-traded orders the AP executes to offset the primary-market position it created or redeemed — are PB-03 Order records on the exchange order book, not additional FO-10 records. The primary-market dealing (FO-10) and the secondary-market hedging (PB-03) are distinct and separate.
- **Order status lifecycle.** The lifecycle progresses `draft → submitted → accepted | rejected → validated → settling → settled | failed`. The `accepted` / `rejected` gate is the ETF sponsor's order-window discretion under the AP agreement (FO-12) — the sponsor reviews the order for eligibility, settlement-basis permission, and AP authorisation before accepting. This gate is distinct from settlement `failed` (which arises after acceptance, during the basket-delivery or creation-units-issuance leg). **Bindingness attaches at acceptance, not at affirmation or settlement.** A `rejected` order is final; a `failed` order post-settlement is handled by a fail-management process. (Sourced: SIFMA ETF AP agreement framework; SEC Rule 6c-11, 17 CFR 270.6c-11, 2019.)
- **Dual-leg settlement and partial settlement.** The creation/redemption is a parallel exchange of two legs: (1) the basket leg — the AP delivers or receives the underlying securities; (2) the creation-units leg — ETF shares are issued or cancelled. The legs can settle on different cycles (ETF shares often T+1; individual basket names settle on each name's native market cycle). Per-leg status (`basket_leg_settlement_status`, `units_leg_settlement_status`) and settlement dates track each leg independently. Where one or more basket names fail to deliver, the order may partially settle — the `partial_settlement_flag` and `cash_in_lieu_names` capture the substitution path. Cash-in-lieu substitution replaces a failing basket name with a cash equivalent at the fund's discretion or per AP agreement terms (not a full `settlement_basis = cash_in_lieu` order). (Sourced: SEC Rule 6c-11 custom-basket and in-kind delivery mechanics; WFE/SIFMA ETF AP agreement framework.)

## Out of scope

- The secondary-market trading of ETF shares by ordinary investors — those are exchange-order-book events at the PB-03 grain, settled at the prevailing market price.
- The cash subscription and redemption of registered fund investors at the transfer-agent dealing window — that is FO-04 Dealing Order at the forward NAV price.
- The AP's exchange-order-book hedging trades used to manage the basket position — those are PB-03 Orders.
- The AML / KYC and on-boarding of the AP as a counterparty — that is SD-13.2 Entity & Counterparty Master and SD-14.3 Financial Crime Prevention; FO-10 reads the AP identity from E-01.

## Owned and consumed by

- **Owned by:** SD-12.15 Transfer Agency & Investor Dealing — the transfer-agency function accepts, validates, and settles ETF creation/redemption orders; SD-12.15 is the system of record for the primary-market dealing window and the order lifecycle, operating as the in-specie sibling of the forward-NAV cash-dealing window it runs for FO-04.
- **Consumed by:** SD-12.15 Transfer Agency & Investor Dealing (validates and settles each ETF creation/redemption order; SD-12.15 is the primary dealing-window operator for the order lifecycle); SD-12.1 Investment Book of Record (IBOR) (the securities-inventory effects of basket deliveries and receipts enter the book of record); SD-12.2 Accounting Book of Record (ABOR) (the accounting-basis position and cash effects of the in-kind exchange); SD-12.9 Fund Accounting & NAV (the creation/redemption changes shares outstanding, which updates the NAV-per-unit divisor; `struck_nav_per_unit` cross-references the E-07 record SD-12.9 owns); SD-12.10 Reconciliation (the in-specie basket delivery reconciliation between the custodian's securities receipt/delivery records and the AP's settlement confirmation); SD-14.3 Financial Crime Prevention (AP primary-market activity monitoring). Custody settlement confirmation is covered via SD-12.5's consumption of FO-11 (the basket PCF against which deliveries are verified) and SD-12.10's reconciliation of FO-10 settled orders against custodian records.

## FIBO alignment

**No published FIBO class for ETF primary-market creation/redemption orders.** FIBO's collective-investment-vehicle framework models fund shares and NAV concepts at the conceptual level; it does not define classes for ETF creation/redemption orders, creation units, or in-specie basket exchange mechanics. The closest semantic anchors are:

- FIBO's collective-investment-vehicle framework aligns to the conceptual level: FO-10 is a transaction in ETF shares (which are instruments in the FIBO CIV namespace) exchanged in a primary-market dealing event.
- The in-kind exchange mechanism, the creation-unit block size, the basket composition, and the AP counterparty role are OpenIM additions with no FIBO equivalent in the published ontology.

The operative standards for the ETF primary-market are the exchange rulebooks, AP agreement terms (as standardised by the WFE / SIFMA frameworks in the US), and the fund's prospectus. No wire-format standard (ISO 20022, FIX) covers the ETF creation/redemption instruction at the same grain as the `setr` family covers FO-04.

## Open extensions

- The creation-unit-size versioning record — where the fund changes the creation unit size (a relatively infrequent event), the versioned history of size changes and their effective dates.
- A cash-in-lieu substitution detail table — listing which specific basket securities were substituted with cash, the substitution values, and the basis for the substitution decision.
- The settlement-instruction cross-reference — linking FO-10 to the custody-level settlement instruction (PB-06 Settlement Instruction) for the basket delivery/receipt, enabling end-to-end settlement tracking.
