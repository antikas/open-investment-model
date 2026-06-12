-- stg_custodian_holdings — the custodian's position record (the external comparator feed).
--
-- A typed staging view over raw_custodian_holdings — the SYNTHETIC custodian holdings file
-- the firm's position reconciliation (SD-12.10) matches its internal book against. Derived
-- from the internal IBOR book so the MAJORITY of rows agree, with a minority carrying a
-- deliberately-injected, labelled break (`break_note` ∈ price_break / qty_break / fx_break /
-- timing_break). The labelled breaks are catalogued in break_labels.csv (the oracle) — this
-- view is the feed the engine reconciles; the manifest is the ground truth it is scored on.
--
-- This is NOT a canonical OpenIM entity — it is an external record, so it has no model file,
-- no Pydantic schema and is out of the schema-drift scope (the drift check covers stg_eNN_*
-- only). Parity-aware SQL: `decimal` for the money/quantity columns; portable casts.

with source as (
    select * from {{ ref('raw_custodian_holdings') }}
)

select
    cast(custodian_record_id as varchar)        as custodian_record_id,
    cast(custodian           as varchar)        as custodian,
    cast(position_id         as varchar)        as position_id,
    cast(portfolio_id        as varchar)        as portfolio_id,
    cast(instrument_id       as varchar)        as instrument_id,
    cast(as_of_date          as date)           as as_of_date,
    cast(quantity            as decimal(28, 8)) as quantity,
    cast(market_value_usd    as decimal(18, 2)) as market_value_usd,
    cast(currency            as varchar)        as currency,
    cast(break_note          as varchar)        as break_note
from source
