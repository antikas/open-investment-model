-- mart_portfolio_holdings — the position-level holdings fact, per portfolio, with the
-- current valuation, asset class, and the fund the portfolio rolls up to. The
-- consumer-facing holdings surface the tools read.
--
-- BOOK: the accounting book (abor) — the official book NAV, performance and reporting
-- read (E-04: SD-12.9 Fund Accounting & NAV, SD-09 Performance, the reporting domains
-- read book = abor). One row per logical holding (the abor row), so a sum over this
-- mart's market_value_usd is a portfolio's accounting market value with no
-- double-counting across books. The ibor (front-office) view stays available in
-- int_position_valuation for an intraday consumer.
--
-- The fund is the holding's portfolio's parent total-fund portfolio (the asset-class
-- sub-portfolio sits under a total_fund portfolio).

with positions as (
    select *
    from {{ ref('int_position_valuation') }}
    where book = 'abor'
),

portfolios as (
    select
        portfolio_id,
        portfolio_name,
        portfolio_type,
        parent_portfolio_id
    from {{ ref('stg_e03_portfolio_mandate') }}
),

funds as (
    -- the total-fund portfolio each asset-class sub-portfolio rolls up to
    select
        portfolio_id,
        portfolio_name as fund_name
    from {{ ref('stg_e03_portfolio_mandate') }}
    where portfolio_type = 'total_fund'
)

select
    p.position_id,
    p.portfolio_id,
    pf.portfolio_name,
    pf.portfolio_type,
    pf.parent_portfolio_id          as fund_id,
    f.fund_name,
    p.instrument_id,
    p.instrument_name,
    p.instrument_class,
    p.asset_class_key,
    p.asset_class_code,
    p.asset_class_label,
    p.asset_class_markets,
    p.as_of_date,
    p.quantity,
    p.commitment_usd,
    p.cost_basis_usd,
    -- the holding's own (abor) market value, and the book-agnostic current mark
    p.e04_market_value_usd          as market_value_usd,
    p.accrued_income_usd,
    p.current_valuation_usd,
    p.current_valuation_date,
    p.valuation_method,
    p.valuation_level,
    p.valuation_source,
    p.valuation_confidence,
    p.currency
from positions p
left join portfolios pf on p.portfolio_id = pf.portfolio_id
left join funds f on pf.parent_portfolio_id = f.portfolio_id
