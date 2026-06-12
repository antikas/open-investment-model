# Real-Assets Specialisation

**Maturity:** Provisional · narrow by design — the directly-held route only; the fund route to real assets is in the private-markets pack

The entity specialisation for **real assets held directly** — real estate, infrastructure and natural-resource assets owned outright or through a joint venture / SPV, rather than through a fund.

## Why directly-held real assets need their own pack

An institutional investor reaches real assets two ways. Through a **fund** — that is the [private-markets pack](../private-markets/README.md): a real-estate or infrastructure fund is a PM-01 Fund & Vehicle, the assets inside it are PM-04 Portfolio Companies, the model already handles it. But also **directly** — owning a building, a toll road, a wind farm, a forest. This pack handles the **direct** route only; it does not re-model the fund route.

A directly-held real asset has structure neither the core nor the private-markets pack carries: a physical asset with a location, an operating profile that period-by-period drives its value, a development lifecycle for assets built rather than bought, leases for real estate, and a valuation that rests on **appraisal** rather than on a manager mark or an observable price.

## How this pack specialises the core

Every entity here either specialises a [core entity](../../core/) or carries structure that hangs off one:

- A **directly-held real asset** is an Instrument / Asset (E-02) of `instrument_class = real_asset` — with no issuer and no universal identifier. **RA-01 Direct Real Asset** carries the physical, locational and structural detail.
- Its **valuation** is a Valuation (E-07) of `method = appraisal`. **RA-05 Asset Appraisal** adds the appraisal-specific structure — the valuer, the standard, the approach, the basis of value.
- It is commonly held through a **joint venture** or an **SPV** — a PM-05 Legal Vehicle of `vehicle_type = jv` or `direct`, shared with the private-markets pack rather than re-modelled here.

What the pack adds that the core does not have: the **operating record** (the period-by-period data that drives a real asset's value), the **lease / tenancy schedule** (the contractual source of a real-estate asset's income), and the **development project** (the construction lifecycle and the concession that frames an infrastructure asset's whole life).

## Entities

| ID | Entity | Specialises | Role |
|---|---|---|---|
| RA-01 | [Direct Real Asset](RA-01-direct-real-asset.md) | E-02 Instrument / Asset (`real_asset`) | The physical asset — real estate, infrastructure or natural resource — its type, location, tenure, holding structure and lifecycle stage. |
| RA-02 | [Asset Operating Record](RA-02-asset-operating-record.md) | — | The periodic operating data — occupancy, throughput, generation, net operating income — that drives the asset's value and performance. |
| RA-03 | [Lease / Tenancy](RA-03-lease-tenancy.md) | — | A lease over a real-estate asset — the contract that produces its income; the set of leases is the tenancy schedule. |
| RA-04 | [Development Project](RA-04-development-project.md) | — | The construction / development lifecycle of an asset, and the concession that frames a concession-based infrastructure asset. |
| RA-05 | [Asset Appraisal](RA-05-asset-appraisal.md) | E-07 Valuation (`appraisal`) | An appraisal-based valuation produced by a qualified valuer to a recognised standard — the real asset's mark. |

## Scope boundary — directly-held, not the fund route

The line is worth restating, because it is the one that keeps this pack non-overlapping with private-markets. If the investor owns an interest in a *fund* that owns the building, the building is a PM-04 Portfolio Company and the investor's holding is a fund interest — private-markets territory. If the investor owns the *building itself* — on its balance sheet or through a JV / SPV it controls — the building is an RA-01 Direct Real Asset. This pack models only the second case.

## Standards this pack grounds against

- **RICS Valuation Global Standards (the Red Book)** and the **International Valuation Standards (IVS)** — the appraisal basis, the approaches and the basis-of-value vocabulary RA-05 references.
- **NCREIF** Timberland and Farmland Property Index practice — the periodic-appraisal cadence (quarterly internal, periodic independent external) RA-05 keeps distinct.
- **Infrastructure asset-management practice** — the greenfield / brownfield development lifecycle and the regulated / availability / contracted / merchant revenue taxonomy on RA-02 and RA-04.

See [PRIOR-ART.md](../../../../PRIOR-ART.md) for how the OpenIM entity model relates to FIBO, the identifier standards and the wider standards landscape.
