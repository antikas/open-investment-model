-- int_e20_performance_bitemporal — append-only bi-temporal LOG of E-20 Performance Result.
--
-- E-20 is APPEND-ONLY (model/entities/core/E-20-performance-result.md; the performance
-- analogue of E-07/E-19 — GIPS verification needs the as-struck figure preserved). Two
-- time axes:
--   VALID-TIME (as-of period): (`period_start`, `period_end`) — `period_end` is the
--                              date the return is *as of*.
--   SYSTEM-TIME (knowledge)   : `system_valid_from` (= the seed's `recorded_at`) — when
--                              the firm recorded the return. A recomputed return for a
--                              prior period (a late valuation arrived) is a restatement:
--                              same logical key recorded later, revised return_value.
--
-- Genuine bi-temporal grain (NOT flat staging). INCREMENTAL on the unique
-- `performance_result_id` (idempotent append). `recorded_at` is operational provenance,
-- not an E-20 model attribute — the schema-faithful staging view does not select it, so
-- the schema-drift check stays green. Bounds + access derived in int_e20_performance_versioned.

{{ config(materialized='incremental', unique_key='performance_result_id') }}

select
    performance_result_id,
    subject_type,
    subject_id,
    cast(period_start as date)                 as period_start,           -- valid-time (period)
    cast(period_end as date)                   as period_end,             -- valid-time (as-of)
    return_basis,
    return_method,
    cast(return_value as decimal(18, 8))       as return_value,
    cast(currency as varchar)                  as currency,
    metric_definition_id,
    cast(composite_id as varchar)              as composite_id,
    valuation_source,
    cast(confidence_score as double precision) as confidence_score,
    cast(recorded_at as date)                  as system_valid_from       -- system-time
from {{ ref('raw_e20_performance_result') }}

{% if is_incremental() %}
where performance_result_id not in (select performance_result_id from {{ this }})
{% endif %}
