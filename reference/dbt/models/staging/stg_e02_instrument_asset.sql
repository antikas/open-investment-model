-- stg_e02_instrument_asset — E-02 Instrument / Asset (model/entities/core/E-02-instrument-asset.md).
--
-- The universal holdable-thing master. A 1:1 typed staging view over
-- raw_e02_instrument_asset, column-faithful to the model file's Attribute schema.
-- Single owner (SD-13.1). View-materialised; idempotent.
--
-- Parity-aware SQL: `varchar` casts, plus `integer` for `asset_class`. The model
-- file declares `asset_class` as `int (FK -> E-09)`, matching E-09's integer PK
-- `asset_class_key`, so the join `stg_e02.asset_class = stg_e09.asset_class_key`
-- is `integer = integer` — valid on postgres (the OIM-111 mart join), not the
-- `varchar = integer` predicate postgres rejects. The `external_ids` map is raw
-- text in this flat sample layer (normalisation is OIM-110/111). No duckdb-only idiom.

with source as (
    select * from {{ ref('raw_e02_instrument_asset') }}
)

select
    cast(instrument_id    as varchar) as instrument_id,
    cast(instrument_name  as varchar) as instrument_name,
    cast(instrument_class as varchar) as instrument_class,
    cast(asset_class      as integer) as asset_class,
    cast(issuer_entity_id as varchar) as issuer_entity_id,
    cast(currency         as varchar) as currency,
    cast(isin             as varchar) as isin,
    cast(figi             as varchar) as figi,
    cast(external_ids     as varchar) as external_ids,
    cast(status           as varchar) as status
from source
