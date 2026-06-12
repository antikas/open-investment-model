-- mart_fund_nav — the canonical fund NAV, rolled up per fund, as-of-capable on the
-- valuation (knowledge-time) axis. This is the aggregate query_canonical_nav(fund,
-- as_of) reads (architecture §6.1) — the data layer the NAV-strike workflow queries.
--
--   NAV = Σ(position market values) + accrued income − fees
--
-- THIS IS THE SYNTHETIC DATA LAYER, NOT A STRUCK PRODUCTION NAV. A green NAV
-- invariant over this mart proves the data-layer arithmetic and the as-of plumbing —
-- it is NOT a fiduciary NAV strike. The production strike (matched to an independent
-- shadow pipeline + a GIPS/CFA worked-example oracle, to the build-gate tolerance,
-- behind a human approval gate) is a later, oracle-anchored piece of work. Treat a
-- green invariant here as the data foundation, never as a published NAV.
--
-- GRAIN: one row per fund (per share class where a fund carries them — this synthetic
-- seed carries no share classes, so the roll-up is per fund and share_class is null;
-- the column + grain are present so a share-classed fund needs no reshape).
--
-- THE VALUATION AXIS IS as-of-capable. gross_market_value sums each held position's
-- valuation AS BELIEVED ON a knowledge date:
--   * default (var nav_knowledge_date unset / null) → the CURRENT-knowledge value
--     (is_current_knowledge) — the everyday "value now" strike;
--   * set (var nav_knowledge_date = 'YYYY-MM-DD') → the value the firm believed on
--     that knowledge date, from the bi-temporal int_e07_valuation_versioned
--     system-time bounds — a PAST-AS-OF strike. A since-revised mark returns its
--     pre-revision value, so the as-of NAV differs from current where a mark was
--     restated.
--
-- THE E-04 LATEST-ONLY LIMITATION (OIM-110 carry-forward) — A LANDMINE, NOT A BOUNDED
-- APPROXIMATION. E-04 carries the holding STATE at the latest period-end only — there
-- is no holding history. So a past-as-of NAV is computed as LATEST HOLDINGS × AS-OF
-- VALUATIONS: the valuation axis is genuinely as-of (the bi-temporal mark history is
-- real), but the SET of positions is the latest set, not the set as it was on the
-- as-of date.
--   * On THIS synthetic seed it is inert: E-04 carries a single as_of_date, so every
--     holding shares one date and there is no other holdings set to mis-select.
--   * On REAL holding history the error is UNBOUNDED, not bounded. A past-as-of strike
--     WRONGLY INCLUDES a position opened after the knowledge date (it is in the latest
--     set) and WRONGLY EXCLUDES a position closed before the latest as_of_date (it is
--     absent from the latest set) — a constituent-set error with no magnitude bound: a
--     past NAV can be wrong by an entire position's value.
-- THEREFORE: DO NOT strike a production past NAV on this latest-holdings path. A correct
-- past-as-of NAV needs an AS-OF HOLDINGS (holding-history) view that reconstructs the
-- position set as it stood on the knowledge date. The NAV-strike workflow (OIM-133) must
-- NOT strike a past NAV against a real multi-date holding set on this path; a holding
-- time-series view is the prerequisite (a note for the tools, OIM-112). The default
-- CURRENT strike is unaffected — only the past-as-of path carries this limitation.
--
-- ACCRUALS + FEES. accrued_income sums the abor accrued income (E-04). fees is 0: the
-- synthetic seed carries NO fee or management-charge source (no fee entity is in the
-- ten-entity BD-09 slice — see the seed dictionary), so the fee term is structurally
-- present in the NAV identity but zero on this data. When a fee source is seeded the
-- term carries it with no reshape. (Stating fees = 0 honestly, rather than omitting
-- the term, keeps the NAV = Σ + accruals − fees identity explicit and testable.)
--
-- MANAGER_MARK PROVENANCE (OIM-72 carry-forward). This seed's marks are all
-- holding-level marks the institution CONSUMES as an investor (manager_mark /
-- appraisal / observable_price / mark_to_model) — there are no operated-vehicle
-- struck NAVs (SD-12.9) mixed in, so the SD-08.3-consumed-mark vs SD-12.9-struck-NAV
-- distinction does not bite on this data and is NOT inferred from `method`. The mart
-- carries the producing method/source per position in mart_portfolio_holdings; were a
-- struck-NAV source seeded, the producing-SD provenance (not `method`) would
-- distinguish it. See the report.

{% set nav_knowledge_date = var('nav_knowledge_date', none) %}

with held as (
    -- the logical holdings (one per position_id) with their fund. Latest holdings set
    -- (E-04 latest-only). abor book — the accounting book NAV reads.
    select distinct
        pv.position_id,
        f.portfolio_id     as fund_id,
        f.portfolio_name   as fund_name
    from {{ ref('int_position_valuation') }} pv
    join {{ ref('stg_e03_portfolio_mandate') }} sp on pv.portfolio_id = sp.portfolio_id
    join {{ ref('stg_e03_portfolio_mandate') }} f
        on sp.parent_portfolio_id = f.portfolio_id
        and f.portfolio_type = 'total_fund'
    where pv.book = 'abor'
),

{% if nav_knowledge_date is none %}
-- CURRENT strike: the latest current-knowledge mark per holding.
valuations as (
    select position_id, value_usd
    from (
        select
            position_id,
            value_usd,
            row_number() over (
                partition by position_id
                order by valuation_date desc, valuation_id desc
            ) as rn
        from {{ ref('int_e07_valuation_current') }}
    ) r
    where rn = 1
),
{% else %}
-- AS-OF strike: the value believed on the knowledge date {{ nav_knowledge_date }},
-- at each holding's latest valuation_date, from the bi-temporal system-time bounds.
valuations as (
    select position_id, value_usd
    from (
        select
            position_id,
            value_usd,
            row_number() over (
                partition by position_id
                order by valuation_date desc, valuation_id desc
            ) as rn
        from {{ ref('int_e07_valuation_versioned') }}
        where system_valid_from <= date '{{ nav_knowledge_date }}'
          and (system_valid_to is null or date '{{ nav_knowledge_date }}' < system_valid_to)
    ) r
    where rn = 1
),
{% endif %}

accruals as (
    -- abor accrued income per holding (E-04 latest-only)
    select position_id, coalesce(accrued_income_usd, 0) as accrued_income_usd
    from {{ ref('int_position_valuation') }}
    where book = 'abor'
),

per_fund as (
    select
        held.fund_id,
        held.fund_name,
        cast(null as varchar)                              as share_class,
        count(distinct held.position_id)                   as n_positions,
        sum(v.value_usd)                                   as gross_market_value,
        sum(coalesce(a.accrued_income_usd, 0))             as accrued_income,
        cast(0 as decimal(18, 2))                          as fees
    from held
    left join valuations v on held.position_id = v.position_id
    left join accruals a on held.position_id = a.position_id
    group by held.fund_id, held.fund_name
)

select
    fund_id,
    fund_name,
    share_class,
    n_positions,
    gross_market_value,
    accrued_income,
    fees,
    -- the NAV identity, explicit: Σ market values + accruals − fees
    (gross_market_value + accrued_income - fees)           as nav_usd,
    -- the knowledge date this NAV was struck as-of: null = current strike
    {% if nav_knowledge_date is none %}
    cast(null as date)                                     as nav_knowledge_date
    {% else %}
    date '{{ nav_knowledge_date }}'                        as nav_knowledge_date
    {% endif %}
from per_fund
