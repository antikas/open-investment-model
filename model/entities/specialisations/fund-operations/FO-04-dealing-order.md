# FO-04 — Dealing Order

A subscription, redemption, transfer or switch instruction submitted by or on behalf of an investor in an open-ended fund — the event at which the investor register moves.

**Specialises:** E-05 Transaction. A dealing order is an investment event: it changes an investor's units held (FO-03) and results in cash flows (E-06). FO-04 adds the fund-operations structure — the dealing-specific attributes (order type, cut-off, struck NAV, units and amount at the class grain) and the ISO 20022 `setr` family grain. It is the open-ended-fund analogue of PB-03 Order in the public-markets pack — the order at the transfer agent's dealing window, not on an exchange order book.

## Purpose

Every movement on the open-ended fund investor register begins with a dealing order: a subscription creates new units, a redemption cancels them, a switch moves units from one class to another, a transfer moves units between investors. FO-04 is the authoritative record of that event — the instruction, the accepted order type, the dealing cut-off it was submitted against, the NAV per unit at which it was struck, the units issued or cancelled, and the cash settled.

Without FO-04, the audit trail "on what basis were units created, cancelled or transferred, and at what price?" is unanswerable. FO-04 is the immutable event record of the dealing window; FO-03 Investor Unitholding is the register state it leaves behind.

FO-04 is distinct from:

- **PB-03 Order** — the securities-market order on an exchange order book (listed instrument, broker-routed, matching). FO-04 is a direct dealing instruction to the transfer agent at a forward NAV price; there is no exchange intermediary.
- **PM-07 Capital Call** / **PM-08 Distribution** — the capital drawdown and return events of a closed-end fund. Those are commitment-based events (PM-06 LP Commitment anchors the relationship); FO-04 is a voluntary investor instruction in an open-ended dealing window.
- **E-05 Transaction** at the `trade` type — a market trade in a listed instrument executed via a broker. FO-04 is at `transaction_type = subscription / redemption / transfer / switch`, the fund-dealing grain, not the brokered-market grain.

## Attribute schema

### Identity and relationship

| Column | Type | Definition |
|---|---|---|
| `order_id` | varchar | **Golden key.** The OpenIM-assigned canonical identifier for this dealing order. |
| `share_class_id` | varchar (FK → FO-02) | The share or unit class the order is against — the class the investor is subscribing to, redeeming from, switching into, or switching out of. |
| `investor_entity_id` | varchar (FK → E-01) | The investor — a Legal Entity in the unitholder role — submitting the order. |
| `unitholding_id` | varchar (FK → FO-03) | The investor's unitholding record in the class, updated when the order settles. |

### Order classification

| Column | Type | Definition |
|---|---|---|
| `order_type` | varchar | `subscription` (investor buys into the class) / `redemption` (investor sells out of the class) / `transfer` (units move to a different investor in the same class) / `switch` (investor moves between classes — the outgoing leg is a redemption; the incoming leg a subscription, captured as a paired order). |

### Dealing mechanics

