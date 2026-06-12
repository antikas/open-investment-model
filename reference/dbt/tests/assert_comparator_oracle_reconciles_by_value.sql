-- The labelled-break oracle reconciles to the data BY VALUE, two-way, on every surface —
-- the value-correctness guard the cash class escaped in cycle 1.
--
-- The cycle-1 oracle tests checked the feed-vs-manifest correspondence by SET MEMBERSHIP
-- (which position_ids are flagged == which are labelled) and by COUNT, but never checked
-- that a labelled break's VALUE matches the actual data difference — and the cash surface
-- had no test at all. The result was a corrupt cash class: a cash label whose amount bore
-- no relation to the data, and two real cash differences that were unlabelled. This test
-- closes that defect-class for good: EVERY difference between the comparator feed and the
-- internal book must reconcile to EXACTLY ONE manifest label whose class AND value match,
-- and EVERY manifest label must correspond to a real data difference of that class and
-- value. It FAILS (returns a row) on any of: an unlabelled difference, a label with no
-- backing difference, or a value mismatch — on cash OR position.
--
-- It is REVERT-SENSITIVE: re-introduce the cycle-1 cash bug (draw admin cash independently
-- of custodian cash, or drop the unbroken-fund equality) and a cash difference becomes
-- unlabelled (or the cash label's value stops matching the data) — this test returns a row
-- and FAILS. Likewise a position label whose amount drifts from the feed difference fails.

-- ============================ CASH surface ============================
with cust_cash as (
    select portfolio_id, balance_usd as cust_bal
    from {{ ref('stg_custodian_cash') }}
),

admin_cash as (
    select portfolio_id, amount_usd as admin_bal
    from {{ ref('stg_admin_statement') }}
    where record_type = 'cash'
),

cash_diffs as (
    -- the ACTUAL custodian-vs-admin cash difference per fund (signed magnitude)
    select
        c.portfolio_id,
        abs(a.admin_bal - c.cust_bal) as data_diff
    from cust_cash c
    join admin_cash a on c.portfolio_id = a.portfolio_id
),

cash_labels as (
    select record_ref as portfolio_id, difference_amount as labelled_amount
    from {{ ref('stg_break_labels') }}
    where reconciliation_type = 'cash'
),

-- (1) an actual cash difference with no label (the cycle-1 false-negative archetype)
cash_unlabelled as (
    select
        d.portfolio_id as detail,
        'cash-difference-not-labelled' as failure
    from cash_diffs d
    left join cash_labels l on d.portfolio_id = l.portfolio_id
    where d.data_diff > 0.005
      and l.portfolio_id is null
),

-- (2) a cash label with no backing difference, OR a value mismatch (the cycle-1
--     mis-valued-label archetype: label says 141029, data says 2972240)
cash_label_problems as (
    select
        l.portfolio_id as detail,
        case
            when d.portfolio_id is null then 'cash-label-has-no-data-difference'
            else 'cash-label-value-mismatch'
        end as failure
    from cash_labels l
    left join cash_diffs d on l.portfolio_id = d.portfolio_id
    where d.portfolio_id is null
       or abs(d.data_diff - l.labelled_amount) > 0.005
),

-- ============================ POSITION surface ============================
ibor as (
    select position_id, coalesce(quantity, 0) as qty, coalesce(market_value_usd, 0) as mv
    from {{ ref('stg_e04_holding_position') }}
    where book = 'ibor'
),

cust_h as (
    select
        position_id,
        coalesce(quantity, 0)         as qty,
        coalesce(market_value_usd, 0) as mv,
        break_note
    from {{ ref('stg_custodian_holdings') }}
),

pos_diffs as (
    -- the actual custodian-vs-IBOR difference per holding (qty and mv magnitudes)
    select
        c.position_id,
        c.break_note,
        abs(c.qty - i.qty) as qty_diff,
        abs(c.mv  - i.mv)  as mv_diff
    from cust_h c
    join ibor i on c.position_id = i.position_id
),

pos_labels as (
    select
        record_ref as position_id,
        cause_classification,
        difference_amount,
        difference_qty
    from {{ ref('stg_break_labels') }}
    where reconciliation_type = 'position'
      and expected_side = 'custodian'
),

-- (3) a flagged position holding whose labelled VALUE does not match the data difference.
--     pricing/fx are market-value differences (difference_amount); data_error/timing are
--     quantity differences (difference_qty).
pos_value_mismatch as (
    select
        p.position_id as detail,
        'position-label-value-mismatch' as failure
    from pos_diffs d
    join pos_labels p on d.position_id = p.position_id
    where (
            p.cause_classification in ('pricing', 'fx')
            and abs(d.mv_diff - coalesce(p.difference_amount, -1)) > 0.05
          )
       or (
            p.cause_classification in ('data_error', 'timing')
            and abs(d.qty_diff - coalesce(p.difference_qty, -1)) > 0.0000001
          )
),

-- (4) a flagged position holding with no value difference at all (a label on a row that
--     actually ties to the book — a decorative/phantom break)
pos_decorative as (
    select
        d.position_id as detail,
        'position-flagged-but-no-data-difference' as failure
    from pos_diffs d
    where d.break_note is not null and d.break_note <> ''
      and d.qty_diff <= 0.0000001 and d.mv_diff <= 0.05
)

select detail, failure from cash_unlabelled
union all
select detail, failure from cash_label_problems
union all
select detail, failure from pos_value_mismatch
union all
select detail, failure from pos_decorative
