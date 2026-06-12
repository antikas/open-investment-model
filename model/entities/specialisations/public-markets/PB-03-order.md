# PB-03 — Order

An instruction to buy or sell a listed instrument — the first event of the trade lifecycle, raised by the investment decision and routed to the trading desk and the market.

**Specialises:** E-05 Transaction (`transaction_type = trade`). The core Transaction names the trade as an event; PB-03 is the lifecycle expansion of its order stage. An Order is *intent*; it is not yet a position change — only an Execution (PB-04) against it moves a holding. It corresponds to the FIX *New Order – Single* (MsgType D) message and its order-state reports.

## Purpose

A market trade is not one event but a chain: an order is raised, routed, worked, filled in one or more executions, allocated across accounts, confirmed and settled. The core E-05 Transaction is too coarse to carry that chain, so the public-markets pack expands it. PB-03 is the head of the chain — the parent record that the executions, allocations and settlement instructions all trace back to. Keeping the order distinct from its fills matters because an order can be partially filled, amended or cancelled, and best-execution evidence (SD-06.4) is the comparison of the order's intent against the executions that resulted.

## Attribute schema

| Column | Type | Definition |
|---|---|---|
| `order_id` | varchar | Primary key. The OpenIM identifier for the order. |
| `transaction_id` | varchar (FK → E-05) | The core Transaction this order belongs to. |
| `parent_order_id` | varchar (FK → self) | The parent, where a block order is split into child orders; null for a top-level order. |
| `instrument_id` | varchar (FK → E-02) | The instrument ordered — a PB-01 listed equity or PB-02 debt instrument. |
| `portfolio_id` | varchar (FK → E-03) | The originating portfolio or mandate; null where the order is a block to be allocated post-trade. |
| `side` | varchar | `buy` / `sell` / `sell_short` / `buy_to_cover`. |
| `order_type` | varchar | `market` / `limit` / `stop` / `stop_limit` / `pegged` / `vwap` / `twap`. |
| `order_quantity` | decimal | The quantity instructed. |
| `limit_price` | decimal | The price constraint for a limit / stop-limit order; null for a market order. |
| `time_in_force` | varchar | `day` / `gtc` / `ioc` / `fok` / `gtd` / `at_open` / `at_close`. |
| `order_datetime` | timestamp | When the order was raised. |
| `broker_entity_id` | varchar (FK → E-01) | The executing broker, as a Legal Entity in the `counterparty` role; null for direct-market-access orders. |
| `execution_venue` | varchar | The intended venue or routing destination (ISO 10383 MIC), where specified. |
| `order_status` | varchar | `new` / `routed` / `partially_filled` / `filled` / `cancelled` / `rejected` / `expired`. |
| `filled_quantity` | decimal | Cumulative quantity executed across all PB-04 executions against this order. |
| `pre_trade_compliance_status` | varchar | `passed` / `failed` / `overridden` — the SD-10.1 pre-trade guideline-check outcome. |
| `source` | varchar | The order-management system the order was captured from. |

## Notes

- An order may carry **pre-trade allocation** — the accounts and quantities it is to be split across, sent on the order itself (the FIX Tag 78/79/80 repeating group). Where it does, the PB-05 Allocation rows are derivable at order time; where allocation is post-trade, they are created after the fills.
- The order is intent and is **mutable while live** — it can be amended (quantity, limit) or cancelled before it is fully filled. Once `filled` or `cancelled` it is terminal. This is the one place the lifecycle is not append-only; the executions and settlements it spawns are.
- Pre-trade compliance (SD-10.1) gates the order before it is routed; a `failed` check blocks routing unless explicitly overridden, and the override is itself an audit event.

## Out of scope

- The realised fill against an order — that is PB-04 Execution; an Order is *intent*, only an Execution moves a position.
- The apportionment of a filled trade across portfolios — that is PB-05 Allocation; PB-03 may carry pre-trade allocation instructions, but the allocation rows are PB-05.
- The settlement of the resulting trade — that is PB-06 Settlement Instruction, the final lifecycle stage.
- The generic transaction record an order belongs to — that is E-05 Transaction of `transaction_type = trade`, which PB-03 expands at its order stage.

## Owned and consumed by

- **Owned by:** SD-06.1 Order Management.
- **Consumed by:** SD-06.2 Trade Execution, SD-06.3 Execution Venue & Broker Management, SD-06.4 Best Execution & Transaction Cost Analysis, SD-10.1 Investment Guideline Monitoring, SD-12.1 Investment Book of Record (IBOR).

## Open extensions

- The order-amendment history as an event sub-model, so the full lifecycle of a mutable order is itself auditable.
- The relationship between a block order and its child orders across multiple brokers.
- The link from PB-03 to TCA benchmarks (arrival price, VWAP) for best-execution measurement.
