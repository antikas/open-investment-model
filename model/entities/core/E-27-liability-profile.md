# E-27 — Liability Profile

The actuarially-projected stream of future benefit or claim payments a liability-relative strategy is built against — the projected cash flows and their sensitivity to interest rates and inflation. The subject a liability-driven or insurance strategy targets, made first-class.

## Purpose

A defined-benefit pension scheme and an insurer do not invest against a return target alone — they invest against a **stream of future liabilities**: the benefits a scheme must pay its members, the claims an insurer must meet. The investment strategy hedges and funds that stream, and to do so it must represent it: the projected cash flows year by year, and how their present value moves with interest rates and inflation. The Liability Profile is that representation — the projected benefit / claim cash-flow stream with its rate and inflation sensitivities and its valuation basis.

The liability is to a liability-driven strategy what the benchmark is to an asset-only allocation: the thing the whole strategy is measured and built against. Yet the model carried no representation of it — the actual cash entity (E-06 Cash Flow Event) records realised, dated movements, not a forward projection. The Liability Profile fills that gap. It is the *subject* of the strategy, ingested from the scheme actuary's or the insurer's projection and consumed by the strategy that targets it.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `liability_profile_id` | varchar | Primary key. |
| `subject_type` | varchar | What the liability is for — `pension_scheme` / `insurance_book` / `mandate` (E-03). |
| `subject_id` | varchar | The identifier of the scheme, book or mandate. |
| `as_of_date` | date | The date the projection is *as of*. |
| `projection_basis` | varchar | The basis the cash flows are projected on — `funding` / `accounting` / `solvency` / `best_estimate`. |
| `cash_flows` | document (JSON) | The projected stream — the projected benefit or claim amount per future period. |
| `pv01` | decimal | The present-value sensitivity to a one-basis-point parallel shift in interest rates. |
| `key_rate_durations` | document (JSON) | The sensitivity decomposed across the key points of the rate curve. |
| `inflation_sensitivity` | decimal | The sensitivity of the present value to a change in the inflation assumption. |
| `discount_curve_ref` | varchar | The discount curve the present value is computed on. |
| `present_value` | decimal | The present value of the projected liabilities on the stated basis. |
| `currency` | char | The currency the liabilities are denominated in. |
| `actuary_source` | varchar | The actuary or actuarial function the projection came from. |
| `version` | varchar | The version of the projection; a re-projection is a new version. |

## Notes

- **Versioned, append-by-version.** A liability is re-projected periodically — as members age, as assumptions are updated, as experience emerges. Each re-projection is a new version; the prior is retained, so a strategy decision stays traceable to the liability profile in force when it was taken.
- The cash flows are a *projection*, not realised movements — this is the distinction from E-06 Cash Flow Event, which records actual dated cash. The Liability Profile is forward-looking and aggregate; E-06 is realised and transactional.
- The sensitivities (`pv01`, `key_rate_durations`, `inflation_sensitivity`) are what a liability-driven strategy hedges against — the hedge portfolio is constructed to match them, and the glidepath is run relative to the funding position they imply.

## Out of scope

- The realised, dated cash movements a scheme actually pays or receives — those are E-06 Cash Flow Events; the Liability Profile is the *projection* of future benefits, not the realised cash.
- The hedging strategy and glidepath built against the liability — those remain analytical artefacts of the strategy Service Domains; E-27 is the liability the strategy targets, not the strategy itself.
- The capital-market assumptions the projection's discounting relies on — those are inputs administered elsewhere in the strategy domain; E-27 references the discount curve, it does not own the assumption set.

## Owned and consumed by

- **Owned by:** co-owned by **SD-01.7 Liability-Driven & Cash-Flow-Driven Strategy** and **SD-01.8 Insurance Investment Strategy** — a single concept with two co-equal owners, the pension-scheme view and the insurance-book view of the same kind of liability stream. The full pattern is documented in [`ownership-map.md`](../../ownership-map.md).
- **Consumed by:** SD-01.4 Strategic Asset Allocation (liability-relative allocation), SD-05.6 Liquidity-Aware Portfolio Management, SD-07.1 Market Risk Management (rate and inflation risk relative to the liability), SD-16.2 Owner & Investor Reporting.

## Open extensions

- The cash-flow document grammar — the typed structure of the projected stream per projection basis.
- The funding-level model — the relationship between the Liability Profile and the asset value that funds it, and the glidepath triggers it drives.
- The relationship between a liability re-projection and the strategy decisions taken under the prior version.
