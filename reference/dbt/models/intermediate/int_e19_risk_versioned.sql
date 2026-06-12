-- int_e19_risk_versioned — the E-19 bi-temporal log with system-time BOUNDS.
--
-- Derives the knowledge-time validity interval per measurement, over the full log.
-- The logical measurement identity (for restatement detection) is
-- (subject_id, risk_type, measure_type, as_of_date) — a re-run of the SAME measure
-- for the SAME subject + as-of date is a restatement; system_valid_to is the next
-- recorded_at for that logical key; null = current knowledge.
--
-- Bi-temporal access (both axes queryable):
--   * current value          : where is_current_knowledge (int_e19_risk_current)
--   * value as-of KNOWLEDGE K : system_valid_from <= K and (system_valid_to is null or K < system_valid_to)
--   * value as-of as_of_date  : the valid-time axis (as_of_date <= D)

with bounded as (
    select
        measurement_id,
        risk_type,
        subject_type,
        subject_id,
        measure_type,
        as_of_date,
        value,
        currency,
        method,
        scenario_id,
        model_id,
        confidence_score,
        system_valid_from,
        lead(system_valid_from) over (
            partition by subject_id, risk_type, measure_type, as_of_date
            order by system_valid_from, measurement_id
        ) as system_valid_to
    from {{ ref('int_e19_risk_bitemporal') }}
)

select
    measurement_id,
    risk_type,
    subject_type,
    subject_id,
    measure_type,
    as_of_date,
    value,
    currency,
    method,
    scenario_id,
    model_id,
    confidence_score,
    system_valid_from,
    system_valid_to,
    (system_valid_to is null) as is_current_knowledge
from bounded
