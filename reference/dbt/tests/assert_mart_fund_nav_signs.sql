-- Sign guard: a fund NAV and its gross market value must be positive, accruals
-- non-negative, fees non-negative, and the position count positive. A negative NAV or
-- gross market value, a negative accrual or fee, or a fund that rolled up zero
-- positions, signals a roll-up defect (a sign error, a bad join, an empty fund). The
-- test fails (returns rows) for any fund violating these.
--
-- (No negative share/unit counts: n_positions is the count of held positions per
-- fund; it must be > 0 for a fund to appear.)

select
    fund_id,
    n_positions,
    gross_market_value,
    accrued_income,
    fees,
    nav_usd
from {{ ref('mart_fund_nav') }}
where nav_usd <= 0
   or gross_market_value <= 0
   or accrued_income < 0
   or fees < 0
   or n_positions <= 0
