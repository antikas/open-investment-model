# RA-04 — Development Project

The construction or development lifecycle of a real asset (RA-01) — the period before the asset is operational, and, for infrastructure, the concession that frames its whole life. One record per development undertaking on an asset.

## Purpose

Not every real asset is bought operational. An investor that takes greenfield risk — building a wind farm, constructing a toll road, developing a building — owns an asset that is, for a period, a *project*, not an income-producing thing. During that period the asset has no operating record (RA-02) and no income to appraise; what it has is a capital programme, a construction counterparty, a completion milestone and construction risk. RA-04 carries that lifecycle.

It also carries the **concession** — for a concession-based infrastructure asset, the agreement with a public authority that grants the right to build and operate, and that fixes the asset's economic life. The concession is the frame the whole asset sits inside, so it is modelled with the development record even though it persists into the operational phase.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `project_id` | varchar | Primary key. |
| `real_asset_id` | varchar (FK → RA-01) | The asset being developed. |
| `development_type` | varchar | `greenfield` (new asset, undeveloped site, highest risk) / `brownfield` (extension or redevelopment of an existing asset) / `refurbishment`. |
| `project_phase` | varchar | `pre_construction` / `under_construction` / `commissioning` / `completed`. |
| `construction_start` | date | When construction began. |
| `target_completion` | date | The planned completion / commissioning date. |
| `actual_completion` | date | The date the asset reached operational status; null while in progress. |
| `total_development_cost` | decimal | The budgeted all-in development cost. |
| `cost_incurred_to_date` | decimal | Development cost incurred so far — the basis for a cost-approach valuation while pre-operational. |
| `contractor_entity_id` | varchar (FK → E-01) | The principal construction counterparty, as a Legal Entity in the `counterparty` role. |
| `concession_grantor_id` | varchar (FK → E-01) | The public authority granting the concession, where the asset is concession-based; null otherwise. |
| `concession_start` | date | The concession commencement date. |
| `concession_end` | date | The concession expiry — the date the asset reverts to the grantor or the right ends. |
| `revenue_model` | varchar | The contracted revenue basis the operational asset will earn under — `regulated` / `availability` / `contracted` / `merchant`. |
| `currency` | char | The currency the cost amounts are expressed in. |
| `status` | varchar | `active` / `completed` / `cancelled`. |

## Notes

- `development_type` is the risk discriminator: a `greenfield` project carries planning, construction and demand risk that a `brownfield` extension or a `refurbishment` does not. The valuation method follows the phase — a pre-operational asset is valued on a cost or residual basis (RA-05), not an income basis, because it has no operating record yet.
- The concession fields persist after `actual_completion` — a concession-based asset is operational *within* its concession term, and `concession_end` is a hard input to its valuation because the asset's income stops, or it reverts, at that date.
- When `project_phase` reaches `completed` and `actual_completion` is set, the asset's `lifecycle_stage` on RA-01 moves to `operational` and operating records (RA-02) begin.

## Out of scope

- The asset being developed — that is RA-01 Direct Real Asset, referenced through `real_asset_id`; RA-04 is the development lifecycle, not the asset.
- The operating data of the completed asset — that is RA-02 Asset Operating Record, which begins once `project_phase` reaches `completed` and the asset turns operational.
- The valuation of a pre-operational asset — that is RA-05 Asset Appraisal on a cost or residual basis; RA-04 supplies cost-to-date and concession term as inputs, it is not the appraisal.
- The concession modelled as its own first-class entity, and the construction-milestone sub-entity — both named as open extensions.

## Owned and consumed by

- **Owned by:** SD-04.11 Development & Construction Management.
- **Populated via:** SD-04.6 Deal Execution & Legal Closing (the concession and construction contracts are captured at closing).
- **Consumed by:** SD-08.3 Private-Asset Valuation (cost-to-date and concession term are valuation inputs), SD-04.11 Development & Construction Management (construction risk), SD-09.7 Private-Markets Cash-Flow Forecasting, SD-05.2 Portfolio Management & Monitoring.

## Open extensions

- The construction-milestone sub-entity — the drawdown and completion milestones a development is monitored against.
- The concession modelled as its own first-class entity where one investor holds several concession assets under related agreements.
- Hand-back and residual-value modelling at concession expiry.
