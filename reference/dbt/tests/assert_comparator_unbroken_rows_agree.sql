-- The comparator feed AGREES with the internal book on every UNBROKEN row — the
-- "majority matches, the engine must FIND the breaks" guard.
--
-- The custodian holdings file is derived from the internal IBOR book, so every custodian
-- holding NOT flagged as a break (break_note = '') must tie EXACTLY to the IBOR book's
-- position on quantity and market value. If an unbroken custodian row silently disagreed
-- with the book, the feed would carry an UNLABELLED break — the engine would surface a
-- difference the oracle does not list, scored as a false positive. This test FAILS
-- (returns rows) for any unbroken custodian holding that does not tie to the IBOR book.
--
-- It also asserts there IS a clear unbroken majority: it fails if the unbroken custodian
-- holdings are not the majority of the feed (the engine must distinguish matched from
-- broken, not assume everything is a break).

with ibor as (
    select position_id, coalesce(quantity, 0) as qty, coalesce(market_value_usd, 0) as mv
    from {{ ref('stg_e04_holding_position') }}
    where book = 'ibor'
),

cust as (
    select
        custodian_record_id,
        position_id,
        coalesce(quantity, 0)         as qty,
        coalesce(market_value_usd, 0) as mv,
        break_note
    from {{ ref('stg_custodian_holdings') }}
),

unbroken_disagreements as (
    -- an unbroken (break_note = '') custodian holding that does not tie to the ibor book
    select
        c.custodian_record_id,
        c.position_id,
        c.qty   as cust_qty,
        i.qty   as ibor_qty,
        c.mv    as cust_mv,
        i.mv    as ibor_mv
    from cust c
    join ibor i on c.position_id = i.position_id
    where (c.break_note is null or c.break_note = '')
      and (abs(c.qty - i.qty) > 0.00000001 or abs(c.mv - i.mv) > 0.01)
),

majority as (
    select
        sum(case when break_note is null or break_note = '' then 1 else 0 end) as n_unbroken,
        count(*) as n_total
    from cust
),

no_majority as (
    select 'no-unbroken-majority' as failure, n_unbroken, n_total
    from majority
    -- the unbroken rows must be a clear majority (> half of the feed)
    where n_unbroken * 2 <= n_total
)

select custodian_record_id as detail, 'unbroken-row-disagrees-with-book' as failure
from unbroken_disagreements
union all
select cast(n_unbroken as varchar) as detail, failure
from no_majority