| Column | Type | Definition |
|---|---|---|
| `deal_date` | date | The date the order was accepted for dealing — the dealing date against which the cut-off applies. |
| `cut_off` | timestamp | The dealing cut-off time and date for the relevant dealing cycle of the class (from FO-02 via FO-01's `dealing_cut_off`). Orders received after cut-off are deferred to the next dealing cycle. |
| `valuation_date` | date | The date the NAV per unit used to price this order is struck (typically one business day after deal date for a T+1 fund, same day for a same-day fund). |
| `struck_nav_per_unit` | decimal | The official NAV per unit at which the order was executed — the class-grain E-07 Valuation record (`unit_class_id = share_class_id`, `method = manager_mark`) struck by SD-12.9 for the valuation date. This is the price of record; it governs the units / amount relationship. |
| `units` | decimal | The number of units issued (subscription, switch-in, transfer-in — positive) or cancelled (redemption, switch-out, transfer-out — negative). Signed by direction. |
| `amount` | decimal | The gross cash amount of the order in `class_currency`. For a subscription: `amount = units × struck_nav_per_unit` adjusted for any dilution levy or swing-pricing adjustment. For a redemption: the cash returned to the investor before any early-redemption fee. |
| `class_currency` | char(3) | The dealing currency of the order, derived from `FO-02.class_currency`. |

### Settlement

| Column | Type | Definition |
|---|---|---|
| `settlement_date` | date | The date cash and units are settled — the dealing cycle's settlement basis (e.g. T+3 for subscription cash; same day for unit issuance in some structures). |
| `status` | varchar | `received` / `accepted` / `priced` / `settled` / `cancelled`. The operational status of the order through the dealing lifecycle. |

### Anti-dilution controls

| Column | Type | Definition |
|---|---|---|
| `dilution_adjustment` | decimal | The dilution levy or swing-pricing adjustment applied to the order, in `class_currency`. Null where no adjustment applies. Positive for a subscription (the subscribing investor bears the dealing cost); negative for a redemption (the redeeming investor bears it). This is the anti-dilution amount from FO-01's `swing_pricing` or `anti_dilution_levy` policy, applied at the order level. |

## Notes

- **FO-04 is an immutable event.** A dealing order that settled is a fact; corrections are new records (a reversal order paired with a correcting order), not edits. This is the E-05 immutability principle applied at the fund-dealing grain.
- **ISO 20022 `setr` family.** The ISO 20022 Securities Trade (`setr`) message family — specifically `setr.010`, `setr.012`, `setr.014`, `setr.016` (subscription/redemption order and confirmation) — is the standard wire format for fund-dealing messages. FO-04's attribute schema is the semantic model behind the `setr` grain; the `order_id` is the OpenIM golden key, and the `setr` reference is held in E-13 / E-14 following the identifier-canonicality principle.
- **Switch orders are paired.** A class switch is two legs: an outgoing `switch_out` redemption from Class A and an incoming `switch_in` subscription to Class B, priced at the respective class NAVs. Both carry the same investor and a cross-reference linking them as a switch pair. The pairing is an open extension in the attribute schema — the two legs are each a separate FO-04 record at the current model grain.
- **Struck NAV is a reference to E-07, not a duplicate.** The `struck_nav_per_unit` field carries the NAV at which the order priced, for audit and completeness on the dealing record. The authoritative, provenance-bearing figure of record is the class-grain E-07 Valuation owned by SD-12.9. `struck_nav_per_unit` is a declared read-cache on the order, derivable from E-07 at the same `(unit_class_id, valuation_date)`.
- **`asset_class` is not on FO-04 directly.** The asset class of the dealing order follows from FO-02 → FO-01 → `asset_class int (FK → E-09)`. FO-04 does not carry a redundant FK; the class context is the FO-02 reference.

## Out of scope

- The order book mechanics of an exchange — FO-04 is a transfer-agent dealing window, not a market order book. Matching and execution are not relevant here; the NAV is struck after cut-off for all accepted orders at the same price.
- The investor-client relationship context — that is BD-15; FO-04 is the back-office operational event, not the client-facing instruction management.
- The capital-call and distribution mechanics of a closed-end fund commitment — those are PM-07 Capital Call and PM-08 Distribution, anchored by PM-06 LP Commitment.
- The fund distribution / income payment to unitholders — that is FO-05 Fund Distribution Event owned by SD-12.7; FO-04 is the dealing event (unit creation / cancellation), not the income-payment event.

## Owned and consumed by

- **Owned by:** SD-12.15 Transfer Agency & Investor Dealing — the transfer agency accepts, prices and settles dealing orders; SD-12.15 is the system of record for the dealing window and the order lifecycle.
- **Consumed by:** SD-12.1 Investment Book of Record (IBOR) (the cash and position effects of settled orders enter the book of record); SD-12.2 Accounting Book of Record (ABOR) (the accounting-basis position and cash effects); SD-12.9 Fund Accounting & NAV (units in issue update from settled subscriptions and redemptions; the struck NAV per unit on FO-04 cross-references the E-07 record SD-12.9 owns); SD-12.10 Reconciliation (dealing-cash reconciliation between the transfer agent and the fund's bank account); SD-14.3 Financial Crime Prevention (investor-flow monitoring — subscription and redemption patterns).

## FIBO alignment

**Partial — structural alignment at the instrument/investor level; dealing-mechanics layer is OpenIM.**

- FIBO's collective-investment-vehicle framework — dealing orders (subscriptions and redemptions in a fund) align at the conceptual level to FIBO's fund-unit transaction concepts. FIBO does not define fund-order classes (FundSubscriptionOrder, FundRedemptionOrder) in its published ontology; the operative standard at the dealing-message grain is ISO 20022 `setr`, which FIBO's framework is complementary to.
- **ISO 20022 `setr`** — the operative standard for the transfer-agency dealing message exchange. FO-04 is the semantic model at the `setr` grain.

What FIBO does not model, and what FO-04 adds:

- The **dealing-cycle cut-off mechanics** — the `cut_off` timestamp, the `valuation_date` derivation, and the forward-pricing discipline (orders placed against a future, not a current, NAV).
- The **anti-dilution adjustment** — the dilution levy and swing-pricing adjustment applied at the individual order level from the fund's anti-dilution policy (FO-01 `swing_pricing`).
- The **switch-leg pairing** — the outgoing and incoming legs of a class switch as a linked pair of FO-04 records.

## Open extensions

- Switch-leg cross-reference — a pair-reference field linking the outgoing and incoming FO-04 legs of a class switch.
- In-specie subscription and redemption — the transfer of securities (rather than cash) into or out of a fund at a dealt NAV; used in ETF authorised-participant create/redeem and some institutional in-specie mandates.
- The large-deal and dealing-suspension controls sub-model — the governance inputs that gate an order from acceptance when it exceeds a threshold or when the fund's gates are in effect (FO-01 `redemption_gate`).
