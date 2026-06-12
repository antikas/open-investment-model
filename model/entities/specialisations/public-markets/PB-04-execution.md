# PB-04 — Execution

A fill — a quantity of an order traded in the market at a price, on a venue, at a time. The event that actually moves a position.

**Specialises:** E-05 Transaction (`transaction_type = trade`). Where PB-03 Order is the *intent*, PB-04 Execution is the *event* — the realised trade against that intent. An order may produce one execution or many; each is an immutable fact. It corresponds to the FIX *Execution Report* (MsgType 8) with an execution status of a fill or partial fill.

## Purpose

An order is worked in the market and comes back as fills. A large order rarely fills in one print — it is split across venues, brokers and time, each slice a separate execution at its own price. PB-04 is the record of one such fill. It is the entity from which the realised position change, the executed price for valuation and performance, and the transaction-cost measurement all derive. Keeping executions separate from the order is what makes partial fills, multi-venue working and a true volume-weighted average execution price representable — and it is the evidence base for best-execution analysis (SD-06.4): the comparison is the execution prices against the order's arrival-price intent.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `execution_id` | varchar | Primary key. |
| `order_id` | varchar (FK → PB-03) | The order this execution fills. |
| `instrument_id` | varchar (FK → E-02) | The instrument traded. |
| `side` | varchar | `buy` / `sell` / `sell_short` / `buy_to_cover` — inherited from the order. |
| `executed_quantity` | decimal | The quantity filled in this execution. |
| `executed_price` | decimal | The price of this fill, in the trading currency. |
| `execution_datetime` | timestamp | The timestamp of the fill. |
| `execution_venue` | varchar | ISO 10383 MIC of the venue the fill occurred on. |
| `broker_entity_id` | varchar (FK → E-01) | The executing broker / counterparty, as a Legal Entity in the `counterparty` role. |
| `trade_date` | date | The date of the trade. |
| `settlement_date` | date | The contractual settlement date — trade date plus the market's settlement cycle (e.g. T+1). |
| `gross_amount` | decimal | Quantity × price, before costs. |
| `commission` | decimal | Broker commission charged on this fill. |
| `taxes_and_fees` | decimal | Stamp duty, transaction taxes, exchange and regulatory fees. |
| `net_amount` | decimal | The cash consideration after commission, taxes and fees — the basis of the Cash Flow Event (E-06). |
| `accrued_interest` | decimal | For a debt instrument — accrued interest paid to / received from the seller; null for equity. |
| `execution_capacity` | varchar | `agency` / `principal` / `riskless_principal` — the broker's capacity in the fill. |
| `last_liquidity_indicator` | varchar | `added` / `removed` — whether the fill posted or took liquidity, where the venue reports it. |

## Notes

- An execution is an **immutable event** — a fill that happened is a fact. A correction (a trade bust, a price amendment) is a new offsetting record, not an edit, consistent with the core E-05 rule.
- The execution's `net_amount` is the consideration that flows to settlement; the cash leg is recorded as a Cash Flow Event (E-06) and the securities leg drives the position change in IBOR (E-04).
- For a debt instrument the dirty (settlement) amount is `gross_amount + accrued_interest ± costs`; carrying `accrued_interest` explicitly keeps clean and dirty price separable for fixed-income performance.
- An execution belongs to exactly one order; it does not reference a portfolio directly — the portfolio attribution is the job of PB-05 Allocation, because a block execution may be split across many accounts.

## Out of scope

- The instruction the fill is worked against — that is PB-03 Order; PB-04 is the realised event, PB-03 is the intent.
- The apportionment of a fill across portfolios — that is PB-05 Allocation; an execution is portfolio-agnostic by construction and does not reference a portfolio directly.
- The settlement of the trade — that is PB-06 Settlement Instruction; PB-04 is the market event, settlement happens days later through different infrastructure.
- The cash leg of the fill — that is a core E-06 Cash Flow Event; PB-04 carries `net_amount` as its basis, not the cash record itself.

## Owned and consumed by

- **Owned by:** SD-06.2 Trade Execution.
- **Consumed by:** SD-06.4 Best Execution & Transaction Cost Analysis, SD-06.5 Trade Allocation, SD-12.3 Trade Confirmation & Matching, SD-12.1 Investment Book of Record (IBOR), SD-08.1 Security Pricing, SD-09.1 Performance Measurement.

## Open extensions

- The relationship between an execution and its Cash Flow Events (E-06) made explicit — the cash and securities legs.
- Venue-level execution-quality fields feeding a fuller TCA model.
- The trade-bust / amendment correction chain as an explicit sub-model.
