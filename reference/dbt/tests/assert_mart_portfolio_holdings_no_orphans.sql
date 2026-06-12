-- Orphan guard: every holding in mart_portfolio_holdings must resolve to a fund (a
-- total-fund portfolio) and to a current valuation. A holding whose portfolio does not
-- roll up to a total fund, or that has no valuation, is an orphan — it would silently
-- drop out of the NAV roll-up (which joins held positions to valuations) and understate
-- the NAV. The test fails (returns rows) for any such holding.
--
-- This is the "holdings tie to positions, zero orphans" invariant: the holdings mart
-- and the NAV mart read the same held-position set, so a holding visible here but
-- missing a fund or a valuation is a real tie defect.

select
    position_id,
    portfolio_id,
    fund_id,
    current_valuation_usd
from {{ ref('mart_portfolio_holdings') }}
where fund_id is null
   or current_valuation_usd is null
