# DR-04 — Margin & Collateral Balance

The operational margining position of a derivatives relationship — the collateral posted and received, and the initial and variation margin owed, against a master-agreement set (DR-03) or a clearing relationship (DR-05) at a point in time. The entity that answers "how much collateral are we exposed for, and is the relationship adequately margined right now."

**Specialises:** none. A margin balance is not an Instrument, not a Transaction and not a Holding in the core sense — it is a *position in the collateral relationship*, the running state of an obligation. It references DR-03 and DR-05, and the individual collateral movements are core Cash Flow Events (E-06) or Transactions (E-05), but the balance itself is a native derivatives-pack entity. It is to the collateral relationship what E-04 Holding / Position is to an instrument: the state, distinct from the events that moved it.

## Purpose

A derivatives relationship is collateralised continuously. As the mark-to-market of the OTC derivatives under a master agreement moves, the net exposure moves, and collateral is called to keep that exposure within the CSA threshold. Variation margin covers the current cost of replacing the trades; initial margin (the independent amount, or regulatory IM) covers the further loss that could accrue between a counterparty default and close-out. The investor must know, for every relationship, the current margin requirement, the collateral actually posted and received, and the gap between them — the margin call.

Without this entity modelled explicitly the operating model has the *trades* (DR-02) and the *agreement* (DR-03) but not the running collateral state, and collateral becomes an off-system spreadsheet. DR-04 makes the margining position a first-class object so margin calls, collateral adequacy, collateral optimisation and the liquidity claim of margin can all be computed and audited. The 2020 and 2022 margin-call spikes were, operationally, failures to see this state clearly and fund it.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `balance_id` | varchar | Primary key. |
| `relationship_type` | varchar | `master_agreement` (bilateral, uncleared) or `clearing` (cleared, via a CCP). |
| `master_agreement_id` | varchar (FK → DR-03) | The bilateral master-agreement set, when `relationship_type = master_agreement`; null otherwise. |
| `clearing_relationship_id` | varchar (FK → DR-05) | The clearing relationship, when `relationship_type = clearing`; null otherwise. |
| `as_of_date` | date | The date the balance is *as of*. |
| `margin_type` | varchar | `variation_margin` / `initial_margin` — which margin this balance records. |
| `net_exposure_usd` | decimal | The net mark-to-market exposure of the covered trades, signed by direction. |
| `margin_required_usd` | decimal | The collateral the relationship requires given the exposure and the CSA / CCP terms. |
| `collateral_posted_usd` | decimal | Collateral the investor has posted to the counterparty / CCP. |
| `collateral_received_usd` | decimal | Collateral the investor holds from the counterparty. |
| `margin_call_usd` | decimal | The outstanding call — the gap between required and posted/received; positive means collateral owed. |
| `collateral_currency` | char | The currency the balance is expressed in. |
| `disputed` | boolean | Whether the margin amount is in dispute with the counterparty. |
| `segregated` | boolean | Whether the collateral is held with a third-party custodian — true for initial margin, which must be segregated. |

## Notes

- **Relationship to ISDA CDM.** CDM models the *collateral and margin-call lifecycle events* — the margin-call event, the collateral transfer — at the transaction grain, and CDM 6.0 simplified the margin-calculation representation. DR-04 does not re-model those events: each collateral movement is a core Cash Flow Event (E-06) or Transaction (E-05), and where CDM is in use the movement carries the CDM event reference. DR-04 is the **portfolio-level balance** the events roll up to — the state, not the event stream. The boundary: CDM models the margin call and the collateral transfer as lifecycle events; OpenIM models the running collateral position and its adequacy.
- DR-04 spans both the **cleared and uncleared** paths through `relationship_type`. An uncleared balance is computed against the CSA terms in DR-03 — the threshold and minimum transfer amount determine when and how much is called. A cleared balance is computed against the CCP's margin model through the clearing relationship (DR-05). Modelling both as one entity with a discriminator keeps the operating model's margin view unified.
- **Initial margin and variation margin are kept as separate balances** (`margin_type`), because they behave differently: variation margin is title-transferred and nets to the exposure; initial margin is segregated with a custodian (`segregated = true`), is one-way in effect, and is a gross independent amount. A single relationship therefore typically has at least two DR-04 rows.
- The margin call is a **liquidity claim**. The outstanding `margin_call_usd` across all relationships is a near-term funding obligation that SD-11.4 Margin & Collateral Operations and the treasury liquidity domains must be able to meet — collateral calls are callable at short notice and concentrate under exactly the stressed-market conditions that move exposures.
- **The underlying collateral movements reference E-26 Collateral Position** — the per-asset posted / received collateral records (asset, direction, valuation, haircut, eligibility) that DR-04's aggregate balances roll up from. E-26 is the shared collateral abstraction; DR-04 is the relationship-level margin position composed of the E-26 positions held against the relationship.

## Out of scope

- The individual collateral movements — those are core E-06 Cash Flow Events or E-05 Transactions; DR-04 is the running balance the movements roll up to, not the event stream.
- The margin-call and collateral-transfer lifecycle events — those are ISDA CDM's at the transaction grain; DR-04 is the portfolio-level balance, the state not the event.
- The bilateral legal framework or the clearing relationship the balance is computed against — those are DR-03 Master Agreement and DR-05 Clearing Relationship, referenced through `master_agreement_id` / `clearing_relationship_id`.
- The collateral-inventory detail — the specific securities and cash posted and their haircuts — named as an open extension; the entity carries aggregate balances.

## Owned and consumed by

- **Owned by:** SD-11.4 Margin & Collateral Operations.
- **Calculated by:** SD-11.4 Margin & Collateral Operations (IM / VM calculation and margin-call settlement).
- **Consumed by:** SD-07.2 Credit & Counterparty Risk Management (collateral offsets net counterparty exposure), SD-07.3 Liquidity Risk Management, SD-11.2 Liquidity Management, SD-11.5 Collateral Optimisation & Inventory Management, SD-12.10 Reconciliation (collateral reconciled against the counterparty / CCP), SD-08.5 Valuation Adjustments & Reserves.

## Open extensions

- The collateral-inventory sub-model — the specific securities and cash posted, their haircuts, and collateral substitution and optimisation.
- The relationship between a DR-04 balance and the individual collateral-movement Cash Flow Events (E-06) that compose it.
- The margin-dispute sub-model — how a disputed amount is tracked, escalated and resolved.
- Wrong-way-risk modelling — where collateral value correlates with counterparty default.
