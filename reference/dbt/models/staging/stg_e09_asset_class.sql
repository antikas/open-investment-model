-- stg_e09_asset_class — E-09 Asset Class (model/entities/core/E-09-asset-class.md).
--
-- The controlled asset-class -> strategy -> sub-strategy taxonomy. A 1:1 typed
-- staging view over raw_e09_asset_class, column-faithful to the model file's
-- Attribute schema. Single owner (SD-13.4). View-materialised; idempotent.
--
-- EFFECTIVE-DATED reference data: `effective_from` / `effective_to` carry the
-- taxonomy entry's validity (effective_to null while active). This is reference-
-- data effective-dating, distinct from the append-only computed-metric grain of
-- E-07/E-19/E-20.
--
-- Parity-aware SQL: `integer` for the int PK `asset_class_key`, `varchar`/`date`
-- for the rest. All portable across duckdb and postgres. No duckdb-only idiom.

with source as (
    select * from {{ ref('raw_e09_asset_class') }}
)

select
    cast(asset_class_key   as integer) as asset_class_key,
    cast(asset_class_code  as varchar) as asset_class_code,
    cast(asset_class_label as varchar) as asset_class_label,
    cast(strategy_code     as varchar) as strategy_code,
    cast(sub_strategy_code as varchar) as sub_strategy_code,
    cast(markets           as varchar) as markets,
    cast(effective_from    as date)    as effective_from,
    cast(effective_to      as date)    as effective_to
from source
