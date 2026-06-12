-- The cross-mart reconciliation invariant (build-gate A1): for every fund, the NAV
-- mart's gross_market_value must equal Σ of the holdings mart's market_value_usd over
-- that fund's holdings — to within |Δ| ≤ $0.01 absolute OR ≤ 1e-6 relative (whichever
-- is looser), the ratified A1 NAV-strike tolerance
-- (docs/design/agentinvest-build-gate-tolerances.md §A1). The test fails (returns rows)
-- for any fund outside the tolerance.
--
-- WHY THIS EXISTS. mart_fund_nav.gross_market_value sums the E-07 mark over the fund's
-- holdings; mart_portfolio_holdings.market_value_usd ships each holding's accounting
-- (abor) market value. Per the model (E-07:28) the mark IS the abor market_value — the
-- two books may differ on quantity or accrual timing, but NOT on the mark, and the same
-- Valuation feeds the market_value_usd of both E-04 book-rows. So summing the holdings
-- mart per fund MUST tie to the NAV mart's gross_market_value. This is the first
-- cross-check a NAV consumer runs against a struck NAV ("does the NAV's gross equal the
-- sum of its holdings?"); if it fails, the two marts disagree on the same holdings, the
-- same book, the same instant.
--
-- (The honest boundary: a green here proves the two synthetic marts reconcile, not a
-- struck production NAV — see mart_fund_nav.sql.)

with holdings_per_fund as (
    select
        fund_id,
        sum(market_value_usd) as holdings_gross_market_value
    from {{ ref('mart_portfolio_holdings') }}
    group by fund_id
),

compared as (
    select
        n.fund_id,
        n.gross_market_value                                 as nav_gross,
        h.holdings_gross_market_value                        as holdings_gross,
        abs(n.gross_market_value - h.holdings_gross_market_value) as abs_diff,
        abs(n.gross_market_value - h.holdings_gross_market_value)
            / nullif(abs(n.gross_market_value), 0)           as rel_diff
    from {{ ref('mart_fund_nav') }} n
    join holdings_per_fund h on n.fund_id = h.fund_id
)

-- A1: fail unless within $0.01 absolute OR 1e-6 relative (whichever is looser)
select *
from compared
where abs_diff > 0.01
  and rel_diff > 0.000001
