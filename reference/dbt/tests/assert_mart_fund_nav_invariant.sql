-- The NAV invariant: for every fund, the mart's nav_usd must equal an
-- INDEPENDENT re-aggregation of the source — Σ(current marks) + Σ(abor accruals) − fees
-- — to within |Δ| ≤ $0.01 absolute OR ≤ 1e-6 relative (whichever is looser), the
-- ratified NAV-strike tolerance. The test fails (returns rows) for any fund outside the
-- tolerance.
--
-- THIS TEST IS FALSIFIABLE, NOT A TAUTOLOGY. It does NOT re-run the mart's own roll-up
-- and compare to itself. It recomputes the NAV from the SOURCE by an independent path
-- on ALL THREE components, including the mark SELECTION:
--   * mark selection: the mark in effect per position is selected by a MAX-BY-KEY join
--     (grouped max valuation_date, tie-broken by max valuation_id, then joined back to
--     read the value) — a DIFFERENT SQL formulation from the mart's row_number() window.
--     A mark-selection bug in the mart (wrong order-by / tie-break / a superseded mark)
--     therefore diverges this figure; the test is independent on mark-selection, not
--     only on the roll-up;
--   * gross market value: Σ over that independently-selected mark per held position,
--     joined fund <- sub-portfolio <- holding straight from int_e07_valuation_current
--     and the portfolio staging — NOT from the mart's per_fund CTE;
--   * accruals: Σ abor accrued income straight from stg_e04_holding_position;
--   * fees: 0 (the synthetic seed carries no fee source).
-- If the mart dropped a position, double-counted a book, mis-summed, mis-applied a
-- term, or mis-SELECTED the mark, this independent figure diverges and the test fails.
-- It exercises the DEFAULT (current) strike — the everyday NAV.
--
-- (The honest boundary: a green here proves the data-layer arithmetic over synthetic
-- data, not a struck production NAV — see mart_fund_nav.sql.)

-- The "latest mark per position" is selected here by an INDEPENDENT path from the
-- mart's. The mart picks it with a window function (row_number() over … order by
-- valuation_date desc, valuation_id desc … rn = 1). This test instead derives the
-- per-position key of the mark in effect with a grouped max, then joins back to read
-- its value — a different SQL formulation. If the mart's window-function mark-SELECTION
-- were wrong (a wrong order-by, a wrong tie-break, a superseded mark picked), this
-- max-by-key path would pick a different row and the NAV would diverge, so the test
-- catches a mark-selection bug, not only a roll-up/accrual bug.
with latest_date as (
    -- the greatest valuation_date per position (a grouped max)
    select position_id, max(valuation_date) as latest_valuation_date
    from {{ ref('int_e07_valuation_current') }}
    group by position_id
),

mark_key as (
    -- the (valuation_date, valuation_id) of the mark in effect per position: the row
    -- with the greatest valuation_date (from latest_date), tie-broken by the greatest
    -- valuation_id at that date. A max-by-key selection — NOT the mart's row_number().
    select
        v.position_id,
        ld.latest_valuation_date,
        max(v.valuation_id) as latest_valuation_id
    from {{ ref('int_e07_valuation_current') }} v
    join latest_date ld
        on v.position_id = ld.position_id
        and v.valuation_date = ld.latest_valuation_date
    group by v.position_id, ld.latest_valuation_date
),

independent_marks as (
    -- latest current-knowledge mark per held position, rolled to fund via the portfolio
    -- tree — computed straight from source, independent of the mart. The mark is read
    -- by joining each position's mark_key back to int_e07_valuation_current (a max-by-key
    -- selection), NOT by re-running the mart's row_number() window.
    select
        f.portfolio_id as fund_id,
        sum(lv.value_usd) as gross_market_value
    from {{ ref('int_e07_valuation_current') }} lv
    join mark_key mk
        on lv.position_id = mk.position_id
        and lv.valuation_date = mk.latest_valuation_date
        and lv.valuation_id = mk.latest_valuation_id
    join (
        -- the logical holdings (abor book), one per position, with their portfolio
        select distinct position_id, portfolio_id
        from {{ ref('stg_e04_holding_position') }}
        where book = 'abor'
    ) h on lv.position_id = h.position_id
    join {{ ref('stg_e03_portfolio_mandate') }} sp on h.portfolio_id = sp.portfolio_id
    join {{ ref('stg_e03_portfolio_mandate') }} f
        on sp.parent_portfolio_id = f.portfolio_id and f.portfolio_type = 'total_fund'
    group by f.portfolio_id
),

independent_accruals as (
    select
        f.portfolio_id as fund_id,
        sum(coalesce(e04.accrued_income_usd, 0)) as accrued_income
    from {{ ref('stg_e04_holding_position') }} e04
    join {{ ref('stg_e03_portfolio_mandate') }} sp on e04.portfolio_id = sp.portfolio_id
    join {{ ref('stg_e03_portfolio_mandate') }} f
        on sp.parent_portfolio_id = f.portfolio_id and f.portfolio_type = 'total_fund'
    where e04.book = 'abor'
    group by f.portfolio_id
),

independent_nav as (
    select
        m.fund_id,
        m.gross_market_value + coalesce(a.accrued_income, 0) - 0 as independent_nav
    from independent_marks m
    left join independent_accruals a on m.fund_id = a.fund_id
),

compared as (
    select
        n.fund_id,
        n.nav_usd                                as mart_nav,
        i.independent_nav                        as independent_nav,
        abs(n.nav_usd - i.independent_nav)       as abs_diff,
        abs(n.nav_usd - i.independent_nav)
            / nullif(abs(i.independent_nav), 0)  as rel_diff
    from {{ ref('mart_fund_nav') }} n
    join independent_nav i on n.fund_id = i.fund_id
)

-- A1: fail unless within $0.01 absolute OR 1e-6 relative (whichever is looser)
select *
from compared
where abs_diff > 0.01
  and rel_diff > 0.000001
