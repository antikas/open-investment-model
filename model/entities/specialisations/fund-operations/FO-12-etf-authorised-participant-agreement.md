# FO-12 — ETF Authorised-Participant Agreement

The standing, dated record of a broker-dealer's or market-maker's right to create and redeem ETF creation units against a specific fund product — the AP Agreement relationship between the fund (FO-01) and an authorised participant (E-01). One record per (fund, AP) with its own lifecycle: the AP is authorised from `authorised_date`, may restrict or terminate its access (`terminated_date` nullable), and may operate under defined settlement-basis permissions.

**Specialises:** a first-class relationship entity in the fund-operations pack extending the core entity model. FO-12 is not a holdable instrument or a transaction event; it is the first-class dated agreement record — the standing access right that makes each FO-10 creation/redemption order valid. An AP may be authorised for one ETF but not another (a relationship at the (fund, AP) grain), and each authorisation has its own lifecycle independent of any individual order.

**Design rationale — entity rather than attribute on FO-10 or an extension of FO-08.** Two comparisons are relevant:

- **Not an attribute on FO-10.** Every FO-10 creation/redemption order references an AP agreement (`ap_agreement_id` FK → FO-12). Promoting the agreement to a first-class entity separates the standing access right (FO-12, one per authorised relationship) from the individual dealing event (FO-10, one per order). An attribute on FO-10 would duplicate the agreement terms on every order and would not model the agreement's independent lifecycle (an agreement can exist — and be terminated — independently of any orders submitted under it). The FO-09 Omnibus Account precedent (the account-relationship entity separated from FO-03 position records) and the FO-08 Service-Provider Appointment precedent (the appointment-relationship entity separated from FO-01 fund records) both confirm this shape.
- **Not an extension of FO-08 Service-Provider Appointment.** An AP is a capital-markets counterparty — a broker-dealer or market-maker that exercises independent trading discretion on a stock exchange. It is not a service provider overseen by the vendor-management function (SD-17.8 Vendor, Outsourcing & Service-Provider Oversight). The AP is not appointed to service the fund; it is *authorised* to trade in its primary market. The relationship is governed by the fund's transfer-agency function (SD-12.15) as the dealing-window operator, not by SD-17.8. Placing AP agreements in FO-08's role enum would mischaracterise the AP as a vendor — conflating a commercial counterparty relationship with an operational service-provider relationship.

## Purpose

The ETF primary market is a gated market: only authorised participants may submit creation/redemption orders. A broker-dealer becomes an AP by entering into a formal agreement with the fund (or its transfer agent) that sets out the dealing mechanics, settlement obligations, and operational procedures. One agreement per (fund, AP) governs all orders the AP submits for that fund; a single AP may hold separate agreements with different funds issued by the same or different managers.

FO-12 is the record of that agreement: the formal standing right of an AP to trade in a given fund's primary market, with its effective dates and the permitted settlement basis (in-kind, cash-in-lieu, or both). SD-12.15 reads FO-12 when validating incoming creation/redemption orders to confirm the submitting AP is currently authorised for the fund and share class, and is using a permitted settlement basis.

FO-12 is distinct from:

- **FO-08 Service-Provider Appointment** — the appointment of a service provider (custodian, administrator, transfer agent, auditor) to serve the fund; FO-08 is owned by SD-17.8 (vendor management). FO-12 is the authorisation of a capital-markets counterparty to access the primary market; owned by SD-12.15 (transfer agency and dealing).
- **FO-10 ETF Creation/Redemption Order** — the individual primary-market dealing event submitted under the standing agreement. FO-12 is the standing access right; FO-10 is each exercise of it.
- **DR-03 Master Agreement** — the ISDA Master Agreement or similar legal framework governing OTC derivatives between the fund and a counterparty. An AP agreement is specific to ETF primary-market dealing; its mechanics are distinct from the OTC derivatives framework.

## Attribute schema

### Identity and relationship

| Column | Type | Definition |
|---|---|---|
| `ap_agreement_id` | varchar | **Golden key.** The OpenIM-assigned canonical identifier for this AP agreement record. |
| `fund_product_id` | varchar (FK → FO-01) | The ETF fund this agreement grants primary-market access to. |
| `ap_entity_id` | varchar (FK → E-01) | The authorised participant — the broker-dealer or market-maker — that holds the primary-market access right under this agreement. |

### Lifecycle

| Column | Type | Definition |
|---|---|---|
| `authorised_date` | date | The date on which the AP was formally authorised to access the primary market of this fund — the effective start date of the agreement. |
| `terminated_date` | date (nullable) | The date on which the authorisation was terminated. Null for currently active agreements. Termination may be initiated by either party; the AP may resign; the fund may revoke the AP's access. |
| `status` | varchar | `active` / `suspended` / `terminated`. `suspended` covers a temporary restriction imposed by the fund or regulator during a dealing-suspension event; the agreement is not terminated but orders cannot be submitted while suspended. |

### Access rights

| Column | Type | Definition |
|---|---|---|
| `permitted_settlement_basis` | varchar | The settlement basis the AP is permitted to use under this agreement. Values: `in_kind` (in-kind basket exchange only), `cash_in_lieu` (cash substitution for basket securities permitted, subject to per-order fund approval), `both` (both in-kind and cash-in-lieu permitted). |

### Standing terms

