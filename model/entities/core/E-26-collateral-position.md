# E-26 — Collateral Position

The generic record of collateral posted or received against a relationship — the asset, the direction, its valuation and haircut, its eligibility, and the counterparty. The shared collateral abstraction that derivatives margining (DR-04) and securities lending (PB-10) both reference.

## Purpose

Collateral is posted and received across several relationships — variation and initial margin against a derivatives master agreement, collateral against a securities loan, collateral in a repo. In every case the underlying fact is the same: a specific asset, of a value, with a haircut, posted in a direction, to or from a counterparty, eligible under some schedule. The Collateral Position is that shared fact, modelled once.

Without it, each collateralised relationship grows its own near-identical collateral model. The derivatives pack's Margin & Collateral Balance (DR-04) is the *running margin position* of a derivatives relationship; a securities loan (PB-10) has a collateral leg of its own; both reduce, underneath, to "what collateral, valued how, posted which way, against this relationship." E-26 is that common abstraction — the per-asset collateral record the relationship-level balances are composed from and reference. It is a position, not an event: the individual collateral movements are core Cash Flow Events (E-06) or Transactions (E-05); E-26 is the state those movements leave.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `collateral_position_id` | varchar | Primary key. |
| `relationship_type` | varchar | What the collateral is held against — `master_agreement` (DR-03) / `securities_loan` (PB-10) / `repo` / `clearing` (DR-05). |
| `relationship_ref` | varchar | The relationship the collateral is posted against — the DR-03 master agreement, the PB-10 loan, the DR-05 clearing relationship. |
| `direction` | varchar | `posted` (collateral the investor has given) / `received` (collateral the investor holds). |
| `collateral_instrument_id` | varchar (FK → E-02) | The asset posted as collateral — cash, a government bond, an equity. |
| `quantity` | decimal | The quantity of the collateral asset. |
| `market_value` | decimal | The market value of the collateral before haircut. |
| `haircut_pct` | decimal | The haircut applied to the collateral, as a percentage. |
| `collateral_value` | decimal | The post-haircut value the collateral counts for. |
| `eligibility_status` | varchar | `eligible` / `ineligible` / `under_review` — whether the asset meets the relationship's collateral-eligibility schedule. |
| `counterparty_entity_id` | varchar (FK → E-01) | The counterparty the collateral is posted to or received from — a Legal Entity in the counterparty role. |
| `as_of_date` | date | The date the collateral position is *as of*. |
| `segregated` | boolean | Whether the collateral is held with a third-party custodian. |

## Notes

- **A position, not an event.** The individual collateral movements — the transfer in, the substitution, the return — are core Cash Flow Events (E-06) or Transactions (E-05); E-26 is the resulting state, the collateral that stands posted or received as of a date. This is the same position-versus-event distinction E-04 Holding / Position keeps for instruments.
- E-26 is the shared abstraction the relationship-level collateral models reference: DR-04 Margin & Collateral Balance carries the *aggregate* margin position of a derivatives relationship and references the underlying per-asset E-26 positions; a securities loan's collateral leg (PB-10) references E-26 for the collateral held against the loan.
- The haircut and eligibility are the collateral-quality fields the optimisation and inventory function works over — which assets are cheapest-to-deliver, which are eligible where, how much post-haircut value the inventory provides.

## Out of scope

- The aggregate margin position of a derivatives relationship — the net exposure, the margin required and the margin call — that is DR-04 Margin & Collateral Balance, which references the per-asset E-26 positions beneath it; E-26 is the individual collateral record, not the relationship-level balance.
- The individual collateral movements — the transfers in and out — those are core E-06 Cash Flow Events or E-05 Transactions; E-26 is the resulting position.
- The securities loan or master agreement the collateral is posted against — those are PB-10 Securities Loan, DR-03 Master Agreement and DR-05 Clearing Relationship, referenced through `relationship_ref`.

## Owned and consumed by

- **Owned by:** SD-11.5 Collateral Optimisation & Inventory Management.
- **Consumed by:** SD-11.4 Margin & Collateral Operations (DR-04 composes E-26 positions), SD-12.13 Securities Lending Operations (PB-10's collateral leg), SD-07.2 Credit & Counterparty Risk Management (collateral offsets net exposure), SD-07.3 Liquidity Risk Management, SD-12.10 Reconciliation.

## Open extensions

- The collateral-substitution sub-model — how a posted asset is replaced by another, and the movement chain behind it.
- Collateral optimisation in full — cheapest-to-deliver selection and the eligibility-schedule model across relationships.
- The repo collateral leg as a first-class relationship type, beyond the discriminator carried here.
