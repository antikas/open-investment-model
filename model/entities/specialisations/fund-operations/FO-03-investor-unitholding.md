# FO-03 — Investor Unitholding

The per-investor, per-share-class record of units held in an open-ended fund — the open-ended parallel to PM-06 LP Commitment.

**Specialises:** E-04 Holding / Position. An investor's holding of units in a share or unit class is a position in that class: an amount owned (units held), a cost basis, an as-of date. FO-03 adds the fund-operations structure — the link to the class (FO-02), the investor (E-01), and the open-ended-specific attributes (cost basis in class currency, the dealing-cycle at which the position was last updated). Where PM-06 is the investor-side commitment into a *closed-end* fund operated by someone else, FO-03 is the manager-side per-investor position in the *open-ended* registered fund the institution itself operates and administers. One FO-03 row exists per (investor, share class).

## Purpose

A fund investor register is a register of who holds what units in each class of each fund. FO-03 is the record at the grain that register is kept — one row per (investor, share class), maintained by the transfer agent as subscriptions add units, redemptions cancel them, and switches move them between classes. Without this record the manager cannot answer "how many units does Investor X hold in Class I GBP?", cannot strike the per-investor distribution amount, and cannot produce the investor's unit statement.

FO-03 is the **manager-side** per-investor register position. It is distinct from:

- **PM-06 LP Commitment** — the investor-side record of capital committed into a *closed-end* fund. PM-06 is a commitment (a promise; drawn down via capital calls); FO-03 is a position (units actually held at a dealt price following subscription).
- **PM-13 Investor Capital Account** — the manager-side periodic capital-account roll-forward for an operated fund. PM-13 is an accounting-period roll-forward (contributions, distributions, allocated gain); FO-03 is the real-time register position (units held, cost basis, as-of date). A manager operating a fund carries both: FO-03 for the live dealing register; PM-13 for the capital-account statement it issues.

The distinctions preserve the role-model: the closed-end and open-ended fund structures have materially different record-keeping mechanics. FO-03 is the open-ended register grain; PM-06 and PM-13 are the closed-end capital account forms.

## Attribute schema

### Identity and relationship

| Column | Type | Definition |
|---|---|---|
| `unitholding_id` | varchar | **Golden key.** The OpenIM-assigned canonical identifier for this unitholding record. |
| `share_class_id` | varchar (FK → FO-02) | The share or unit class the investor holds units in. One FO-03 row per (investor, share class). |
| `investor_entity_id` | varchar (FK → E-01) | The investor — a Legal Entity in the unitholder role. For omnibus registrations (e.g. a platform holding units on behalf of underlying investors), this is the legal holder of record. |

### Position

| Column | Type | Definition |
|---|---|---|
| `units_held` | decimal | The number of units the investor holds in this share class at `as_of_date`. Updated at each dealing cycle as subscriptions add units and redemptions cancel them. |
| `as_of_date` | date | The date the unitholding is as of — the last dealing cut-off at which the position was updated. |
| `cost_basis` | decimal | The investor's cost basis in this class, in `class_currency` (from FO-02). Aggregate of subscription amounts at dealt prices, adjusted for switch-ins and partial redemptions, following the lot-relief convention the transfer agent applies. |
| `class_currency` | char(3) | The currency of this unitholding, derived from `FO-02.class_currency`. Carried here for query convenience; the canonical source is FO-02. |

### Identifiers

| Column | Type | Definition |
|---|---|---|
| `account_reference` | varchar | The investor's account or holder reference at the transfer agent — the operational identifier used in dealing confirmations and statements. This is an operational read-cache; the canonical investor identity is `investor_entity_id` (FK → E-01) following the identifier-canonicality principle. |

## Notes

- **One row per (investor, share class), updated in place.** The unitholding is a state record (what the investor holds today), not an immutable event. Subscriptions, redemptions and switches produce Dealing Orders (FO-04) as the events; each settled order updates the FO-03 row. The event trail is FO-04; the current register state is FO-03.
- **Omnibus and nominee registrations.** Many open-ended funds are registered through intermediaries — platforms, distributors, custodians — that hold units in omnibus accounts on behalf of underlying investors. In that case, the legal holder of record (the platform) is the `investor_entity_id`; the underlying investor accounts are at the platform's recordkeeping layer, below the fund's register. FO-03 models the register at the legal-holder level. Look-through to underlying investors is a later extension.
- **Active register only.** A position reduces to zero when all units are redeemed; the FO-03 row records zero units from the last redemption date. The full holding history is the sequence of FO-04 Dealing Order events.
- **Cost basis follows the lot-relief convention.** The `cost_basis` field reflects the aggregate cost basis under whichever lot-identification method (average cost, FIFO, etc.) the transfer agent applies for this fund. The method is a governed reference; this field is the accumulated result.

## Out of scope

- The events that moved the unitholding to its current state — those are FO-04 Dealing Order; FO-03 is the register state, not the event.
- The distribution paid from the fund to the investor — those are FO-05 Fund Distribution Events owned by SD-12.7; FO-03 records the position, not the income.
- The NAV per unit at which a subscription was struck — that is the class-grain E-07 Valuation record produced by SD-12.9; FO-03 carries `cost_basis` as the aggregate cost of entry, not the per-dealing-cycle price.
- Participant-level DC recordkeeping below the omnibus account — excluded from this pack by design; the register ends at the legal holder of record.

## Owned and consumed by

- **Owned by:** SD-12.15 Transfer Agency & Investor Dealing — the transfer-agency function maintains the investor register: creating FO-03 records on first subscription, updating them as dealings settle, and closing them on full redemption.
- **Consumed by:** SD-12.7 Income & Distribution Processing (the per-investor distribution amount — the per-unit income multiplied by FO-03 `units_held` at the ex-date); SD-12.9 Fund Accounting & NAV (reads the FO-03 register at the dealing cut-off to derive the units-in-issue input for the NAV strike; the struck figure of record is stored on the class-grain valuation record SD-12.9 owns at `method = manager_mark` — that stored `units_in_issue` is the canonical NAV-per-unit divisor for any historical NAV, not a re-sum of current register rows; FO-03 is the operational source, the struck valuation record is the figure of record); SD-15.14 Client & Investor Reporting (the investor's unit balance and statement); SD-16.2 Owner & Investor Reporting (regulatory and shareholder reporting at investor-register grain).

## FIBO alignment

**Partial — structural alignment at the investor/instrument level; register-mechanics layer is OpenIM.**

- `fibo-sec-fund-fund:FundUnit` — FIBO's concept of a unit held in a collective investment vehicle aligns to FO-03's position in a share or unit class.
- FIBO's collective-investment-vehicle framework — FO-03 represents the investor's ownership interest in a share or unit class, which aligns to FIBO's account-and-ownership constructs at the conceptual level. No specific FIBO class maps precisely to the per-investor, per-class register-position grain FO-03 models.

What FIBO does not model, and what FO-03 adds:

- The **per-investor register grain** with dealing-cycle update mechanics (subscriptions add, redemptions cancel, switches move between FO-02 rows).
- The **omnibus / legal-holder-of-record distinction** and its look-through boundary.
- The **cost basis** as an accumulated, lot-method-governed field at the class grain.

## Open extensions

- Look-through from an omnibus account to underlying investor accounts within a platform or nominee structure.
- Lot-level cost basis tracking — the individual subscription tranches and their carried cost, supporting specific-lot identification methods.
- The DC recordkeeping extension — not in scope for this pack; see the DC-exclusion section in the fund-operations pack README.
