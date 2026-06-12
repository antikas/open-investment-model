# BD-08 — Valuation & Pricing

**Office:** Middle.

**Maturity:** Provisional · 6 Service Domains across security pricing, independent / model valuation, private-asset valuation, fair-value governance

The valuation capability — the middle-office function that determines what the firm's positions are worth. Every position the firm holds carries a value, and that value flows into the NAV, the performance numbers, the risk measures, the fee calculation and the financial statements. BD-08 is the capability that produces and governs that value. It sources observable prices, models values where no price exists, values private assets, governs the valuation policy, applies the adjustments that move a raw mark to a prudent one, and independently verifies the result. It sits between the front office that trades and the back office that strikes the official NAV (SD-12.9) from BD-08's marks.

Each Service Domain below is its own file.

## Service Domains

| ID | Service Domain | Applies | What it does |
|---|---|---|---|
| SD-08.1 | [Security Pricing](SD-08.1-security-pricing.md) | PUB | Sources, validates and applies a market price for every instrument that has one — quoted or vendor-evaluated. |
| SD-08.2 | [Independent / Mark-to-Model Valuation](SD-08.2-independent-mark-to-model-valuation.md) | BOTH | Models a value for instruments with no usable market price — curves, volatility surfaces, derivative and structured-product pricing. |
| SD-08.3 | [Private-Asset Valuation](SD-08.3-private-asset-valuation.md) | PRIV | Determines and reviews the fair value of private equity, private credit, real-asset and infrastructure holdings. |
| SD-08.4 | [Fair-Value Governance](SD-08.4-fair-value-governance.md) | BOTH | Governs the valuation policy and the fair-value-hierarchy classification, and adjudicates contested marks. |
| SD-08.5 | [Valuation Adjustments & Reserves](SD-08.5-valuation-adjustments-and-reserves.md) | BOTH | Calculates XVA, bid-offer, model-uncertainty, liquidity and prudent-valuation adjustments. |
| SD-08.6 | [Independent Price Verification & Price Challenge](SD-08.6-independent-price-verification-and-price-challenge.md) | BOTH | Independently verifies the firm's prices and marks against external sources and runs the challenge of contested marks. |

## A price the firm sources vs a value the firm models

The line that runs through BD-08: **SD-08.1 produces a price the firm *sources and validates*** — it selects, from the prices the outside world supplies, the one the firm will use, and proves it fit. **SD-08.2 produces a value the firm *models itself*** — it builds the price from cash flows, curves and option models because no usable external price exists. **SD-08.3 is the third case** — a private asset valued on a periodic estimate of what it would fetch, neither continuously priced nor model-derived from market data. The three are one capability — putting a value on a holding — split by *where the value comes from*, not by asset class.

## Owns the value, not always the production

BD-08 owns the firm's *valuation*, but a firm may not *produce* every mark itself. An asset manager or fund routinely delegates valuation production to its fund administrator or a valuation agent — the administrator strikes the marks and SD-12.9 the NAV. What is never delegable is the valuation *policy and oversight*: SEC Rule 2a-5 makes the fund board's "valuation designee" accountable for oversight of any delegate; AIFMD Article 19 requires the valuation function to be independent and leaves the AIFM responsible.

So BD-08's Service Domains are *active* at every firm — but at a firm that delegates production, SD-08.1 / SD-08.2 / SD-08.3 are exercised as oversight of the administrator's output, while SD-08.4 (policy and committee) and SD-08.6 (independent verification) are exercised in full and in-house. The model is the union; what an implementation produces in-house versus oversees in a delegate is the subset — an implementation choice, not a model split.

## Archetype activation

BD-08 is active for every archetype — nothing the firm holds escapes valuation — but the *shape* of the function varies by who produces the marks and what is held.

