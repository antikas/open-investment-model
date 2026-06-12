-- stg_e05_transaction — E-05 Transaction (model/entities/core/E-05-transaction.md).
--
-- The universal investment event — the trade / subscription / capital call / income
-- event from which positions (E-04) are derived and cash flows (E-06) arise. A 1:1
-- typed staging view over raw_e05_transaction, column-faithful to the model file's
-- Attribute schema. Owned by SD-12.1 IBOR (transactions update the book of record).
--
-- The trade_date / settlement_date / status carry the TD–SD timing that drives both the
-- IBOR/ABOR book divergence (a trade settling after the as-of date is in IBOR on trade
-- date but in ABOR only on settlement date) and the timing break class in the external
-- comparator feed. An in-flight buy is `status = pending` / `confirmed` with
-- settlement_date > the as-of date; the bulk are `settled`.
--
-- Parity-aware SQL: `decimal(28,8)` for quantity, `decimal(18,2)` for amount_usd (NOT
-- duckdb's `double`); `varchar`/`date` casts are portable. No duckdb-only idiom.

with source as (
    select * from {{ ref('raw_e05_transaction') }}
)

select
    cast(transaction_id        as varchar)        as transaction_id,
    cast(transaction_type      as varchar)        as transaction_type,
    cast(portfolio_id          as varchar)        as portfolio_id,
    cast(instrument_id         as varchar)        as instrument_id,
    cast(trade_date            as date)           as trade_date,
    cast(settlement_date       as date)           as settlement_date,
    cast(quantity              as decimal(28, 8)) as quantity,
    cast(amount_usd            as decimal(18, 2)) as amount_usd,
    cast(counterparty_entity_id as varchar)       as counterparty_entity_id,
    cast(status                as varchar)        as status,
    cast(source                as varchar)        as source
from source
