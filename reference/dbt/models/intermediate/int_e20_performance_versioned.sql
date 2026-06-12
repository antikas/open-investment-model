-- int_e20_performance_versioned — the E-20 bi-temporal log with system-time BOUNDS.
--
-- Derives the knowledge-time validity interval per result, over the full log. The
-- logical result identity (for restatement detection) is
-- (subject_id, return_basis, return_method, period_start, period_end) — a recomputed
-- return for the SAME subject + basis + method + period is a restatement; system_valid_to
-- is the next recorded_at for that logical key; null = current knowledge.
--
-- Bi-temporal access (both axes queryable):
--   * current return         : where is_current_knowledge (int_e20_performance_current)
--   * return as-of KNOWLEDGE K: system_valid_from <= K and (system_valid_to is null or K < system_valid_to)
--   * return as-of period     : the valid-time axis (period_end <= D)

with bounded as (
    select
        performance_result_id,
        subject_type,
        subject_id,
        period_start,
        period_end,
        return_basis,
        return_method,
        return_value,
        currency,
        metric_definition_id,
        composite_id,
        valuation_source,
        confidence_score,
        system_valid_from,
        lead(system_valid_from) over (
            partition by subject_id, return_basis, return_method, period_start, period_end
            order by system_valid_from, performance_result_id
        ) as system_valid_to
    from {{ ref('int_e20_performance_bitemporal') }}
)

select
    performance_result_id,
    subject_type,
    subject_id,
    period_start,
    period_end,
    return_basis,
    return_method,
    return_value,
    currency,
    metric_definition_id,
    composite_id,
    valuation_source,
    confidence_score,
    system_valid_from,
    system_valid_to,
    (system_valid_to is null) as is_current_knowledge
from bounded
