-- Singular test: E-04 Holding / Position is key-partitioned by `book` (ADR-0022),
-- so its identity is the COMPOSITE (position_id, book) — a position_id appears once
-- per book (ibor and abor), never twice in the same book. This test fails (returns
-- rows) if any (position_id, book) pair occurs more than once.
--
-- This replaces a dbt_utils.unique_combination_of_columns test so the project
-- needs no package dependency. The SQL is parity-aware (group by + having count
-- render identically on duckdb and the postgres prod target). It asserts the
-- key-partition invariant the model file declares, not single-column uniqueness
-- (position_id alone is intentionally NOT unique — the IBOR and ABOR rows share it).

select
    position_id,
    book,
    count(*) as n
from {{ ref('stg_e04_holding_position') }}
group by position_id, book
having count(*) > 1
