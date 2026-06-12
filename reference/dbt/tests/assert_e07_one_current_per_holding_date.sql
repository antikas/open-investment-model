-- Bi-temporal invariant (E-07): for each logical valuation key (position_id,
-- valuation_date) there is EXACTLY ONE current-knowledge row — the latest-recorded
-- mark. A revision (a later recorded_at) must supersede the prior mark, not coexist
-- as a second "current" row. This test fails (returns rows) if any logical key has
-- zero or more than one current-knowledge mark.
--
-- This is the load-bearing correctness guard for the bi-temporal materialisation:
-- without it, a "current" view that double-counts a revised holding would inflate a
-- NAV. Parity-aware SQL (group by + having; portable duckdb/postgres).

select
    position_id,
    valuation_date,
    count(*) as current_rows
from {{ ref('int_e07_valuation_current') }}
group by position_id, valuation_date
having count(*) <> 1
