-- The IBOR/ABOR divergence is GENUINE and CHARACTERISED — the half-job guard.
--
-- The whole point of the W2 reconciliation substrate is that the two books of record
-- (IBOR real-time, ABOR accounting) genuinely DIFFER, so SD-12.10's IBOR/ABOR
-- reconciliation has real divergence to find. Before this cycle the ibor and abor rows
-- were byte-identical (a reconciliation would be trivially clean). This test FAILS
-- (returns a row) if the divergence collapses back to (near-)identical — i.e. if fewer
-- than a floor of logical holdings differ between their ibor and abor rows on quantity,
-- cost basis, market value or accrued income.
--
-- It also BOUNDS the divergence (the "characterised, not random noise" half): every
-- per-holding difference must be within a sane relative band (no book is wildly off the
-- other — the books are two views of the same holding, not two different holdings). A
-- divergence outside the band is itself a returned row (a test failure), so a generator
-- bug that blew a number up is caught too.
--
-- ABOR is the NAV-bearing accounting truth (unchanged); IBOR diverges from it. The
-- divergence classes: TD/SD timing (ibor quantity/MV higher — an in-flight buy in ibor
-- not yet in abor), accruals (abor carries accrued income, ibor does not), cost basis
-- (ibor trade-date lot vs abor average cost).

with books as (
    select
        position_id,
        max(case when book = 'ibor' then coalesce(quantity, 0) end)            as ibor_qty,
        max(case when book = 'abor' then coalesce(quantity, 0) end)            as abor_qty,
        max(case when book = 'ibor' then coalesce(cost_basis_usd, 0) end)      as ibor_cost,
        max(case when book = 'abor' then coalesce(cost_basis_usd, 0) end)      as abor_cost,
        max(case when book = 'ibor' then coalesce(market_value_usd, 0) end)    as ibor_mv,
        max(case when book = 'abor' then coalesce(market_value_usd, 0) end)    as abor_mv,
        max(case when book = 'ibor' then coalesce(accrued_income_usd, 0) end)  as ibor_accr,
        max(case when book = 'abor' then coalesce(accrued_income_usd, 0) end)  as abor_accr
    from {{ ref('stg_e04_holding_position') }}
    group by position_id
),

diffs as (
    select
        position_id,
        ibor_qty, abor_qty, ibor_cost, abor_cost, ibor_mv, abor_mv, ibor_accr, abor_accr,
        case
            when ibor_qty <> abor_qty or ibor_cost <> abor_cost
                 or ibor_mv <> abor_mv or ibor_accr <> abor_accr
            then 1 else 0
        end as differs,
        -- the largest relative gap across the divergence columns (mv as the scale)
        case when abor_mv > 0 then abs(ibor_mv - abor_mv) / abor_mv else 0 end as mv_rel_gap,
        case when abor_qty > 0 then abs(ibor_qty - abor_qty) / abor_qty else 0 end as qty_rel_gap,
        case when abor_cost > 0 then abs(ibor_cost - abor_cost) / abor_cost else 0 end as cost_rel_gap
    from books
),

summary as (
    select
        sum(differs) as n_divergent_holdings,
        count(*)     as n_holdings
    from diffs
)

-- (1) the divergence must be PRESENT: fail if fewer than 5 holdings diverge (the
--     half-job trigger — a book effectively identical to the other).
select 'too-few-divergent-holdings' as failure, n_divergent_holdings, n_holdings
from summary
where n_divergent_holdings < 5

union all

-- (2) the divergence must be BOUNDED / characterised: fail on any holding whose
--     ibor/abor gap exceeds a sane band (mv or qty > 60%, cost > 30%) — that is not a
--     book divergence, it is noise or a generator bug.
select 'divergence-out-of-band' as failure,
       cast(differs as bigint)   as n_divergent_holdings,
       0                         as n_holdings
from diffs
where mv_rel_gap > 0.60 or qty_rel_gap > 0.60 or cost_rel_gap > 0.30