| Archetype | BD-08 | What differs |
|---|---|---|
| Third-party asset manager | Full | Valuation production often delegated to the fund administrator; the firm runs the policy (SD-08.4), the committee and independent price verification (SD-08.6). SD-08.3 active only for an alternatives manager. |
| Hedge fund | Full | A daily independent valuation function — heavy SD-08.2 (OTC and structured marks) and SD-08.6 (IPV against counterparties and consensus pricing); the administrator strikes the official NAV. |
| Private-markets manager (PE / private credit / real assets) | Full | SD-08.3 is the centre of gravity — a quarterly valuation cycle, GP-mark production or review, third-party appraisers; SD-08.1 / SD-08.2 thin. |
| Asset owner (pension / SWF / endowment) | Full | Values a multi-asset book — public marks plus a private-markets sleeve reviewed via SD-08.3; consumes more than it produces, with custodian and GP valuations as inputs. |
| Insurer | Full | Valuation feeds both the fair-value view and the regulatory (Solvency II) balance sheet; the *carrying* basis is an accounting determination downstream — see non-overlap. |
| Index / passive manager | Partial | A thin function — almost entirely SD-08.1 observable pricing; SD-08.2 / SD-08.3 dormant. |
| Wealth manager / private bank | Partial | Mostly SD-08.1 on liquid client holdings; SD-08.3 where clients hold private assets. |

The common core, true of every archetype: **every firm must put a defensible, independently-verified value on every position, govern how that value is reached, and stand behind it to auditors and investors — whether it produces the marks itself or oversees a delegate that does.**

**Why the manager-archetype row is split into sub-archetypes.** The discriminator the sub-archetype rows divide on in BD-08 is the **dominant valuation method** — the manager-archetype row is sub-typed because the SD that carries the most weight (SD-08.1 observable-price, SD-08.2 mark-to-model, SD-08.3 manager-mark / appraisal, SD-12.9-feed operated-fund NAV) is what differentiates a BD-08 implementation. A third-party asset manager's centre of gravity is SD-08.1 / SD-08.6 oversight of administrator output; a hedge fund's is SD-08.2 model-and-IPV-heavy daily independent valuation; a private-markets manager's is SD-08.3 quarterly cycle with GP-mark production or review and third-party appraisers; an index / passive manager's is almost entirely SD-08.1. The valuation-method discriminator is what the sub-typing makes visible; collapsing it would assert one valuation shape across managers that the regulatory frame (SEC Rule 2a-5, AIFMD Article 19) does not contemplate.

## Wider-source grounding

Grounded against external industry references:

- **IFRS 13 / ASC 820** fair-value measurement and the three-level fair-value hierarchy — the accounting standards that define "fair value" and the Level 1 / 2 / 3 classification.
- **SEC Rule 2a-5** (the 2020 fund-valuation rule and the "valuation designee") and **AIFMD Article 19** — the regulatory valuation regimes; the source of the owns-versus-produces distinction.
- The **IPEV Valuation Guidelines** and **IVS** / the RICS Red Book — the private-asset and real-asset methodology standards.
- The **multi-curve / OIS-discounting** framework and the LIBOR-to-risk-free-rate transition; ISDA definitions and option-pricing theory for the derivative-valuation layer.
- The **XVA** literature and the EU **prudent-valuation** regime (CRR Article 105, the EBA additional-value-adjustment RTS).
- The Basel Committee's treatment of **independent price verification** as a key valuation control.
- The institution-archetype panel and the public / private / delegated-production divide.

## Non-overlap — where the boundaries run

- **BD-08 vs SD-13.4 Market & Reference Data Management.** SD-13.4 delivers raw market data — the feeds, the curves, the reference prices — as a data-management capability. BD-08 turns that data into a governed *valuation* of the firm's actual holdings. SD-13.4 owns Price & Market Data (E-08); BD-08 owns Valuation (E-07). A raw vendor price is SD-13.4's; the firm's chosen, validated price for a position it holds is SD-08.1's.
- **BD-08 vs SD-12.9 Fund Accounting & NAV.** BD-08 values the *holdings* — it produces the per-instrument marks. SD-12.9 strikes the *NAV* — it takes BD-08's marks, adds accruals, fees, expenses and the rest of the fund balance sheet, and produces the official net asset value per share or unit. A BD-08-governed, independently-verified set of marks is a precondition of a struck NAV.
- **BD-08 vs BD-07 Investment Risk.** BD-08 produces the value; BD-07 measures the risk in that value. They share the curve and market-data inputs but answer different questions — *what is it worth* versus *how much can it move*.
- **The insurer's dual basis.** BD-08 produces a fair value for every holding. Whether the *carrying* value on the insurer's balance sheet is that fair value or an amortised-cost / book-value figure is an accounting-policy determination — IFRS 9 classification, statutory accounting — made in the BD-12 accounting domains, not in BD-08. BD-08 always produces fair value; the accounting domain decides what basis is carried.
- **Valuation model governance versus the model itself.** SD-08.2 builds, calibrates and uses the valuation models. The enterprise model inventory and the independent model validation are **SD-14.4 Model Governance & AI Governance**. SD-08.2's models are *in* the SD-14.4 inventory; SD-08.2 does not own their independent validation.

