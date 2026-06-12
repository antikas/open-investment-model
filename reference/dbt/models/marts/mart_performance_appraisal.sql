-- mart_performance_appraisal — the current-knowledge performance results (E-20) with
-- their appraisal context (the subject fund/portfolio, its name and type). The BD-09
-- performance fact the tools and the performance-appraisal workflow read.
--
-- GRAIN: one row per current-knowledge performance result — the latest-recomputed
-- figure per logical key (subject_id, return_basis, return_method, period_start,
-- period_end). A recomputed return (a late valuation arrived) supersedes the prior
-- figure here; the as-struck figure stays queryable in int_e20_performance_versioned
-- (the GIPS verification surface), so the as-of axis is preserved.
--
-- THIS IS THE SYNTHETIC DATA LAYER. The returns are illustrative synthetic figures,
-- not benchmarked against any real fund or a GIPS/CFA worked example. The fiduciary
-- returns strike (matched to the published GIPS Handbook / CFA-CIPM examples, to the
-- ratified returns tolerance) is a later, oracle-anchored piece of work. A green
-- pipeline over this data is the data foundation, not a verified return.

with results as (
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
        confidence_score
    from {{ ref('int_e20_performance_current') }}
),

subjects as (
    select
        portfolio_id,
        portfolio_name,
        portfolio_type,
        parent_portfolio_id
    from {{ ref('stg_e03_portfolio_mandate') }}
)

select
    r.performance_result_id,
    r.subject_type,
    r.subject_id,
    s.portfolio_name        as subject_name,
    s.portfolio_type        as subject_portfolio_type,
    s.parent_portfolio_id   as subject_parent_portfolio_id,
    r.period_start,
    r.period_end,
    r.return_basis,
    r.return_method,
    r.return_value,
    r.currency,
    r.metric_definition_id,
    r.composite_id,
    r.valuation_source,
    r.confidence_score
from results r
left join subjects s on r.subject_id = s.portfolio_id
