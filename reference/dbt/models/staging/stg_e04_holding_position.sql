-- stg_e04_holding_position — E-04 Holding / Position (model/entities/core/E-04-holding-position.md).
--
-- What the investor owns, at two books of record. A 1:1 typed staging view over
-- raw_e04_holding_position, column-faithful to the model file's Attribute schema.
--
-- KEY-PARTITIONED BY `book` (ADR-0022): every row is a position in a named book —
-- SD-12.1 IBOR owns `book = ibor`, SD-12.2 ABOR owns `book = abor`, co-equally.
-- `book` is part of identity, so (position_id, book) is the natural composite
-- grain (the seed carries IBOR/ABOR pairs that genuinely diverge — see the two
-- market_value_usd numbers for POS-0005/0006). The dbt tests assert the
-- composite (position_id, book) uniqueness, not position_id alone.
--
-- Parity-aware SQL: `decimal(18,2)` for the money/quantity columns (NOT duckdb's
-- `double`, a duckdb-only idiom the postgres prod target can't render).
-- `decimal`/`numeric` render on both backends. `varchar`/`date` casts are
-- portable. No duckdb-only
-- idiom remains in this model.

with source as (
    select * from {{ ref('raw_e04_holding_position') }}
)

select
    cast(position_id        as varchar)       as position_id,
    cast(book               as varchar)       as book,
    cast(portfolio_id       as varchar)       as portfolio_id,
    cast(instrument_id      as varchar)       as instrument_id,
    cast(as_of_date         as date)          as as_of_date,
    cast(quantity           as decimal(28, 8)) as quantity,
    cast(commitment_usd     as decimal(18, 2)) as commitment_usd,
    cast(cost_basis_usd     as decimal(18, 2)) as cost_basis_usd,
    cast(market_value_usd   as decimal(18, 2)) as market_value_usd,
    cast(currency           as varchar)       as currency,
    cast(accrued_income_usd as decimal(18, 2)) as accrued_income_usd
from source
