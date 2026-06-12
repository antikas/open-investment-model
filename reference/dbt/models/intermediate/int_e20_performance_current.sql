-- int_e20_performance_current — the CURRENT-knowledge view of E-20 Performance Result.
--
-- For each (subject_id, return_basis, return_method, period_start, period_end), the
-- latest-recorded return — what the firm reports NOW. A recomputed return (a later
-- recorded_at, e.g. a late valuation arrived) supersedes the prior figure here, while
-- the as-struck figure stays queryable as-of its knowledge window in
-- int_e20_performance_versioned (the GIPS verification surface).

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
    system_valid_from
from {{ ref('int_e20_performance_versioned') }}
where is_current_knowledge
