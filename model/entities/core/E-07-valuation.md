# E-07 — Valuation

A point-in-time value of a holding (E-04) — and the record of *how* that value was arrived at. Every holding is valued; the difference across asset classes is the method, not the entity.

## Purpose

A holding has a value, and the value changes over time. The Valuation entity captures one value at one date — and, crucially, its **method, source and confidence**, because not all values are equal. A liquid instrument is valued at an observable market price. An illiquid one — a private fund interest, a directly-held asset, an OTC derivative — is *marked*: estimated by a model, a manager or an appraiser, reviewed, and restated as new information arrives. The Valuation entity is universal; what differs is the method.

Because marks are estimates, OpenIM models valuation as an **append-only history**: a new valuation does not overwrite the prior one, it is added alongside it. The set of Valuations for a holding *is* its value trajectory — and the trajectory, with its confidence, is what time-series and J-curve analysis read.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `valuation_id` | varchar | Primary key. |
| `position_id` | varchar (FK → E-04) | The holding being valued — the **logical-holding identity** `position_id`, shared across E-04's two books of record, not a single book-row. A mark is a property of the instrument-in-a-portfolio and applies to both the IBOR and ABOR view, so the reference is to the logical holding, not to `(position_id, book)`. Null when the valuation is at instrument grain or share/unit-class grain. |
| `instrument_id` | varchar (FK → E-02) | The instrument or asset, where the valuation is at instrument rather than position grain. Null when the valuation is at position grain or share/unit-class grain. |
| `unit_class_id` | varchar (FK → FO-02) | The share or unit class, where the valuation is at share/unit-class grain — the **NAV-per-unit** record. Used when `method = manager_mark` and the struck value is the per-class NAV (class NAV ÷ units in issue). Null for position-grain and instrument-grain valuations. |
| `units_in_issue` | decimal | The number of units or shares outstanding for this class at the valuation date — the divisor in `NAV per unit = class NAV ÷ units in issue`. Populated only on class-grain (`unit_class_id` is non-null) records. Updated each dealing cycle as subscriptions create and redemptions cancel units; owned at this grain because it is the figure of record at the moment of the NAV strike, not static class reference data. |
| `valuation_date` | date | The date the valuation is *as of*. |
| `value_usd` | decimal | The valuation. For a class-grain record this is the NAV per unit in the class currency, translated to USD for the canonical layer. |
| `method` | varchar | How the value was determined — `observable_price` (a quoted market price) / `mark_to_model` / `manager_mark` / `appraisal` / `amortised_cost`. Class-grain NAV-per-unit records use `method = manager_mark`. |
| `valuation_level` | varchar | The fair-value hierarchy level — `level_1` (observable price) / `level_2` (observable inputs) / `level_3` (unobservable inputs). |
| `source` | varchar | The source the valuation came from — a pricing feed, an internal model, a manager report, an administrator statement, an appraiser. |
| `confidence_score` | float | A confidence score, where the value was modelled or extracted rather than observed. |

## Notes

