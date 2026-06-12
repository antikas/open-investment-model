# RA-05 — Asset Appraisal

An appraisal-based valuation of a directly-held real asset (RA-01) — a professional opinion of value produced by a qualified valuer to a recognised standard. The real-assets specialisation of how a real asset's value is determined.

**Specialises:** E-07 Valuation, of `method = appraisal`. Where the core Valuation entity records a value and how it was arrived at, RA-05 carries the appraisal-specific structure — the valuer, the standard, the valuation approach, the basis of value — that an appraised real asset needs and that a manager mark or an observable price does not.

## Purpose

A directly-held real asset has no quoted price. Its value is an **appraisal** — a qualified valuer's opinion, produced periodically to a recognised standard such as the RICS Valuation Global Standards (the Red Book) or the International Valuation Standards (IVS). The appraisal is the asset's mark, and like every mark in OpenIM it is an estimate with a method, a source and a confidence, recorded append-only so the value trajectory is preserved.

RA-05 makes the appraisal auditable: for any value on the asset's trajectory, the model can name the valuer, the standard followed, the approach used and the date of inspection. That is the governance the core Valuation entity asks for, made concrete for real assets.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `appraisal_id` | varchar | Primary key (also the `valuation_id` of the E-07 record). |
| `real_asset_id` | varchar (FK → RA-01) | The asset being appraised. |
| `valuation_date` | date | The date the appraisal is *as of*. |
| `appraised_value` | decimal | The opinion of value. |
| `currency` | char | The currency the value is expressed in. |
| `valuation_approach` | varchar | The method used — `income` (capitalising net operating income) / `comparable` (market evidence) / `cost` (depreciated replacement cost) / `residual` (development appraisal). |
| `basis_of_value` | varchar | The IVS 2025 basis of value — `market_value` / `market_rent` / `equitable_value` / `investment_value` / `synergistic_value` / `liquidation_value`. These are the bases defined by the International Valuation Standards; the IVS framework does *not* use "fair value" (an IFRS 13 term) as a basis. |
| `reporting_basis` | varchar | The financial-reporting or jurisdiction-specific basis the appraisal additionally satisfies, where that differs from the IVS basis — `ifrs13_fair_value` (the IFRS 13 fair-value measurement) / `existing_use_value` (the RICS UK-practice term) / `none`. Kept separate from `basis_of_value` so an IVS basis is never mislabelled as an IFRS or RICS term. |
| `valuation_standard` | varchar | The standard the appraisal was produced to — `RICS_Red_Book` / `IVS` / `USPAP` / other. |
| `valuer_entity_id` | varchar (FK → E-01) | The valuer or valuation firm, as a Legal Entity in the appraiser role. |
| `valuer_type` | varchar | `external` (an independent third-party valuer) / `internal` (an in-house valuation). |
| `discount_rate` | float | The discount or capitalisation rate applied, where the approach is income-based. |
| `inspection_date` | date | When the asset was last physically inspected for this appraisal. |
| `confidence_score` | float | A confidence indicator, where the appraisal carries material uncertainty — a Red Book material-valuation-uncertainty declaration maps here. |

## Notes

- RA-05 is **append-only**, inheriting the E-07 discipline: a new appraisal is added alongside the prior one, never over it. The set of appraisals for an asset is its value trajectory, and the trajectory — quarterly internal, periodically external — is what performance and time-series analysis read.
- `valuer_type` carries the independence governance. NCREIF-style practice and the Red Book both expect a periodic **independent external** appraisal alongside more frequent internal ones; the model keeps the two distinct so the cadence can be checked.
- `valuation_approach` follows the asset's state: an operational let building is appraised on an `income` or `comparable` basis; a pre-operational development (RA-04) is appraised on a `cost` or `residual` basis because it has no income yet. The approach makes the valuation auditable against the asset's lifecycle stage.
- The income-approach appraisal reads the operating record (RA-02) and, for real estate, the tenancy schedule (RA-03) — the appraisal is grounded in observed operating data, not asserted independently of it.

## Out of scope

- The generic valuation record — that is E-07 Valuation, the core entity RA-05 specialises; RA-05 carries only the appraisal-specific structure.
- Marks on fund interests or listed instruments — RA-05 is the directly-held-real-asset route only.
- Valuation policy, the valuation-level classification and contested-mark adjudication — that is SD-08.4 Fair-Value Governance, not the appraisal record.

## Owned and consumed by

- **Owned by:** SD-08.3 Private-Asset Valuation.
- **Governed by:** SD-08.4 Fair-Value Governance (valuation policy, the valuation-level 1/2/3 classification, contested marks).
- **Consumed by:** E-07 Valuation (the appraisal is the asset's valuation record); SD-12.2 Accounting Book of Record (ABOR), SD-09 Performance & Analytics, SD-05.2 Portfolio Management & Monitoring, SD-07.4 Concentration & Exposure Risk.

## Open extensions

- The restatement model — how a corrected appraisal for a prior date relates to the original, inherited from the open extension on E-07.
- The material-valuation-uncertainty declaration as structured data rather than a confidence scalar.
- The split between desktop and full-inspection appraisals, and the cadence policy linking the two.
