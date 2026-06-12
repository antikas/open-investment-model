-- stg_custodian_cash — the custodian's cash balances (the external comparator feed).
--
-- A typed staging view over raw_custodian_cash — the SYNTHETIC custodian cash statement the
-- firm's cash reconciliation (SD-12.10) matches its internal book against, one balance per
-- fund. Derived from the internal book so the balances agree; the cash break class is
-- exercised via the administrator statement (stg_admin_statement), keeping cash recon a
-- distinct surface. Not a canonical OpenIM entity — out of the schema-drift scope.

with source as (
    select * from {{ ref('raw_custodian_cash') }}
)

select
    cast(custodian_cash_id as varchar)        as custodian_cash_id,
    cast(custodian         as varchar)        as custodian,
    cast(portfolio_id      as varchar)        as portfolio_id,
    cast(as_of_date        as date)           as as_of_date,
    cast(balance_usd       as decimal(18, 2)) as balance_usd,
    cast(currency          as varchar)        as currency
from source
