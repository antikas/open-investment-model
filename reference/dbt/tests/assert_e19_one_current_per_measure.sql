-- Bi-temporal invariant (E-19): for each logical risk-measurement key
-- (subject_id, risk_type, measure_type, as_of_date) there is EXACTLY ONE
-- current-knowledge row. A model-recalibration restatement (later recorded_at) must
-- supersede the prior figure, not coexist. Fails (returns rows) on zero or >1 current.

select
    subject_id,
    risk_type,
    measure_type,
    as_of_date,
    count(*) as current_rows
from {{ ref('int_e19_risk_current') }}
group by subject_id, risk_type, measure_type, as_of_date
having count(*) <> 1
