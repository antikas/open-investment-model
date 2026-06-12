-- int_e19_risk_bitemporal — the append-only bi-temporal LOG of E-19 Risk Measurement.
--
-- E-19 is APPEND-ONLY (model/entities/core/E-19-risk-measurement.md; the risk analogue
-- of E-07). Two time axes:
--   VALID-TIME (as-of)   : `as_of_date`        — the date the measurement is *as of*.
--   SYSTEM-TIME (knowledge): `system_valid_from` (= the seed's `recorded_at`) — when the
--                            firm recorded it. A model recalibration restatement is the
--                            same (subject, risk_type, measure_type, as_of_date) recorded
--                            later with a revised value.
--
-- Genuine bi-temporal grain (NOT flat staging). INCREMENTAL on the unique
-- `measurement_id` (idempotent append). `recorded_at` is operational provenance, not an
-- E-19 model attribute — the schema-faithful staging view does not select it, so the
-- schema-drift check stays green. The system-time bounds + current/as-of access are
-- derived in int_e19_risk_versioned over the full log.

{{ config(materialized='incremental', unique_key='measurement_id') }}

select
    measurement_id,
    risk_type,
    subject_type,
    subject_id,
    measure_type,
    cast(as_of_date as date)                   as as_of_date,             -- valid-time
    cast(value as decimal(28, 8))              as value,
    cast(currency as varchar)                  as currency,
    cast(method as varchar)                    as method,
    cast(scenario_id as varchar)               as scenario_id,
    cast(model_id as varchar)                  as model_id,
    cast(confidence_score as double precision) as confidence_score,
    cast(recorded_at as date)                  as system_valid_from       -- system-time
from {{ ref('raw_e19_risk_measurement') }}

{% if is_incremental() %}
where measurement_id not in (select measurement_id from {{ this }})
{% endif %}
