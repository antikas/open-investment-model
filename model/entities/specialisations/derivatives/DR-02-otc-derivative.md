# DR-02 — OTC Derivative

A bilaterally negotiated over-the-counter derivative — an interest-rate, cross-currency or equity swap, a forward, or an OTC option — held by an institutional investor for hedging, overlay management or as an instrument in its own right. Unlike a listed derivative, the contract is privately negotiated between two parties and its terms are bespoke.

**Specialises:** E-02 Instrument / Asset (`instrument_class = otc_derivative`). A position in an OTC derivative is a Holding (E-04) in an Instrument of that class; DR-02 is the entity that specifies the contract behind it. It aligns to FIBO's Derivatives domain for the contract semantics and adds the underlying relationship, the bespoke economic terms, and the counterparty and master-agreement relationships the core E-02 record does not carry.

## Purpose

An OTC derivative is, like a listed derivative, a holdable thing the core records thinly. But the OTC contract is *negotiated*, not standardised: there is no exchange contract code, no shared specification, no fungibility. Each OTC derivative is its own contract with its own economic terms, its own counterparty, and its own place in a master-agreement relationship. The investor needs that bespoke specification to value the position, to know who it faces, and to know which master agreement and collateral arrangement governs it.

The OTC derivative is the instrument behind most precise hedging and overlay work (SD-05.4) — an interest-rate swap to hedge duration to a specific tenor, a cross-currency swap to hedge a foreign-currency liability, an equity total-return swap to gain or hedge a specific exposure. The bespoke terms are what make OTC the right tool where a standardised listed contract does not fit; they are also what make the entity heavier than DR-01.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `instrument_id` | varchar (FK → E-02) | **Golden key.** The core Instrument / Asset record this specialises. |
| `derivative_type` | varchar | `swap` / `forward` / `option` / `swaption`. |
| `derivative_sub_type` | varchar | The product detail — `interest_rate_swap` / `cross_currency_swap` / `equity_total_return_swap` / `credit_default_swap` / `fx_forward` / `inflation_swap`, etc. |
| `underlying_type` | varchar | `interest_rate` / `fx` / `equity` / `credit` / `inflation` / `commodity`. |
| `underlying_instrument_id` | varchar (FK → E-02) | The underlying instrument, where it is a single modelled instrument; null where the underlying is a rate or index referenced through `underlying_reference`. |
| `underlying_reference` | varchar (FK → E-10) | The underlying rate, index or benchmark, where the underlying is not a single instrument. |
| `counterparty_entity_id` | varchar (FK → E-01) | The bilateral counterparty — a Legal Entity in the `counterparty` role. |
| `master_agreement_id` | varchar (FK → DR-03) | The master agreement governing this contract; null only for the rare uncovered trade. |
| `notional_amount` | decimal | The notional principal the contract's payments are computed on. |
| `notional_currency` | char | The currency of the notional. |
| `trade_date` | date | When the contract was agreed. |
| `effective_date` | date | When the contract's economic terms start to accrue. |
| `maturity_date` | date | The scheduled termination date of the contract. |
| `pay_leg` | document (JSON) | The terms of the leg the investor pays — rate or index, spread, frequency, day-count. |
| `receive_leg` | document (JSON) | The terms of the leg the investor receives. |
| `clearing_status` | varchar | `cleared` / `uncleared` — whether the contract is novated to a CCP (see DR-05) or remains bilateral. |
| `cdm_trade_ref` | varchar | Cross-reference to the contract's representation in ISDA CDM, where the implementation runs CDM. |

## Notes

- **Relationship to ISDA CDM — this is the entity where the boundary is sharpest.** ISDA CDM models the OTC derivative product, the trade in it, and the full set of lifecycle events — execution, confirmation, novation, amendment, partial termination, compression, settlement — at the transaction grain, in a machine-executable form. **OpenIM does not re-model any of that.** DR-02 is the buy-side **instrument / position record** that references CDM (`cdm_trade_ref`) for the authoritative product-and-trade representation and carries only the attributes the portfolio-level operating model needs above it: which counterparty, which master agreement, what notional, what maturity, cleared or not. The bespoke leg economics are held here as a `pay_leg` / `receive_leg` summary sufficient for portfolio reasoning; the *executable* product definition and the lifecycle-event history live in CDM. The rule of thumb: if a question is about the contract or a lifecycle event, it is CDM's; if it is about the position, the exposure, the counterparty relationship or the collateral, it is OpenIM's.
- An OTC derivative position is the unit at which counterparty exposure aggregates: SD-07.2 Credit & Counterparty Risk Management rolls DR-02 positions up by `counterparty_entity_id` to measure exposure to each counterparty, netted within the master-agreement set (DR-03).
- Identifier reality: an OTC derivative has **no universal identifier** — it is a bilateral contract. It carries an internal `instrument_id` golden key and, where CDM is in use, the `cdm_trade_ref`. This is closer to the private-markets no-shared-key reality than to the listed-instrument case.
- A cleared OTC derivative (`clearing_status = cleared`) has been novated so the investor faces a CCP rather than the original counterparty; the original master-agreement relationship is replaced by the clearing relationship (DR-05). The model keeps `master_agreement_id` for the pre-clearing or never-cleared case and `clearing_status` to discriminate.

## Out of scope

- The contract, the trade and the full set of lifecycle events — execution, confirmation, novation, amendment, compression, settlement — those are ISDA CDM's at the transaction grain; DR-02 references CDM through `cdm_trade_ref` and does not re-model any of it.
- An exchange-traded, standardised derivative — that is DR-01 Listed Derivative; DR-02 is the bilaterally negotiated, bespoke contract.
- The bilateral legal framework governing the contract — that is DR-03 Master Agreement & Collateral Terms, referenced through `master_agreement_id`.
- The clearing relationship a cleared OTC derivative is novated into — that is DR-05 Clearing Relationship; the `clearing_status` field discriminates.

## Owned and consumed by

- **Owned by:** SD-13.1 Instrument & Security Master.
- **Originated by:** SD-06.6 Derivatives & OTC Trade Management (the trade that brings the contract into being; CDM is referenced here for the lifecycle representation).
- **Consumed by:** SD-05.4 Overlay & Hedging Management, SD-07.1 Market Risk Management, SD-07.2 Credit & Counterparty Risk Management, SD-08.2 Independent / Mark-to-Model Valuation, SD-08.5 Valuation Adjustments & Reserves (XVA), SD-11.4 Margin & Collateral Operations.

## Open extensions

- The `pay_leg` / `receive_leg` document grammar — the typed vocabulary the leg summary is expressed in — and how it relates to the full CDM payout representation.
- The concrete CDM cross-reference contract: which CDM identifier `cdm_trade_ref` resolves, and the mapping discipline for an implementation that does not run CDM.
- The lifecycle-event relationship — how a CDM amendment, novation or partial termination flows back to the DR-02 instrument record and the position.
- The concrete FIBO Derivatives concept mapping for swaps, forwards and OTC options.
