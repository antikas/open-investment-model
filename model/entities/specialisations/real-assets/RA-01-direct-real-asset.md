# RA-01 — Direct Real Asset

The golden record of a physical asset an investor holds **directly** — a building, a toll road, a wind farm, a forest — owned outright or through a joint venture / SPV, rather than through a fund.

**Specialises:** E-02 Instrument / Asset, of `instrument_class = real_asset`. A directly-held real asset is a position (E-04) in an Instrument / Asset; RA-01 is the entity that carries the physical, locational and structural detail that kind of instrument needs and that no liquid instrument has. Unlike a debt or equity instrument, a real asset has no issuer — `issuer_entity_id` on E-02 is null — and no universal market identifier; RA-01 carries the asset's own attributes instead.

## Purpose

When an investor owns a property or an infrastructure asset directly, the thing it holds is not a security with a CUSIP and a quoted price — it is a physical asset at a location, with a use, an operating profile and a lifecycle. The core Instrument / Asset entity says only that a `real_asset` instrument exists; RA-01 is where the asset *is* — its type, where it sits, what it does, how it is held. It is the anchor record the operating data (RA-02), the leases (RA-03), the development history (RA-04) and the appraisals (RA-05) all reference.

A real asset reached **through a fund** is not modelled here — that is a portfolio company (PM-04) inside a fund (PM-01) in the private-markets pack. RA-01 is strictly the asset the investor owns and controls itself.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `real_asset_id` | varchar | **Golden key.** The OpenIM-assigned canonical identifier (also the `instrument_id` of the E-02 record). |
| `asset_name` | varchar | Canonical name of the asset. |
| `asset_category` | varchar | The top-level kind — `real_estate` / `infrastructure` / `natural_resource`. |
| `asset_subtype` | varchar | The finer type — `office` / `retail` / `industrial` / `residential` / `hotel` for real estate; `transport` / `energy` / `utility` / `social` / `digital` for infrastructure; `timberland` / `farmland` / `energy` / `mining` for natural resources (the four-way natural-resource subtype matches the BD-04 prose). |
| `country` | varchar | The jurisdiction the asset sits in. |
| `location` | varchar | Address, site or coordinates — the physical location. |
| `tenure` | varchar | The legal interest held — `freehold` / `leasehold` / `concession` / `usufruct`; for a concession, RA-04 carries the term and counterparty. |
| `holding_vehicle_id` | varchar (FK → PM-05) | The legal vehicle / SPV / JV the asset is held through; null where held directly on the balance sheet. |
| `ownership_pct` | float | The investor's ownership share of the asset, where held in a joint venture; 100 where held outright. |
| `lifecycle_stage` | varchar | `development` / `operational` / `stabilised` / `divesting` / `disposed` — see RA-04 for the development detail. |
| `physical_size` | decimal | The asset's measured size in `size_unit`. |
| `size_unit` | varchar | The unit `physical_size` is expressed in — `sqm` / `sqft` for real estate, `MW` for energy, `lane_km` for a road, `hectares` for land. |
| `acquisition_date` | date | When the investor acquired the asset. |
| `currency` | char | The asset's reporting currency. |
| `external_ids` | map | Property-register, land-registry, plant or vendor identifiers (the in-record view of E-14). |
| `status` | varchar | `active` / `under_development` / `disposed`. |

## Notes

- A real asset has **no issuer and no universal identifier**. Where a listed instrument's master-data problem is normalising vendor feeds, a real asset's is identity of the physical thing itself across registers, appraisers and operators — RA-01 carries the alias and external-identifier structure for that.
- `asset_category` and `asset_subtype` drive which other RA entities apply: a `real_estate` asset typically carries Leases (RA-03); an `infrastructure` asset typically carries a concession and a development history (RA-04); both carry operating records (RA-02) and appraisals (RA-05).
- The holding structure is deliberately shared with the private-markets pack: a directly-held asset is normally held through a PM-05 Legal Vehicle of `vehicle_type = jv` or `direct`. RA-01 references PM-05 rather than re-modelling the vehicle.

## Out of scope

- The generic instrument record a real asset specialises — that is E-02 Instrument / Asset of `instrument_class = real_asset`; RA-01 carries the physical, locational and structural detail.
- A real asset reached *through a fund* — that is a portfolio company (PM-04) inside a fund (PM-01); RA-01 is strictly the asset the investor owns and controls itself.
- The asset's periodic operating data, leases, development history and appraisals — those are RA-02, RA-03, RA-04 and RA-05; RA-01 is the anchor record they all reference.
- The legal vehicle the asset is held through — that is PM-05 Legal Vehicle / SPV, referenced through `holding_vehicle_id`; RA-01 does not re-model the vehicle.

## Owned and consumed by

- **Owned by:** SD-13.1 Instrument & Security Master.
- **Populated via:** SD-04.6 Deal Execution & Legal Closing (the asset enters the book at acquisition).
- **Consumed by:** E-04 Holding / Position (the investor's position references this asset as its instrument); SD-04.10 Direct Real-Asset Management, SD-04.11 Development & Construction Management, SD-05.2 Portfolio Management & Monitoring, SD-07.4 Concentration & Exposure Risk, SD-08.3 Private-Asset Valuation, SD-09 Performance & Analytics.

## Open extensions

- The asset-component sub-structure — a real asset is often a set of components (buildings on an estate, turbines in a wind farm) with their own ages and condition.
- The relationship between RA-01 and a multi-asset portfolio held in one vehicle.
- ESG and physical-climate-risk attributes on the asset record (the data SD-13.9, the climate-risk analytics SD-07.8), now mandatory under the 2025 RICS Red Book.
