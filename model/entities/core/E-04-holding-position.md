# E-04 — Holding / Position

What the investor owns: a position in an instrument or asset (E-02), within a portfolio (E-03), at a point in time. The entity every exposure, risk and performance calculation ultimately reads from. Held at two grains — the real-time **IBOR** view and the official accounting-basis **ABOR** view.

## Purpose

A holding is the answer to "what do we own, how much, in which portfolio, as of when." It is the spine of the operating model: every number about the investor's investments — exposure, concentration, performance, NAV — is computed from holdings. It is genuinely universal: a position in a listed equity, a government bond, a listed future, an OTC swap, an LP interest in a private fund, or a directly-held building is, in each case, a Holding / Position. What differs is the instrument it points to and how that instrument is valued — not the holding entity itself.

OpenIM models the holding at **two books of record**, because the buy-side keeps two and they are not the same number on the same day:

- **IBOR** — the real-time, intraday view the front office trades and manages against.
- **ABOR** — the official, accounting-basis view used for NAV, financial reporting and audit.

The two are reconciled (SD-12.10); the model keeps them distinct rather than asserting a single position.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `position_id` | varchar | Part of the primary key. The identifier of the logical holding, shared across its two books of record. |
| `book` | varchar | `ibor` or `abor` — which book of record this position belongs to. Part of the primary key: the identity of a position is `(position_id, book)`, because the same logical holding carries two genuinely-different numbers, one per book. |
| `portfolio_id` | varchar (FK → E-03) | The portfolio the position sits in. |
| `instrument_id` | varchar (FK → E-02) | The instrument or asset held. |
| `as_of_date` | date | The date the position is *as of*. |
| `quantity` | decimal | Units held, where the instrument is quantity-denominated. |
| `commitment_usd` | decimal | Committed amount, where the instrument is a fund interest with an undrawn commitment. |
| `cost_basis_usd` | decimal | The cost basis of the position. |
| `market_value_usd` | decimal | The current value of the position (from the latest E-07 Valuation). |
| `currency` | char | The position's currency. |
| `accrued_income_usd` | decimal | Accrued but unpaid income — coupon, dividend — on the ABOR book. |

## Notes

- The primary key is the composite **`(position_id, book)`** — `book` is in the identity, not merely an attribute. A logical holding keeps one `position_id` across both books; the `book` value distinguishes its IBOR record from its ABOR record, which are reconciled against each other (SD-12.10) precisely because they are two records of the same thing that may not agree on a given day. `position_id` alone is not unique across the two books.
- **`position_id` is the logical-holding identity, shared across both book-rows — and that is the grain other entities reference E-04 at when the fact they record is book-agnostic.** A row of E-04 is identified by the composite `(position_id, book)`, but `position_id` on its own names the logical holding across both books. An entity whose fact attaches to the *logical holding* regardless of book references E-04 by `position_id` alone: a Valuation (E-07) — a mark applies to both the IBOR and ABOR view, and feeds the `market_value_usd` of both rows — and a Securities Loan (PB-10) — one lent-security relationship, not a per-book record. An entity whose fact is genuinely book-specific would carry the composite `(position_id, book)` instead; none does today. So `position_id` serves two roles: part of the composite row-identity, and the book-agnostic logical-holding handle that book-agnostic referencers use.
- A position references the universal **Instrument / Asset** (E-02). A position in a fund interest carries a `commitment_usd` and an undrawn portion; a position in a listed instrument carries a `quantity`; a position in a directly-held real asset carries neither in the same sense. The holding entity is the same; the instrument it points to differs.
- The position's *value* comes from E-07 Valuation — an observable price for a liquid instrument, a mark-to-model or manager NAV for an illiquid one. The holding records the value; the valuation entity records how it was arrived at.
- Look-through: a position in a fund interest is the LP's holding; the fund's own holdings in portfolio companies are modelled in the private-markets pack (PM-09 Fund Investment), and SD-07.5 Look-Through Exposure Analysis decomposes the one into the other.

## Out of scope

- The event that moved a holding to its current state — that is E-05 Transaction; E-04 is the state a transaction leaves behind, not the event.
- How a holding's value was arrived at — that is E-07 Valuation; E-04 records the resulting `market_value_usd` but not the method, source or confidence behind it.
- A fund's own holdings in portfolio companies — the investor's holding is a position in a *fund interest*; the fund's underlying holdings are PM-09 Fund Investment, reached by look-through.
- The instrument or asset a position is in — that is E-02 Instrument / Asset, which E-04 references through `instrument_id`.

## Owned and consumed by

- **Owned by:** key-partitioned by the `book` attribute, which is part of E-04's identity — every instance is *a position in a named book*. **SD-12.1 Investment Book of Record (IBOR)** is the sole authoritative source for instances where `book = ibor`; **SD-12.2 Accounting Book of Record (ABOR)** is the sole authoritative source for instances where `book = abor`. The two Service Domains are **co-equal owners of their partitions** — neither holds schema authority over the other; the schema is the model's, defined once for E-04. The two books diverge intraday and are reconciled by SD-12.10. Consumers must declare which book they consume — the front office reads `book = ibor`; SD-12.9 Fund Accounting & NAV, SD-09 Performance & Analytics, the BD-16 reporting capabilities (SD-16.2 / SD-16.3 / SD-16.4) and BD-14's internal-control attestation (SD-14.7) read `book = abor`; BD-07 Investment Risk reads ibor for intraday measures and abor for period-end. The full pattern is documented in [`ownership-map.md`](../../ownership-map.md).
- **Consumed by:** SD-07 Investment Risk (all domains), SD-09 Performance & Analytics, SD-05.2 Portfolio Management & Monitoring, SD-12.10 Reconciliation, SD-13.10 Investment Reporting & Dashboards — effectively every domain that reasons about what the investor owns.

## Open extensions

- Lot-level detail for tax-lot accounting.
- The IBOR / ABOR reconciliation model — how the two books differ and how breaks between them are tracked.
- The corporate-action adjustments that change a position between valuation dates (public-markets pack).
