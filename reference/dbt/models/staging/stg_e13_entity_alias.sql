-- stg_e13_entity_alias — E-13 Entity Alias (model/entities/core/E-13-entity-alias.md).
--
-- A name a master record has been seen under. A 1:1 typed staging view over
-- raw_e13_entity_alias, column-faithful to the model file's Attribute schema.
--
-- APPEND-ONLY: the model file declares E-13 append-only — an alias, once learned,
-- is kept; a record accumulates names. The grain is (alias_id); the as-of axis is
-- `first_seen_at`. KEY-PARTITIONED by master kind (`subject_type`: legal_entity /
-- instrument / fund / portfolio_company) per the ownership map — SD-13.1/13.2/13.3
-- own their partitions. Like the other append-only entities, the bi-temporal
-- MATERIALISATION is a coordination point — this is a flat view, not a
-- snapshot/incremental model. Grain declared, materialisation deferred.
--
-- Parity-aware SQL: `varchar`/`date` casts only — portable across duckdb and
-- postgres. No duckdb-only idiom.

with source as (
    select * from {{ ref('raw_e13_entity_alias') }}
)

select
    cast(alias_id      as varchar) as alias_id,
    cast(subject_type  as varchar) as subject_type,
    cast(subject_id    as varchar) as subject_id,
    cast(alias_name    as varchar) as alias_name,
    cast(first_seen_at as date)    as first_seen_at,
    cast(source        as varchar) as source,
    cast(confirmed_by  as varchar) as confirmed_by
from source
