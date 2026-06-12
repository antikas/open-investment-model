# DR-01 — Listed Derivative

An exchange-traded derivative — a future or an exchange-listed option — held by an institutional investor for hedging, overlay management, cash equitisation or efficient exposure. A standardised, fungible contract traded on an organised exchange and cleared through that exchange's central counterparty.

**Specialises:** E-02 Instrument / Asset (`instrument_class = listed_derivative`). A position in a listed derivative is a Holding (E-04) in an Instrument of that class; DR-01 is the entity that specifies the contract behind it. It aligns to FIBO's Derivatives domain for the contract semantics — what a future or an exchange-traded option *is* — and adds the underlying relationship and the standardised contract terms the core E-02 record does not carry.

## Purpose

A listed derivative is a holdable thing, but the core Instrument / Asset record says only that it exists, what class it is and what currency it trades in. The investor needs the contract specification to value the position, compute its exposure and manage its lifecycle: the underlying it references, the contract multiplier that converts a quoted price to a cash value, the expiry, and — for an option — the strike and the right conferred. Because exchange-traded contracts are standardised and fungible, this specification is reference data shared by every holder of the contract, not a per-trade negotiation. DR-01 is the standardised-contract master that sits behind the position.

The listed derivative is also the instrument through which most overlay and cash-equitisation programmes are implemented (SD-05.4, SD-05.5): index futures give a portfolio equity or duration exposure without holding the underlying basket, and the contract's standardisation is what makes that cheap and liquid.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `instrument_id` | varchar (FK → E-02) | **Golden key.** The core Instrument / Asset record this specialises. |
| `derivative_type` | varchar | `future` / `option` — and, for an option, `call` or `put` carried in `option_right`. |
| `underlying_type` | varchar | The kind of underlying — `equity_index` / `single_equity` / `bond` / `interest_rate` / `commodity` / `fx` / `volatility`. |
| `underlying_instrument_id` | varchar (FK → E-02) | The underlying instrument, where it is itself a modelled instrument (a single equity, a bond); null where the underlying is an index or rate referenced through `underlying_reference`. |
| `underlying_reference` | varchar (FK → E-10) | The underlying index, benchmark or rate, where the underlying is not a single instrument — e.g. an equity index (E-10) or a reference rate. |
| `exchange_entity_id` | varchar (FK → E-01) | The exchange the contract is listed and traded on — a Legal Entity in an exchange role. |
| `ccp_entity_id` | varchar (FK → E-01) | The central counterparty that clears the contract — a Legal Entity in the `counterparty` (clearing-house) role. |
| `contract_multiplier` | decimal | The contract size — the multiplier converting a one-point price move to a cash amount. |
| `expiry_date` | date | The contract expiry / last trading date. |
| `settlement_method` | varchar | `cash` or `physical`. |
| `option_right` | varchar | `call` / `put`; null for futures. |
| `strike_price` | decimal | The exercise price; null for futures. |
| `exercise_style` | varchar | `european` / `american`; null for futures. |
| `tick_size` | decimal | The minimum price increment. |
| `exchange_symbol` | varchar | The exchange ticker / contract code. |

## Notes

- **Relationship to ISDA CDM.** A listed derivative *contract* and its lifecycle map to CDM's product and event models — CDM represents exchange-traded futures and options and their lifecycle events. DR-01 does not re-model the contract mechanics; it is the buy-side **instrument master record** the investor's position points to, holding the standardised reference data needed to value and aggregate the position. Where an OpenIM implementation runs CDM, DR-01 carries the cross-reference to the CDM product representation; where it does not, DR-01 is the self-contained contract specification. The boundary: CDM models the contract and the trade; OpenIM models the instrument-as-reference-data and the position above it.
- Listed derivatives are **centrally cleared by construction** — every exchange-traded contract clears through the exchange's CCP, so there is no bilateral master-agreement relationship (DR-03) behind a listed-derivative position. The margining relationship is the cleared path: see DR-05 Clearing Relationship and DR-04 Margin & Collateral Balance.
- Identifier reality: listed derivatives largely *have* universal identifiers — exchange contract codes, and FIGI / ISIN where assigned — so the master-data task is normalisation across vendor feeds, not the entity resolution the private-markets pack contends with.
- An option's value is non-linear in the underlying; the contract specification here is the input to mark-to-model valuation (SD-08.2) and to the delta-adjusted exposure that risk (SD-07.1) computes — the model holds the contract terms, not the greeks.

## Out of scope

- The generic instrument record a listed derivative specialises — that is E-02 Instrument / Asset of `instrument_class = listed_derivative`; DR-01 carries the underlying relationship and standardised contract terms.
- The contract mechanics and lifecycle events — those map to ISDA CDM's product and event models; DR-01 is the buy-side instrument-as-reference-data record, not the contract representation.
- A bilaterally negotiated OTC derivative — that is DR-02 OTC Derivative; DR-01 is exchange-traded and standardised only.
- The clearing relationship a listed derivative sits under — that is DR-05 Clearing Relationship; there is no bilateral master agreement (DR-03) behind a listed-derivative position.

## Owned and consumed by

- **Owned by:** SD-13.1 Instrument & Security Master.
- **Populated via:** SD-13.4 Market & Reference Data Management (exchange contract specifications arrive as reference-data feeds).
- **Consumed by:** SD-05.4 Overlay & Hedging Management, SD-05.5 Cash Equitisation & Drag Management, SD-06.6 Derivatives & OTC Trade Management, SD-07.1 Market Risk Management, SD-08.2 Independent / Mark-to-Model Valuation, SD-11.4 Margin & Collateral Operations.

## Open extensions

- The contract-series relationship — the roll from one expiry to the next, and the continuous-contract abstraction overlay programmes manage against.
- The concrete FIBO Derivatives concept mapping for exchange-traded futures and options.
- The relationship between a listed-option instrument and its underlying when the underlying is itself a derivative (options on futures).
- The CDM product-representation cross-reference attribute, made concrete once the implementation's CDM binding is specified.
