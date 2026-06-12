# PB-07 — Corporate Action

An event initiated by a security's issuer that changes the security, the holding in it, or both — a dividend, a split, a merger, a rights issue, a tender offer.

**Specialises:** E-05 Transaction (`transaction_type = corporate_action`). The core Transaction names the event; PB-07 carries the corporate-action sub-model — the mandatory / voluntary distinction, the key-date calendar, and the election where the holder has a choice. It aligns to the ISO 20022 securities-events (`seev`) message family — announcement, entitlement, instruction and confirmation messages.

## Purpose

A corporate action is the issuer acting on its own securities, and the investor is a passive (or, for voluntary events, a choosing) recipient. The event must be captured, validated against the holding, processed, and its entitlement — cash, new securities, or both — applied. The entity exists because a corporate action is **not** a trade: it is not executed, it has no counterparty, and its terms and timing are set by the issuer. It needs its own structure — the mandatory / voluntary discriminator that decides whether the holder must act, and the four-date calendar (announcement, ex-date, record date, payment date, plus an election deadline for choice events) that governs entitlement.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `corporate_action_id` | varchar | Primary key. |
| `transaction_id` | varchar (FK → E-05) | The core Transaction this event belongs to. |
| `instrument_id` | varchar (FK → E-02) | The security the event affects. |
| `event_type` | varchar | `cash_dividend` / `stock_dividend` / `stock_split` / `reverse_split` / `rights_issue` / `merger` / `spin_off` / `tender_offer` / `exchange_offer` / `coupon_payment` / `redemption` / `name_change`. |
| `mandatory_voluntary` | varchar | `mandatory` (applies automatically) / `mandatory_with_choice` (applies, but with a default-able option) / `voluntary` (the holder must elect to participate). |
| `announcement_date` | date | When the issuer or its agent publicly disclosed the event. |
| `ex_date` | date | The date on and after which a buyer does not receive the entitlement. |
| `record_date` | date | The date on which the issuer's registrar identifies holders of record. |
| `payment_date` | date | The date the entitlement (cash or securities) is delivered. |
| `election_deadline` | date | For a choice or voluntary event — the market deadline by which the holder's instruction must be submitted; null for a pure-mandatory event. |
| `terms_ratio` | varchar | The event terms — e.g. `2:1` for a split, the dividend rate per share, the subscription ratio for a rights issue. |
| `resulting_instrument_id` | varchar (FK → E-02) | The new or changed instrument an entitlement delivers, where the event produces securities; null for a pure-cash event. |
| `cash_rate` | decimal | The cash entitlement per unit held, where the event pays cash. |
| `currency` | char | The currency of a cash entitlement. |
| `event_status` | varchar | `announced` / `confirmed` / `election_open` / `election_closed` / `processed` / `cancelled`. |
| `source` | varchar | The data source the event was captured and validated from. |

## Notes

- For a **voluntary** or **mandatory-with-choice** event, the holder's decision is captured per affected portfolio as an *election* — the chosen option and the quantity it applies to, submitted before the `election_deadline`. The election deadline is a hard operational stop; late elections are rejected. The entity holds the election as an attribute set; an open extension below promotes it to its own sub-entity, because one event can carry one election per portfolio.
- Entitlement is calculated against the holding (E-04) **as at the record date**, not the processing date — the date discipline is the core of the sub-model.
- A corporate action's cash or securities outcome is itself a Transaction (E-05) and Cash Flow Event (E-06) — a dividend pays cash, a split changes quantity, a merger replaces one instrument with another. PB-07 is the event; the position and cash consequences are recorded through the core entities.
- A coupon payment on a debt instrument is a corporate action of `event_type = coupon_payment`; its forward schedule is materialised by PB-08 Income Schedule, and PB-07 records the actual event when it occurs.

## Out of scope

- The generic transaction record a corporate action specialises — that is E-05 Transaction of `transaction_type = corporate_action`; PB-07 carries the corporate-action sub-model.
- The position and cash consequences of the event — those are recorded through core E-04 Holding / Position and E-06 Cash Flow Event; PB-07 is the event, not its outcome.
- The forward calendar of expected coupons and dividends — that is PB-08 Income Schedule; PB-07 records an income event when it *occurs*, PB-08 is the projection before it occurs.
- The holder's election promoted to its own sub-entity — named as an open extension; the entity holds the election as an attribute set.

## Owned and consumed by

- **Owned by:** SD-12.6 Corporate Actions Processing.
- **Populated via:** SD-13.4 Market & Reference Data Management (corporate-action data feeds).
- **Consumed by:** SD-12.7 Income & Distribution Processing, SD-12.1 Investment Book of Record (IBOR), SD-12.2 Accounting Book of Record (ABOR), SD-12.12 Proxy Voting & Stewardship Operations (meeting events), SD-05.2 Portfolio Management & Monitoring, SD-13.1 Instrument & Security Master (instrument-changing events).

## Open extensions

- The **election** promoted to its own sub-entity — one election per (event, portfolio), with the chosen option and quantity.
- The entitlement-calculation sub-model — the rule from event terms and record-date holding to the resulting cash / securities movement.
- The handling of complex multi-leg events — mergers with cash-and-stock consideration, spin-offs with cost-basis apportionment.
