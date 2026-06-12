# DR-05 — Clearing Relationship

The relationship through which an institutional investor's centrally cleared derivatives are cleared — the central counterparty (CCP), the clearing broker the investor accesses it through, and the clearing account that holds the cleared positions. One DR-05 record per (investor, clearing broker, CCP) clearing arrangement.

**Specialises:** none. A clearing relationship is a *legal and operational relationship* between Legal Entities — the investor, its clearing broker and the CCP — not an Instrument, Transaction or Holding. It references E-01 for those parties and is referenced by the cleared listed derivatives (DR-01) and cleared OTC derivatives (DR-02) it covers. It is the cleared-path analogue of DR-03 Master Agreement & Collateral, which governs the uncleared bilateral path.

## Purpose

A large share of an institutional investor's derivatives book is centrally cleared — every exchange-traded future and option by construction, and the OTC derivative classes subject to a mandatory clearing obligation. Clearing changes who the investor faces: the contract is novated so the CCP stands between the two original parties, and the investor's counterparty becomes the CCP, accessed through a clearing broker (a clearing member of the CCP). This is structurally different from the bilateral master-agreement relationship — there is no CSA, the margin terms come from the CCP's rulebook and risk model, and the default-management waterfall is the CCP's, not a bilateral close-out.

The investor needs the clearing relationship modelled explicitly so it can answer which CCP and which clearing broker a cleared position runs through, what the margining basis is, and what the investor's exposure is to the clearing broker itself — a real and separate exposure, because client collateral passes through the broker. Without DR-05, cleared positions have no modelled relationship and the cleared-versus-uncleared distinction collapses.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `clearing_relationship_id` | varchar | **Golden key.** The OpenIM-assigned identifier for the clearing arrangement. |
| `investor_entity_id` | varchar (FK → E-01) | The investing institution, as the clearing client. |
| `clearing_broker_entity_id` | varchar (FK → E-01) | The clearing broker / futures commission merchant — a Legal Entity in the `counterparty` (clearing-member) role — through which the investor accesses the CCP. |
| `ccp_entity_id` | varchar (FK → E-01) | The central counterparty — a Legal Entity in the `counterparty` (clearing-house) role. |
| `clearing_model` | varchar | The account-segregation model — `omnibus` / `individually_segregated` / `gross_omnibus` — determining how the investor's positions and collateral are held at the CCP. |
| `asset_class_scope` | varchar | The product scope of the relationship — `listed_derivatives` / `otc_rates` / `otc_credit`, etc. |
| `clearing_account_ref` | varchar | The clearing-account identifier at the clearing broker / CCP. |
| `clearing_agreement_date` | date | The date the clearing agreement with the broker was executed. |
| `margin_basis` | varchar | The CCP's margin methodology — the model the CCP's initial-margin requirement is computed under (e.g. a historical-simulation or SPAN-style model). |
| `status` | varchar | `active` / `terminated`. |

## Notes

- **Relationship to ISDA CDM.** CDM models the **clearing lifecycle event** — the novation by which a bilateral trade is replaced by two trades facing the CCP — as a lifecycle event at the transaction grain. DR-05 does not re-model that event; where CDM is in use, the cleared DR-02 record carries the CDM reference for the clearing event. DR-05 is the **portfolio-level relationship** the cleared positions hang off — the standing arrangement, not the per-trade novation. The boundary: CDM models the act of clearing a trade; OpenIM models the clearing relationship the trades are cleared into.
- DR-05 is the **cleared-path peer of DR-03**. An OTC derivative is governed by *either* a bilateral master agreement (DR-03, uncleared) *or* a clearing relationship (DR-05, cleared) — the `clearing_status` on DR-02 discriminates. A listed derivative (DR-01) is *always* cleared and so always sits under a DR-05. An investor typically holds both kinds of relationship at once.
- The **clearing broker is a distinct exposure**. Even though the CCP is the ultimate counterparty, client collateral and positions pass through the clearing broker, and the `clearing_model` (the segregation arrangement) determines how exposed the investor is to a clearing-broker default — individually-segregated accounts are protected differently from omnibus accounts. SD-07.2 Credit & Counterparty Risk Management reasons about both the CCP and the clearing-broker exposure, and DR-05 carries the structure that lets it.
- Margining for a cleared relationship runs against the **CCP's rulebook and risk model**, not a negotiated CSA. The margin balances themselves are DR-04 records with `relationship_type = clearing` pointing at this entity.

## Out of scope

- The clearing lifecycle event — the novation by which a bilateral trade is replaced by two trades facing the CCP — that is ISDA CDM's at the transaction grain; DR-05 is the standing relationship, not the per-trade novation.
- The bilateral uncleared path — that is DR-03 Master Agreement & Collateral Terms; an OTC derivative is governed by either DR-03 or DR-05, and `clearing_status` on DR-02 discriminates.
- The cleared positions themselves — those are DR-01 Listed Derivative and cleared DR-02 OTC Derivative, which hang off DR-05.
- The margin balances under the clearing relationship — those are DR-04 Margin & Collateral Balance with `relationship_type = clearing`; DR-05 carries the relationship, DR-04 the running margin position.

## Owned and consumed by

- **Owned by:** SD-14.9 Legal & Contract Management (the clearing agreement is a legal document).
- **Sourced from:** SD-06.6 Derivatives & OTC Trade Management and SD-06.3 Execution Venue & Broker Management (the clearing arrangement is established alongside the trading and broker setup).
- **Consumed by:** SD-11.4 Margin & Collateral Operations, SD-07.2 Credit & Counterparty Risk Management, SD-12.10 Reconciliation (cleared positions reconciled against the CCP and clearing broker), DR-04 Margin & Collateral Balance.

## Open extensions

- The default-fund-contribution sub-model — the investor's or clearing member's contribution to the CCP default fund, and the mutualised-loss exposure that carries.
- The porting model — what happens to the investor's cleared positions and collateral if its clearing broker defaults.
- The relationship between a clearing relationship and the CCP's eligible-collateral and concentration rules.
- The concrete representation of the CCP margin model where it is needed for independent margin replication.
