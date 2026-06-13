-- int_e07_valuation_bitemporal — the append-only bi-temporal LOG of E-07 Valuation.
--
-- E-07 is APPEND-ONLY (model/entities/core/E-07-valuation.md): a restated value for
-- a prior date is a NEW row, never an overwrite. That gives two time axes:
--
--   VALID-TIME (business as-of)    : `valuation_date` — the date the value is *as of*.
--   SYSTEM-TIME (knowledge / when)  : `system_valid_from` (= the seed's `recorded_at`)
--                                     — when the firm recorded this mark. A revision is
--                                     the same valuation_date recorded later, carrying a
--                                     different value_usd.
--
-- This is the genuine bi-temporal materialisation — NOT flat drop-recreate
-- staging. It is materialised INCREMENTAL on the unique
-- `valuation_id`: each seeded valuation row is appended ONCE; a re-run appends nothing
-- (idempotent — no duplicate rows). This model is the append-only log; the derived
-- system-time bounds (system_valid_to / is_current_knowledge) and the current/as-of
-- access are computed in the views on top (int_e07_valuation_current,
-- int_e07_valuation_asof) over the FULL log — so they stay correct after an
-- incremental append (a window function computed over only the new rows would be
-- wrong; deriving over the full table in a view is correct and cheap).
--
-- WHY INCREMENTAL, NOT A dbt SNAPSHOT. dbt snapshots detect changes in a *mutating*
-- source you do not control and synthesise the system-time axis for you. Here the
-- source IS the append-only log — the firm's own valuation history already carries
-- `recorded_at`. So the truthful model is to append the log and derive the
-- system-time bounds from the data: (a) fully reproducible in ONE `dbt build` (a
-- snapshot needs two source states across two runs to show two knowledge points), and
-- (b) idempotent (incremental on the unique key never duplicates). `recorded_at` is
-- an operational provenance column carried in the seed; it is NOT an E-07 model
-- attribute, so the schema-faithful staging view (stg_e07_valuation) does not select
-- it and the schema-drift check stays green.

{{ config(materialized='incremental', unique_key='valuation_id') }}

select
    valuation_id,
    position_id,
    cast(valuation_date as date)               as valuation_date,         -- valid-time
    cast(value_usd as decimal(18, 2))          as value_usd,
    cast(method as varchar)                    as method,
    cast(valuation_level as varchar)           as valuation_level,
    cast(source as varchar)                    as source,
    cast(confidence_score as double precision) as confidence_score,
    cast(recorded_at as date)                  as system_valid_from       -- system-time
from {{ ref('raw_e07_valuation') }}

{% if is_incremental() %}
-- append-only: only rows not already in the log (so a re-run is a no-op append)
where valuation_id not in (select valuation_id from {{ this }})
{% endif %}
