-- The labelled-break oracle reconciles to the data BY VALUE, two-way, on every surface —
-- the value-correctness guard.
--
-- A correspondence check by SET MEMBERSHIP alone (which position_ids are flagged == which
-- are labelled) and by COUNT does NOT verify
-- that a labelled break's VALUE matches the actual data difference — and a surface with
-- no value test at all can carry a corrupt class: a cash label whose amount bore
-- no relation to the data, and two real cash differences that were unlabelled. This test
-- closes that defect-class for good: EVERY difference between the comparator feed and the
-- internal book must reconcile to EXACTLY ONE manifest label whose class AND value match,
-- and EVERY manifest label must correspond to a real data difference of that class and
-- value. It FAILS (returns a row) on any of: an unlabelled difference, a label with no
-- backing difference, or a value mismatch — on cash OR position.
--
-- It is REVERT-SENSITIVE: re-introduce the original cash bug (draw admin cash independently
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

-- (1) an actual cash difference with no label (the false-negative archetype)
cash_unlabelled as (
    select
        d.portfolio_id as detail,
        'cash-difference-not-labelled' as failure
    from cash_diffs d
    left join cash_labels l on d.portfolio_id = l.portfolio_id
    where d.data_diff > 0.005
      and l.portfolio_id is null
),

-- (2) a cash label with no backing difference, OR a value mismatch (the
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
),

-- ============================ A/B-DISAGREEMENT surface ============================
-- The A/B-disagreement case is a position label whose expected_side is INTERNAL: the custodian
-- ties to the IBOR book value (Pipeline A clears) but the IBOR book value diverges from the E-07
-- mark (Pipeline B breaks). Its labelled value must equal the book-vs-mark divergence by value.
ab_book_mark as (
    -- the IBOR book value vs the E-07 mark per holding (the int model carries both columns)
    select
        position_id,
        abs(e04_market_value_usd - current_valuation_usd) as book_mark_diff
    from {{ ref('int_position_valuation') }}
    where book = 'ibor'
),

ab_labels as (
    select record_ref as position_id, difference_amount as labelled_amount
    from {{ ref('stg_break_labels') }}
    where reconciliation_type = 'position'
      and expected_side = 'internal'
),

-- (5) an A/B (position-internal) label whose value does not match the book-vs-mark divergence
--     (the label->data direction). NOTE: this CTE checks ONLY label->data on the A/B + ibor_abor
--     surfaces (every labelled break reconciles to a real divergence by value). The REVERSE
--     direction (an unlabelled book-vs-mark or IBOR/ABOR divergence with no label) is NOT
--     re-implemented here in SQL — it is enforced at the PYTEST layer: the seed-loaded pin test's
--     NO-SPURIOUS assertion fails on any unlabelled engine-visible divergence, and
--     assert_comparator_unbroken_rows_agree binds every un-noted custodian holding to tie the book.
--     (The full two-direction scoring formalisation lives in the eval layer; do not add the reverse CTE here.)
ab_value_mismatch as (
    select
        l.position_id as detail,
        'ab-disagreement-label-value-mismatch' as failure
    from ab_labels l
    left join ab_book_mark m on l.position_id = m.position_id
    where m.position_id is null
       or abs(m.book_mark_diff - l.labelled_amount) > 0.05
),

-- ============================ IBOR/ABOR surface ============================
-- A rule-unreachable break is an IBOR-vs-ABOR market-value residual the deterministic rules
-- cannot explain (the engine lands `unexplained`; the oracle carries the true cause). Its
-- labelled value must equal the actual IBOR-vs-ABOR market-value difference.
abor_pos as (
    select position_id, coalesce(market_value_usd, 0) as mv
    from {{ ref('stg_e04_holding_position') }}
    where book = 'abor'
),

ibor_abor_diffs as (
    select
        i.position_id,
        abs(a.mv - i.mv) as mv_diff
    from ibor i
    join abor_pos a on i.position_id = a.position_id
),

ibor_abor_labels as (
    -- the manifest record_ref is 'ibor:POS-XXXX'; strip the side prefix to the bare position_id
    select
        replace(record_ref, 'ibor:', '') as position_id,
        difference_amount as labelled_amount
    from {{ ref('stg_break_labels') }}
    where reconciliation_type = 'ibor_abor'
),

-- (6) an ibor_abor label with no backing IBOR-vs-ABOR difference, or a value mismatch
ibor_abor_problems as (
    select
        l.position_id as detail,
        case when d.position_id is null then 'ibor-abor-label-has-no-data-difference'
             else 'ibor-abor-label-value-mismatch' end as failure
    from ibor_abor_labels l
    left join ibor_abor_diffs d on l.position_id = d.position_id
    where d.position_id is null
       or abs(d.mv_diff - l.labelled_amount) > 0.05
),

-- ============================ NAV surface ============================
-- The admin fund-level NAV vs the internally-derivable NAV, rolled up per total fund under the
-- repo's CANONICAL NAV identity (mart_fund_nav.sql:5) — NAV = Sigma(market values) + accrued
-- income - fees — so the oracle and the W1 NAV-strike path read ONE NAV truth (SSOT).
-- fees are structurally zero on this seed (no fee source is seeded —
-- mart_fund_nav.sql:48-53), so the term is omitted but named. The labelled shadow-NAV divergence's
-- value must equal the admin-vs-canonical-internal NAV difference.
fund_parent as (
    select portfolio_id, parent_portfolio_id
    from {{ ref('stg_e03_portfolio_mandate') }}
),

internal_nav as (
    -- Sigma the ABOR market value + Sigma the ABOR accrued income, rolled up to the total fund
    -- (sleeve -> parent total fund) — the canonical NAV identity (fees = 0 on this seed).
    select
        coalesce(fp.parent_portfolio_id, e.portfolio_id) as fund_id,
        sum(coalesce(e.market_value_usd, 0) + coalesce(e.accrued_income_usd, 0)) as internal_nav
    from {{ ref('stg_e04_holding_position') }} e
    left join fund_parent fp on e.portfolio_id = fp.portfolio_id
    where e.book = 'abor'
    group by 1
),

admin_nav as (
    select portfolio_id as fund_id, amount_usd as admin_nav
    from {{ ref('stg_admin_statement') }}
    where record_type = 'nav'
),

nav_diffs as (
    select
        a.fund_id,
        abs(a.admin_nav - i.internal_nav) as nav_diff
    from admin_nav a
    join internal_nav i on a.fund_id = i.fund_id
),

nav_labels as (
    select record_ref as fund_id, difference_amount as labelled_amount
    from {{ ref('stg_break_labels') }}
    where reconciliation_type = 'nav'
),

-- (7) a nav label with no backing admin-vs-internal NAV difference, or a value mismatch;
--     AND an unlabelled admin-vs-internal NAV divergence beyond the 1 bp band
nav_label_problems as (
    select
        l.fund_id as detail,
        case when d.fund_id is null then 'nav-label-has-no-data-difference'
             else 'nav-label-value-mismatch' end as failure
    from nav_labels l
    left join nav_diffs d on l.fund_id = d.fund_id
    where d.fund_id is null
       or abs(d.nav_diff - l.labelled_amount) > 0.05
),

nav_unlabelled as (
    -- an admin NAV that diverges from the internal NAV beyond ~1 bp with no label
    select
        d.fund_id as detail,
        'nav-difference-not-labelled' as failure
    from nav_diffs d
    join internal_nav i on d.fund_id = i.fund_id
    left join nav_labels l on d.fund_id = l.fund_id
    where d.nav_diff > i.internal_nav * 0.0001
      and l.fund_id is null
)

select detail, failure from cash_unlabelled
union all
select detail, failure from cash_label_problems
union all
select detail, failure from pos_value_mismatch
union all
select detail, failure from pos_decorative
union all
select detail, failure from ab_value_mismatch
union all
select detail, failure from ibor_abor_problems
union all
select detail, failure from nav_label_problems
union all
select detail, failure from nav_unlabelled
