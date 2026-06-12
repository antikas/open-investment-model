# RA-03 — Lease / Tenancy

A lease over a real-estate asset (RA-01) — the contract between the investor as landlord and a tenant that produces the asset's income. One record per lease; the set of leases over an asset is its tenancy schedule.

## Purpose

For a real-estate asset, the leases *are* the income. The value of a let building is the value of its tenancy schedule — the contracted rent, its duration, its review pattern, the credit of the tenants. An appraisal (RA-05) of a commercial property reads the leases directly; the operating record's (RA-02) gross income is the sum of the rent the leases produce. Modelling the lease explicitly is what lets the income be traced to its contractual source rather than asserted as a number.

The lease is the real-estate analogue of the private-markets pack's Fund Terms (PM-10): a contract whose economic content — rent, escalation, reviews, breaks — drives the asset's cash flow and must be held as queryable data, not buried in a document.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `lease_id` | varchar | Primary key. |
| `real_asset_id` | varchar (FK → RA-01) | The asset the lease is over. |
| `tenant_entity_id` | varchar (FK → E-01) | The tenant, as a Legal Entity in the `counterparty` / tenant role. |
| `demised_area` | decimal | The area let under the lease, in the asset's `size_unit`. |
| `lease_start` | date | The lease commencement date. |
| `lease_expiry` | date | The contractual expiry date. |
| `break_date` | date | The earliest tenant or landlord break date, where the lease has a break option; null otherwise. |
| `passing_rent` | decimal | The current contractual rent payable under the lease. |
| `currency` | char | The currency the rent is expressed in. |
| `rent_review_basis` | varchar | How the rent changes at review — `open_market` / `indexed` / `fixed_uplift` / `turnover` / `none`. |
| `next_review_date` | date | The date of the next rent review. |
| `lease_type` | varchar | The repairing-and-insuring basis — `FRI` (full repairing and insuring) / `gross` / `net` / `ground_lease`. |
| `tenant_covenant` | varchar | An indicator of the tenant's credit strength — the covenant the income rests on. |
| `lease_status` | varchar | `active` / `holding_over` / `expired` / `surrendered`. |
| `source` | varchar | The source document the lease was abstracted from. |

## Notes

- The tenancy schedule of an asset yields the **weighted-average unexpired lease term (WALT)** — the duration of contracted income, a primary value driver computed by weighting `lease_expiry` (or `break_date`) by `passing_rent` across the asset's leases. WALT is derived, not stored: it is a property of the lease set.
- `rent_review_basis` and `next_review_date` carry the reversionary potential — the gap between passing rent and open-market rent that an appraisal capitalises into a reversionary value.
- A lease is the income side of a real-estate asset; an infrastructure asset's income is contractual in a different form — a concession or an offtake agreement — carried on RA-04 and RA-02 rather than here. RA-03 is real-estate-specific.

## Out of scope

- The asset the lease is over — that is RA-01 Direct Real Asset, referenced through `real_asset_id`.
- The realised period income a tenancy schedule produces — that is RA-02 Asset Operating Record; RA-03 is the contractual source, RA-02 the observed result.
- An infrastructure asset's contracted income — a concession or offtake agreement — that is RA-04 Development Project and RA-02; RA-03 is real-estate-specific.
- The settled rent-review history as an event sub-entity — named as an open extension; the entity carries `passing_rent` and the next-review attributes only.

## Owned and consumed by

- **Owned by:** SD-04.10 Direct Real-Asset Management — the lease-as-data entity *is* the economic content of the lease (rent, reviews, breaks, tenancy status), and SD-04.10 is the function that sets and maintains that content: letting, lease renewals, rent reviews and tenant management are write operations on this record. The authoritative source for a data entity is the function that authors its substance, and the lease's substance is exactly these economic terms. SD-14.9 holds the executed document — legal custody, a thinner relation, recorded as a consume below — but it does not author the rent, the review pattern or the break terms. The shape echoes the private-markets pack's Fund Terms (PM-10): the economic terms held as queryable data, the executed document held by the legal function as a document source rather than as the term authority.
- **Populated via:** SD-13.11 Document & Content Management (the lease is abstracted from the executed document).
- **Consumed by:** SD-14.9 Legal & Contract Management (legal custody of the executed lease as a document, and the contractual-obligation register over it — the legal-document relation, not authorship of the economic terms), SD-08.3 Private-Asset Valuation (the tenancy schedule is the income-approach input for real estate), SD-07.2 Credit & Counterparty Risk Management (tenant covenant), SD-09.7 Private-Markets Cash-Flow Forecasting.

## Open extensions

- The rent-review event sub-entity — the history of settled reviews, so passing rent is traceable through its review chain.
- Lease incentives — rent-free periods, capital contributions, fit-out — modelled as data alongside the headline rent.
- Service-charge and recoverable-expense modelling, linking the lease to the operating record's expense lines.
