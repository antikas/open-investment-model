-- stg_e01_legal_entity — E-01 Legal Entity (model/entities/core/E-01-legal-entity.md).
--
-- The universal party master. A 1:1 typed staging view over raw_e01_legal_entity,
-- column-faithful to the model file's Attribute schema (the schema-drift check
-- cross-checks the Pydantic schema, which is itself drift-checked against this
-- model file). Single owner (SD-13.2). View-materialised per the staging
-- convention — idempotent by construction.
--
-- Parity-aware SQL: casts use `varchar` / `date` only (both duckdb and the
-- dbt-postgres prod target render these). No duckdb-only idiom. The `known_aliases`
-- array and `external_ids` map are kept as their raw text in this flat sample
-- staging layer (the normalised list/map shaping is OIM-110/111 — the seed carries
-- them as `;`-joined / JSON text so the column EXISTS at the right grain now).

with source as (
    select * from {{ ref('raw_e01_legal_entity') }}
)

select
    cast(entity_id        as varchar) as entity_id,
    cast(entity_name      as varchar) as entity_name,
    cast(entity_type      as varchar) as entity_type,
    cast(lei              as varchar) as lei,
    cast(domicile         as varchar) as domicile,
    cast(parent_entity_id as varchar) as parent_entity_id,
    cast(known_aliases    as varchar) as known_aliases,
    cast(external_ids     as varchar) as external_ids,
    cast(status           as varchar) as status,
    cast(first_seen_at    as date)    as first_seen_at
from source