## Design notes

- **SD-08.1 covers evaluated pricing.** Most of the fixed-income universe trades but not continuously, and is priced by vendor evaluated (matrix) pricing — a sourced-and-validated price, not a modelled one. The SD-08.1 / SD-08.2 line is "a price the firm sources" versus "a value the firm models", not "equities versus everything else".
- **SD-08.2 names the quantitative valuation layer** — multi-curve construction, OIS / risk-free-rate discounting, volatility-surface calibration and structured-product valuation — the post-2008 quantitative-valuation reality.
- **Naming follows capability.** SD-08.6 carries Independent Price Verification (IPV) as the recognised industry and regulatory term. SD-08.4 names the Fair-Value Governance capability, not the committee that exercises it; it owns valuation policy, fair-value-level classification and contested-mark adjudication.
- **The owns-versus-produces distinction.** BD-08's Service Domains are active at every firm, but at a firm that delegates valuation production to an administrator they are exercised as oversight. This is captured in the README framing above, not by tagging Service Domains — production-versus-oversight is an implementation choice, not a model split.
- **No new entities.** BD-08 owns Valuation (E-07) and consumes the market-data and instrument entities.
- **Panel-substitution rationale — asset-owner collapse.** The single "Asset owner (pension / SWF / endowment)" row collapses DBP and SWF-E — BD-08's discriminating axis is **production-versus-oversight of the mark**, not the asset-owner sub-archetype. A DB pension, a SWF and an endowment value a multi-asset book on the same pattern — public marks from custodians, a private-markets sleeve reviewed via SD-08.3, and oversight of the production performed by administrators and GPs. The Insurer keeps its own row (Solvency II regulatory balance-sheet feed, accounting-basis integration) — it is not included in the collapse.

## How BD-08 relates to the rest of the model

- **Consumes** the market-data and instrument entities — Price & Market Data (E-08, owned by SD-13.4), Instrument / Asset (E-02), Holding / Position (E-04, `book = ibor` — BD-08 values the live holdings), Portfolio / Mandate (E-03) — and, for private assets, Fund Investment (PM-09) and LP Commitment (PM-06). SD-08.4 / SD-08.5 / SD-08.6 also consume E-07 Valuation across any `method` (governance, adjustments and IPV cut across the observable-price, mark-to-model and manager-mark / appraisal producers).
- **Owns** Valuation (E-07): SD-08.1 owns the observable-price valuations, SD-08.2 the mark-to-model valuations, SD-08.3 the manager-mark and appraisal valuations, SD-08.5 the adjustment and reserve components; SD-08.4 governs E-07 through the valuation policy and the fair-value-level classification. SD-08.6 owns no entity — it is a control that verifies E-07. SD-08.3's `manager_mark` valuations and SD-12.9 Fund Accounting & NAV's operated-fund NAV share the `manager_mark` method value but are co-equal owners distinguished by producing capability — SD-08.3 records the mark the institution *consumes* as an investor in an externally-managed interest, where SD-12.9 strikes the NAV of a vehicle the institution *operates* — a distinction the model carries in prose rather than as a separate method value (the same shape as E-04's `book`).
- **Feeds** SD-12.9 Fund Accounting & NAV (the marks the NAV is struck from), SD-12.2 ABOR (the accounting book), BD-07 Investment Risk and BD-09 Performance & Analytics (which both consume valuations), the fee calculation, and the fair-value disclosures in the BD-13 reporting.
