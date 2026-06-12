-- stg_e14_external_identifier — E-14 External Identifier (model/entities/core/E-14-external-identifier.md).
--
-- A cross-reference from a master's golden key to an external-system identifier.
-- A 1:1 typed staging view over raw_e14_external_identifier, column-faithful to
-- the model file's Attribute schema. KEY-PARTITIONED by master kind
-- (`subject_type`) per the ownership map — SD-13.1/13.2/13.3 own their partitions.
-- View-materialised; idempotent.
--
-- Parity-aware SQL: `varchar` casts plus `boolean` for `verified`. `boolean`
-- renders on both duckdb and postgres. No duckdb-only idiom.

with source as (
    select * from {{ ref('raw_e14_external_identifier') }}
)

select
    cast(external_id_record as varchar) as external_id_record,
    cast(subject_type       as varchar) as subject_type,
    cast(subject_id         as varchar) as subject_id,
    cast(external_system    as varchar) as external_system,
    cast(external_id        as varchar) as external_id,
    cast(id_type            as varchar) as id_type,
    cast(verified           as boolean) as verified
from source
