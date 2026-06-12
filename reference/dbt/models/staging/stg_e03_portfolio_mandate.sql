-- stg_e03_portfolio_mandate — E-03 Portfolio / Mandate (model/entities/core/E-03-portfolio-mandate.md).
--
-- The capital container governed by a mandate. A 1:1 typed staging view over
-- raw_e03_portfolio_mandate, column-faithful to the model file's Attribute schema.
-- Faceted ownership (SD-05.2 portfolio facet + SD-01.2 mandate facet) — both
-- facets live on this one record. View-materialised; idempotent.
--
-- Parity-aware SQL: `varchar` / `date` casts, plus `integer` for `asset_class`.
-- The model file declares `asset_class` as `int (FK -> E-09)`, matching E-09's
-- integer PK `asset_class_key`, so the asset-class join is `integer = integer`
-- (valid on postgres), not the `varchar = integer` predicate postgres rejects.
-- No duckdb-only idiom.

with source as (
    select * from {{ ref('raw_e03_portfolio_mandate') }}
)

select
    cast(portfolio_id         as varchar) as portfolio_id,
    cast(portfolio_name       as varchar) as portfolio_name,
    cast(portfolio_type       as varchar) as portfolio_type,
    cast(parent_portfolio_id  as varchar) as parent_portfolio_id,
    cast(asset_class          as integer) as asset_class,
    cast(mandate_objective    as varchar) as mandate_objective,
    cast(benchmark_id         as varchar) as benchmark_id,
    cast(base_currency        as varchar) as base_currency,
    cast(managed_by_entity_id as varchar) as managed_by_entity_id,
    cast(inception_date       as date)    as inception_date,
    cast(status               as varchar) as status
from source
