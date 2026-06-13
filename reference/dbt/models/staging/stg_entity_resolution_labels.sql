-- stg_entity_resolution_labels — the labelled entity-resolution oracle (the ground truth).
--
-- A typed staging view over entity_resolution_labels.csv — the manifest cataloguing the TRUE
-- canonical E-01 entity_id (or NEW / AMBIGUOUS) for every inbound feed record, tagged with the
-- difficulty tier it exercises. This is the ORACLE a resolution eval scores the cascade against:
-- ZERO mis-merges (no two distinct true entities merged) and ZERO missed-merges among the
-- auto-resolved set, with the genuinely-ambiguous correctly quarantined.
--
-- The labels are derived from the INJECTION INTENT used to build raw_entity_resolution_feed.csv
-- (never read back from the feed strings) — the OIM-160 oracle-integrity discipline. The same
-- manifest is emitted as entity_resolution_labels.json (the form the engine / eval read); this view
-- is the dbt-/analyst-readable form. NOT a canonical entity — it labels the feed, out of the
-- schema-drift scope.
--
-- Parity-aware SQL: `varchar` casts only — portable across duckdb and postgres.

with source as (
    select * from {{ ref('entity_resolution_labels') }}
)

select
    cast(source_record_id  as varchar) as source_record_id,
    cast(true_entity_id    as varchar) as true_entity_id,
    cast(resolution_outcome as varchar) as resolution_outcome,
    cast(difficulty_tier   as varchar) as difficulty_tier,
    cast(note              as varchar) as note
from source
