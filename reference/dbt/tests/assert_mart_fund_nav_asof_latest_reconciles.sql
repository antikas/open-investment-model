-- As-of reconciliation: the as-of NAV struck at the LATEST knowledge state must equal
-- the CURRENT NAV. The current strike reads int_e07_valuation_current
-- (is_current_knowledge); the as-of strike reads int_e07_valuation_versioned filtered
-- to a knowledge date. At the latest knowledge date the versioned is_current_knowledge
-- rows ARE the current rows — so the two paths must agree per fund, to within the A1
-- tolerance. The test fails (returns rows) if any fund's current gross market value
-- diverges from the same figure computed via the versioned (is_current_knowledge)
-- path.
--
-- This guards the as-of plumbing: it proves the bi-temporal versioned path the as-of
-- strike uses reconciles to the everyday current path at the latest knowledge state —
-- so a past-as-of strike (which only differs by reading an EARLIER knowledge window)
-- is built on a path that is correct at the boundary. NOT a tautology: the current
-- and versioned models are different SQL (one filters is_current_knowledge in a view,
-- the other derives system-time bounds with a window function) — they could diverge
-- if the bound derivation were wrong.

with current_path as (
    select
        f.portfolio_id as fund_id,
        sum(lv.value_usd) as gmv_current
    from (
        select position_id, value_usd,
            row_number() over (partition by position_id
                               order by valuation_date desc, valuation_id desc) as rn
        from {{ ref('int_e07_valuation_current') }}
    ) lv
    join (select distinct position_id, portfolio_id
          from {{ ref('stg_e04_holding_position') }} where book='abor') h
        on lv.position_id = h.position_id
    join {{ ref('stg_e03_portfolio_mandate') }} sp on h.portfolio_id = sp.portfolio_id
    join {{ ref('stg_e03_portfolio_mandate') }} f
        on sp.parent_portfolio_id = f.portfolio_id and f.portfolio_type='total_fund'
    where lv.rn = 1
    group by f.portfolio_id
),

versioned_latest_path as (
    -- latest valuation_date per position, taking the is_current_knowledge row from the
    -- versioned (bi-temporal) model — the as-of strike at the latest knowledge state.
    select
        f.portfolio_id as fund_id,
        sum(lv.value_usd) as gmv_versioned
    from (
        select position_id, value_usd,
            row_number() over (partition by position_id
                               order by valuation_date desc, valuation_id desc) as rn
        from {{ ref('int_e07_valuation_versioned') }}
        where is_current_knowledge
    ) lv
    join (select distinct position_id, portfolio_id
          from {{ ref('stg_e04_holding_position') }} where book='abor') h
        on lv.position_id = h.position_id
    join {{ ref('stg_e03_portfolio_mandate') }} sp on h.portfolio_id = sp.portfolio_id
    join {{ ref('stg_e03_portfolio_mandate') }} f
        on sp.parent_portfolio_id = f.portfolio_id and f.portfolio_type='total_fund'
    where lv.rn = 1
    group by f.portfolio_id
)

select
    c.fund_id,
    c.gmv_current,
    v.gmv_versioned,
    abs(c.gmv_current - v.gmv_versioned) as abs_diff
from current_path c
join versioned_latest_path v on c.fund_id = v.fund_id
where abs(c.gmv_current - v.gmv_versioned) > 0.01
  and abs(c.gmv_current - v.gmv_versioned) / nullif(abs(c.gmv_current), 0) > 0.000001
