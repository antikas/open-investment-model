-- stg_e06_cash_flow_event — E-06 Cash Flow Event (model/entities/core/E-06-cash-flow-event.md).
--
-- A dated movement of cash between the investor and a portfolio / instrument / fund /
-- counterparty — the granular cash record performance (especially money-weighted return)
-- is computed from. A 1:1 typed staging view over raw_e06_cash_flow_event, column-faithful
-- to the model file's Attribute schema. Owned by SD-12.1 IBOR.
--
-- A cash flow is the cash *consequence* of a Transaction (E-05): the cash leg of a settled
-- trade carries the transaction_id; an income / fee flow may not. The signed, dated series
-- of cash flows for a holding or portfolio is the direct input to internal rate of return.
--
-- Parity-aware SQL: `decimal(18,2)` for amount (NOT duckdb's `double`); `varchar`/`date`/
-- `char` casts are portable. No duckdb-only idiom.

with source as (
    select * from {{ ref('raw_e06_cash_flow_event') }}
)

select
    cast(cash_flow_id    as varchar)        as cash_flow_id,
    cast(portfolio_id    as varchar)        as portfolio_id,
    cast(instrument_id   as varchar)        as instrument_id,
    cast(transaction_id  as varchar)        as transaction_id,
    cast(cash_flow_date  as date)           as cash_flow_date,
    cast(cash_flow_type  as varchar)        as cash_flow_type,
    cast(direction       as varchar)        as direction,
    cast(amount          as decimal(18, 2)) as amount,
    cast(currency        as varchar)        as currency,
    cast(source          as varchar)        as source
from source