| Column | Type | Definition |
|---|---|---|
| `credit_standing` | varchar | The AP's credit standing as assessed at agreement establishment and reviewed periodically: `good_standing` \| `watch` \| `restricted`. Orders are validated against this at acceptance (FO-10 status `submitted → accepted`); a `restricted` AP cannot submit orders. |
| `trading_limit_creation_units` | integer (nullable) | The maximum number of creation units the AP may submit per dealing day under the standing agreement. Null means no explicit cap; orders beyond the limit are rejected at acceptance. |
| `creation_fee_basis_points` | decimal (nullable) | The creation fee charged to the AP per creation unit, expressed in basis points of the creation-unit NAV. Carries the standing rate; the computed fee amount on a specific order is referenced, not duplicated (the FO-06 fee-figure precedent — fee computations belong to the operational processing function). |
| `redemption_fee_basis_points` | decimal (nullable) | The redemption fee charged to the AP per creation unit redeemed, in basis points of the creation-unit NAV. Same reference-not-duplicate principle. |
| `fail_fee_basis_points` | decimal (nullable) | The fail fee owed by the AP when a basket name fails to deliver on the agreed settlement date and the AP agreement does not permit cash-in-lieu substitution for that name. Expressed in basis points of the failed name's value per dealing day of the fail. The standing rate is on FO-12; the computed fail-fee amount for a specific settlement failure is an operational record. |

## Notes

- **One FO-12 per (fund, AP).** A single AP may be authorised for many different ETFs (each with a separate FO-12 record). The same fund may have many authorised APs (each with a separate FO-12 record for that fund). The (fund_product_id, ap_entity_id) composite is the natural business key.
- **Historical agreements are retained.** When an AP terminates its agreement, the row's `terminated_date` is populated and `status` is set to `terminated`; a new agreement with the same AP — if re-authorised — is a new FO-12 record. The full history of which APs were authorised for a fund and over which dates is preserved in the append pattern — rows are never deleted or overwritten.
- **FO-12 is the `ap_agreement_id` FK target on FO-10.** Every creation/redemption order must carry a reference to a currently-active FO-12 record. SD-12.15 validates this on order acceptance; an order submitted by an AP with no active FO-12 for the fund is rejected.
- **The AP's counterparty identity** is its E-01 Legal Entity record, maintained by SD-13.2 Entity & Counterparty Master. FO-12 reads the E-01 party record; it does not duplicate party data.
- **Good-standing check at order acceptance.** When SD-12.15 processes an incoming FO-10 order (transition from `submitted` to `accepted` or `rejected`), it reads FO-12 to confirm (1) the AP has an active agreement (`status = active`), (2) the `credit_standing` is `good_standing`, (3) the `permitted_settlement_basis` covers the order's `settlement_basis`, and (4) the order's `num_creation_units` does not breach the `trading_limit_creation_units` cap. Failure on any check produces a `rejected` status on FO-10. This gate is the AP-agreement-side complement to the basket validation (SD-12.15 reads FO-11 in parallel to confirm the AP's submitted composition).
- **Fee terms on FO-12, computed amounts referenced.** The standing `creation_fee_basis_points`, `redemption_fee_basis_points`, and `fail_fee_basis_points` represent the contractual rate schedule. Computed fee amounts for individual orders and settlement fails are operational records produced by SD-12.15 and referenced in the same pattern as FO-06 Fee Accrual (the computed figure is a separate record with the formula provenance; the rate lives on the agreement).

## Out of scope

- The operational procedures agreement (creation/redemption procedures manual) that supplements the AP agreement — that is an E-15 Document Metadata record.
- The AP's AML / KYC on-boarding as a financial counterparty — that is SD-13.2 Entity & Counterparty Master and SD-14.3 Financial Crime Prevention. FO-12 presupposes an on-boarded AP; it is the primary-market-access grant, not the on-boarding record.
- The AP's secondary-market dealing in ETF shares on the exchange — those are PB-03 Orders. FO-12 governs primary-market creation/redemption only.
- The computed fee amounts on individual orders — creation fees, redemption fees, and fail fees for specific deals are computed at transaction time by SD-12.15 Transfer Agency & Investor Dealing and referenced from the operational records, not duplicated here. FO-12 holds the standing rates (the basis-points terms); the per-order computed amounts follow the FO-06 precedent (FO-06 Fee Accrual carries computed figures; the terms live on the agreement).

## Owned and consumed by

- **Owned by:** SD-12.15 Transfer Agency & Investor Dealing — the transfer-agency function establishes, maintains, and terminates AP agreements; SD-12.15 is the system of record for which parties are currently authorised to access the ETF's primary market and on what terms.
- **Consumed by:** SD-12.1 Investment Book of Record (IBOR) (reads FO-12 to confirm the AP's authorised status before booking the securities effects of a settled creation/redemption); SD-14.3 Financial Crime Prevention (reads FO-12 to confirm AP authorisation status when monitoring primary-market activity against counterparty-risk and financial-crime controls).

## FIBO alignment

**No published FIBO class for the ETF Authorised-Participant Agreement.** FIBO models party roles (broker-dealers, market-makers) and legal agreements at the conceptual level; it does not define a class for the ETF primary-market AP authorisation agreement in its published ontology.

- The AP as a party is a Legal Entity in a broker-dealer role: FIBO's `fibo-be-le-lp:LegalEntity` aligns to the `ap_entity_id` FK → E-01 at the entity level.
- The fund product the agreement grants access to is a collective investment vehicle: FIBO's collective-investment-vehicle framework aligns to FO-01 at the conceptual level.
- The AP Agreement relationship itself, its lifecycle (authorised/suspended/terminated), and the settlement-basis access rights are OpenIM additions with no FIBO equivalent in the published ontology.

## Open extensions

- A per-class AP authorisation variant — where the AP agreement covers only specific share classes of a multi-class ETF, a class-level authorisation record below the fund-level FO-12.
- An AP-agreement amendment history — the audit record of changes to the permitted settlement basis or operational terms, each with its effective date and authorising parties.
- Cross-fund AP roster management — where a fund manager maintains a list of APs authorised across its ETF range, a roll-up view linking multiple FO-12 records for the same AP across different funds.