- The entity is **append-only**. The set of Valuations for a holding is its value trajectory; no row is overwritten when a new mark arrives. A restated value for a prior date is a new row — restatement detection compares the new value to the prior one for the same date.
- **The valuation grain is the logical holding, not the book-row.** E-04's identity is the composite `(position_id, book)` — the same logical holding carries an IBOR record and an ABOR record. A valuation's `position_id` FK references the **logical-holding identity** (`position_id`, shared across both books), because a mark is a property of the instrument-in-a-portfolio that applies equally to both the real-time (IBOR) and accounting-basis (ABOR) view of the holding — the two books may differ on quantity or accrual timing, but not on the mark. So the same Valuation feeds the `market_value_usd` of both E-04 book-rows; the reference is book-agnostic by design, and is *not* the composite `(position_id, book)`.
- **Three grains — one entity.** E-07 accommodates valuations at three grains, distinguished by which of the three FK columns is populated: (a) **position grain** — `position_id` non-null, `instrument_id` and `unit_class_id` null (the primary case for holding-level marks); (b) **instrument grain** — `instrument_id` non-null, `position_id` and `unit_class_id` null (price-to-value at instrument level); (c) **share/unit-class grain** — `unit_class_id` non-null, `position_id` and `instrument_id` null (the NAV-per-unit record for an issued share or unit class, `method = manager_mark`). This follows the typed-extension pattern — one schema, three grain variants, discriminated by which FK is populated.
- **NAV per unit is a class-grain Valuation.** The investor-reported figure `NAV per unit = class NAV ÷ units in issue` is a `method = manager_mark` valuation at the `unit_class_id` grain. It is a figure of record: it is externally reported to investors, disclosed in regulatory filings, and used for dealing at the pricing point — it must be answerable from a stored record with provenance, not recomputed from a mart. `units_in_issue` is carried at this grain because it is the divisor at the moment of the NAV strike and is itself a dealing-cycle figure (updated as subscriptions create and redemptions cancel units); it is not static class reference data and does not belong on the FO-02 master record.
- `method`, `valuation_level` and `confidence_score` carry the mark-to-model governance: for an illiquid holding, every value is traceable to how it was produced and how far it can be relied on. For a liquid holding valued at an observable price, the method is simply `observable_price` and the confidence is implicit.
- **Private-markets specialisation.** A fund NAV is a Valuation with `method = manager_mark` (later possibly adjusted or independently marked). The private-markets pack records the fund-level NAV trajectory and the multiples (TVPI, DPI, RVPI) derived from it, and the four valuation lenses — manager NAV, adjusted NAV, mark-to-model NAV, realisable NAV — as distinct Valuations on the same holding.

## Out of scope

- The market observation a valuation may be built from — that is E-08 Price & Market Data; a Price is a market fact, a Valuation is the value of a *holding*.
- The appraisal-specific structure of a real-asset valuation — the valuer, the standard, the valuation approach — that is RA-05 Asset Appraisal, the real-assets specialisation of E-07.
- Valuation policy, the fair-value-level adjudication and contested-mark governance — that is SD-08.4 Fair-Value Governance, not the valuation record.
- A measured *risk* number — VaR, exposure, stress loss — that is E-19 Risk Measurement, the risk analogue of E-07, not a Valuation.

## Owned and consumed by

- **Owned by:** key-partitioned by the `method` attribute, using the same vocabulary the attribute schema declares. **SD-08.1 Security Pricing** for `method = observable_price` (a quoted market price) and `method = amortised_cost` (the rule-based amortised-cost price of a debt holding carried to maturity). **SD-08.2 Independent / Mark-to-Model Valuation** for `method = mark_to_model` (a quant-modelled mark). **SD-08.3 Private-Asset Valuation** for `method = manager_mark` (the manager- or administrator-reported mark of a private fund, private-credit or directly-held private interest) and `method = appraisal` (the real-asset appraisals RA-05 Asset Appraisal specialises). **SD-12.9 Fund Accounting & NAV** produces the official struck NAV of a vehicle the institution *operates* — recorded as `method = manager_mark`, distinguished from SD-08.3's marks not by a different method value but by being the NAV the institution strikes on a fund it operates (its investor capital accounts are PM-13), as opposed to the reported mark it consumes as an investor in an externally-managed interest. SD-12.9 also produces the **NAV-per-unit** record at the share/unit-class grain (`unit_class_id` FK → FO-02, `method = manager_mark`, `units_in_issue` populated) — the investor-reported figure of record for each class of an operated open-ended fund. Each Service Domain is the sole authoritative source for the instances it produces; the schema is the model's, common across methods so the value trajectory is same-shape. The full pattern is documented in [`ownership-map.md`](../../ownership-map.md).
- **Governed by:** SD-08.4 Fair-Value Governance.
- **Consumed by:** SD-05.2 Portfolio Management & Monitoring, SD-07 Investment Risk, SD-09 Performance & Analytics, SD-12 Investment Operations & Servicing, SD-13.10 Investment Reporting & Dashboards, SD-16.2 Owner & Investor Reporting (the NAV-per-unit series and disclosed figures in the regulatory disclosure documents).

## Open extensions

- Restatement modelling — how a corrected mark for a prior date relates to the original, and the lookback window for restatement detection.
- The confidence envelope — expressing valuation uncertainty as a range, not a point.
- The four-lens NAV detail in the private-markets pack.
