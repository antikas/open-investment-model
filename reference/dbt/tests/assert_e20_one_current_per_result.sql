-- Bi-temporal invariant (E-20): for each logical performance-result key
-- (subject_id, return_basis, return_method, period_start, period_end) there is
-- EXACTLY ONE current-knowledge row. A recomputed return (later recorded_at, e.g. a
-- late valuation arrived) must supersede the as-struck figure in the current view,
-- while the as-struck figure stays queryable as-of its knowledge window in the
-- versioned model (the GIPS verification surface). Fails on zero or >1 current.

select
    subject_id,
    return_basis,
    return_method,
    period_start,
    period_end,
    count(*) as current_rows
from {{ ref('int_e20_performance_current') }}
group by subject_id, return_basis, return_method, period_start, period_end
having count(*) <> 1
