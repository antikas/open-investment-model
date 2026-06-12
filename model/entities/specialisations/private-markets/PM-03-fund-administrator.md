# PM-03 — Fund Administrator

A fund administrator, and the operational metadata of dealing with one. A **counterparty master**, not a lookup table.

**Specialises:** E-01 Legal Entity, in the `administrator` role. PM-03 adds the operational structure the data relationship needs — delivery method, data-quality tier, known quirks.

## Why it is a counterparty master, not a lookup

An institutional investor of any scale deals with twenty to thirty or more administrators across its funds, at widely varying operational maturity. They differ in reporting format, delivery mechanism, data quality and timeliness. Normalising data across a mixed-maturity administrator population is one of the hard infrastructure problems of investment operations — one administrator may offer a direct data-warehouse share while another still emails PDFs. The master carries enough about each administrator for the ingestion layer to handle its data correctly.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `admin_id` | varchar | **Golden key** (also the `entity_id` of the Legal Entity in the administrator role). |
| `admin_name` | varchar | Canonical name. |
| `delivery_method` | varchar | How this administrator delivers data: `data_share` / `api` / `sftp` / `pdf_only`. Drives which ingestion path the platform applies. |
| `data_quality_tier` | varchar | `high` / `medium` / `low` — an operational assessment based on experience. |
| `funds_administered` | int | Count of the investor's funds this administrator services. |
| `primary_contact` | varchar | The relationship contact. |
| `notes` | varchar | Known quirks — format issues, recurring data problems, reporting-lag patterns. |

## Resolution and maintenance

Administrators are a small, stable, proactively-onboarded population — resolution is largely trivial. The substantive work is **maintenance**: keeping `delivery_method`, `data_quality_tier` and `notes` current as experience accumulates, because the ingestion layer depends on them.

## Out of scope

- The generic party master an administrator specialises — that is E-01 Legal Entity in the `administrator` role; PM-03 adds only the operational structure the data relationship needs.
- The manager that runs the fund — that is PM-02 GP / Management Company; the administrator is a distinct service-provider role.
- The funds an administrator services — those are PM-01 Fund & Vehicle, which references the administrator through `administrator_id`.
- The SLA / service-level oversight relationship — held with SD-17.8 Vendor, Outsourcing & Service-Provider Oversight; an SLA sub-structure is an open extension, not part of this entity.

## Owned and consumed by

- **Owned by:** SD-13.2 Entity & Counterparty Master.
- **Maintained with:** SD-17.8 Vendor, Outsourcing & Service-Provider Oversight.
- **Consumed by:** SD-12.9 Fund Accounting & NAV, SD-12.10 Reconciliation, SD-13.6 GP & Manager Report Ingestion, SD-13.4 Market & Reference Data Management.

## Open extensions

- An SLA / service-level sub-structure for the SD-17.8 oversight relationship.
- A delivery-channel history — when an administrator's `delivery_method` changes.
