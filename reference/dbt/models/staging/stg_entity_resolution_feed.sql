-- stg_entity_resolution_feed — the inbound entity-resolution feed (the resolution capability input).
--
-- A 1:1 typed staging view over raw_entity_resolution_feed.csv: inbound legal-entity records from
-- three named source systems (custodian · administrator · internal_onboarding) carrying deliberate,
-- labelled duplicates and variants of a subset of the E-01 masters plus net-new entities. This is
-- the FEED the deterministic three-tier resolution cascade (OIM-199) runs over to produce golden
-- records + a steward review queue. SYNTHETIC, derived to exercise the difficulty gradient (exact
-- LEI · alias · name-variant-no-ID · genuinely-ambiguous).
--
-- NOT a canonical OpenIM entity — no model file, OUT of the schema-drift scope (the feed labels the
-- resolution problem; it is not part of the book). The companion entity_resolution_labels.{csv,json}
-- is the ORACLE (the eval's ground truth), NOT an engine input — the cascade resolves from the feed's
-- observable evidence (name / lei / domicile / parent hint / external id), never by reading the
-- answer key (the OIM-160 oracle-integrity discipline).
--
-- Parity-aware SQL: `varchar` / `date` casts only — portable across duckdb and postgres. No
-- duckdb-only idiom.

with source as (
    select * from {{ ref('raw_entity_resolution_feed') }}
)

select
    cast(source_record_id as varchar) as source_record_id,
    cast(source_system    as varchar) as source_system,
    cast(raw_name         as varchar) as raw_name,
    cast(raw_lei          as varchar) as raw_lei,
    cast(raw_domicile     as varchar) as raw_domicile,
    cast(raw_parent_hint  as varchar) as raw_parent_hint,
    cast(raw_external_id  as varchar) as raw_external_id,
    cast(raw_id_type      as varchar) as raw_id_type,
    cast(received_at      as date)    as received_at
from source
