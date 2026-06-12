-- int_e19_risk_current — the CURRENT-knowledge view of E-19 Risk Measurement.
--
-- For each (subject_id, risk_type, measure_type, as_of_date), the latest-recorded
-- value — what the firm believes the risk number is NOW. A model-recalibration
-- restatement (a later recorded_at) supersedes the prior figure here, while the prior
-- figure stays queryable as-of its knowledge window in int_e19_risk_versioned.

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
    system_valid_from
from {{ ref('int_e19_risk_versioned') }}
where is_current_knowledge
