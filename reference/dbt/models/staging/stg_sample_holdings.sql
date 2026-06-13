-- stg_sample_holdings — a SAMPLE staging model that proves the
-- pipeline runs (seed -> staging view -> tests), nothing more.
--
-- This is a DELIBERATELY GENERIC sample, NOT a BD-09 entity. The ten BD-09
-- entities (E-01 Legal Entity, E-04 Holding/Position, E-07 Valuation, E-20
-- Performance Result, ...) are realised as the stg_eNN_* staging models, each
-- cross-checked against model/entities/E-NN-*.md. This model exists only to make
-- `dbt build` green + idempotent on the duckdb dev backend.
--
-- Shape (so the entity staging models drop in beside it without rework):
-- a 1:1 typed view over a `raw` seed, casting raw CSV text to typed columns and
-- deriving one trivial measure (market_value). Materialised as a view per the
-- staging convention (idempotent by construction — a view is a query, not
-- stored rows, so re-running never duplicates).

with source as (
    select * from {{ ref('raw_sample_holdings') }}
)

select
    cast(holding_id      as varchar)  as holding_id,
    cast(portfolio_code  as varchar)  as portfolio_code,
    cast(instrument_code as varchar)  as instrument_code,
    cast(quantity        as integer)  as quantity,
    cast(price           as double)   as price,
    cast(quantity as double) * cast(price as double) as market_value,
    cast(as_of_date      as date)     as as_of_date
from source
