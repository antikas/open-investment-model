-- int_e07_valuation_current — the CURRENT-knowledge view of E-07 Valuation.
--
-- For each (position_id, valuation_date), the value the firm believes NOW — the
-- latest-recorded mark (is_current_knowledge). This is the everyday "what is the
-- value" surface a NAV strike reads; a revision (a later recorded_at) automatically
-- supersedes the prior mark here, while the prior mark stays queryable as-of its
-- knowledge window in int_e07_valuation_versioned (the GIPS / audit replay surface).

select
    valuation_id,
    position_id,
    valuation_date,
    value_usd,
    method,
    valuation_level,
    source,
    confidence_score,
    system_valid_from
from {{ ref('int_e07_valuation_versioned') }}
where is_current_knowledge
