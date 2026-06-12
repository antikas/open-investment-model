-- int_position_risk — a holding-level subject (E-04) resolved to its current risk
-- measurements (E-19). The position-level risk fact a risk dashboard reads.
--
-- E-19 risk measurements attach to a subject (subject_type / subject_id) that is a
-- holding, a portfolio, a total fund or a counterparty. This model resolves the
-- HOLDING-subject measurements (subject_type = 'holding', subject_id = a position_id)
-- onto the logical holding, alongside the holding's instrument + asset class — the
-- E-04 x E-19 join the goal names. Portfolio / total-fund / counterparty risk
-- measurements are NOT holding-grain and are left in int_e19_risk_current for the
-- portfolio- and fund-level consumers (a holding-grain join would drop or fan them
-- out wrongly).
--
-- GRAIN: one row per (position_id, measurement) for holding-subject risk — the
-- current-knowledge risk figure per (subject_id, risk_type, measure_type, as_of_date).
-- A holding's distinct positions across books share one logical holding, so the
-- attach is on the logical holding (position_id), book-agnostic like the valuation.
--
-- THE AS-OF PATH IS PRESERVED via int_e19_risk_versioned (the bi-temporal surface);
-- this model carries current-knowledge, mirroring int_position_valuation.

with holding_keys as (
    -- the logical holdings (one row per position_id) with their instrument + asset class
    select distinct
        pv.position_id,
        pv.portfolio_id,
        pv.instrument_id,
        pv.instrument_name,
        pv.asset_class_key,
        pv.asset_class_code,
        pv.asset_class_label
    from {{ ref('int_position_valuation') }} pv
),

holding_risk as (
    select
        measurement_id,
        risk_type,
        subject_type,
        subject_id,
        measure_type,
        as_of_date,
        value          as risk_value,
        currency       as risk_currency,
        method         as risk_method,
        scenario_id,
        model_id,
        confidence_score as risk_confidence
    from {{ ref('int_e19_risk_current') }}
    where subject_type = 'holding'
)

select
    hk.position_id,
    hk.portfolio_id,
    hk.instrument_id,
    hk.instrument_name,
    hk.asset_class_key,
    hk.asset_class_code,
    hk.asset_class_label,
    hr.measurement_id,
    hr.risk_type,
    hr.measure_type,
    hr.as_of_date,
    hr.risk_value,
    hr.risk_currency,
    hr.risk_method,
    hr.scenario_id,
    hr.model_id,
    hr.risk_confidence
from holding_risk hr
join holding_keys hk
    on hr.subject_id = hk.position_id     -- holding-subject risk onto the logical holding
