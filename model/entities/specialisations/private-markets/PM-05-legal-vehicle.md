# PM-05 — Legal Vehicle / SPV

The legal structure through which an investor holds a private investment — the layer between the fund investment (PM-09) and the cash flows. Cash flows are recorded at vehicle grain and aggregate up to the investment.

## Purpose

A private investment is often held through a legal vehicle — a special-purpose vehicle (SPV), a direct holding, a co-investment vehicle, a joint venture, or a separately managed account. The vehicle is where the legal ownership and the cash mechanics sit. Modelling it explicitly is what lets cash flows be recorded at the right grain and rolled up correctly; without it, deal-level cash flow cannot be reconciled to investment-level performance. SPV-within-SPV nesting is supported through the `vehicle_type` hierarchy.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `vehicle_id` | varchar | Primary key. |
| `investment_id` | varchar (FK → PM-09) | The fund investment held through this vehicle. |
| `vehicle_name` | varchar | Legal name of the vehicle. |
| `vehicle_type` | varchar | `spv` / `direct` / `co_invest` / `jv` / `sma`. |
| `jurisdiction` | varchar | The vehicle's jurisdiction of incorporation. |
| `incorporation_date` | date | When the vehicle was incorporated. |
| `lei` | varchar | Legal Entity Identifier, where one exists. |

## Out of scope

- The fund investment held through a vehicle — that is PM-09 Fund Investment; PM-05 is the legal structure the investment sits in, referenced through `investment_id`.
- The cash flows arising at vehicle grain — those are core E-06 Cash Flow Events recorded at this grain; PM-05 is the vehicle, not the cash records.
- A fund as a commitment vehicle — that is PM-01 Fund & Vehicle; PM-05 is the SPV / direct / co-invest / JV / SMA layer between the fund investment and the cash flows.
- A public-markets separately managed account portfolio — that is E-03 Portfolio / Mandate; the relationship between PM-05 and an SMA portfolio is an open cross-pack question.

## Owned and consumed by

- **Owned by:** SD-13.3 Investment Vehicle & Fund Master.
- **Consumed by:** SD-04.6 Deal Execution & Legal Closing, SD-12.1 Investment Book of Record (IBOR), SD-14.9 Legal & Contract Management; core Cash Flow Events (E-06) arising from a private investment record at this grain.

## Open extensions

- The SPV-nesting hierarchy — maximum depth and the parent-vehicle reference.
- A separately managed account is also a kind of legal vehicle; the relationship between PM-05 and a public-markets SMA portfolio (E-03) is an open cross-pack question.

## The multi-vehicle case is already backed

One fund investment held through *several* vehicles needs no extra structure. `investment_id` is a many-to-one foreign key — many PM-05 vehicle rows may reference the same PM-09 investment — so the set of vehicles an investment is held through is exactly the vehicles whose `investment_id` resolves to that investment (the inverse traversal of this column). A column on PM-09 pointing back at PM-05 would be redundant, and a single foreign key could not hold the *set* of vehicles in any case. The relationship is the existing `investment_id` edge read in the one-investment-to-many-vehicles direction.
