-- stg_admin_statement — the fund administrator's statement (the external comparator feed).
--
-- A typed staging view over raw_admin_statement — the SYNTHETIC administrator statement the
-- firm reconciles its transaction and cash records against (SD-12.10 transaction matching +
-- cash reconciliation). Carries `record_type` ∈ transaction / cash lines. Derived from the
-- internal book so the majority agree, with deliberately-injected, labelled breaks: a
-- MISSING transaction (a settled internal trade absent from the admin record), an EXTRA
-- transaction (an admin line absent from the internal book), and a cash balance that
-- disagrees with the custodian. All catalogued in break_labels.csv (the oracle).
--
-- Not a canonical OpenIM entity — an external record, out of the schema-drift scope.

with source as (
    select * from {{ ref('raw_admin_statement') }}
)

select
    cast(admin_record_id as varchar)        as admin_record_id,
    cast(record_type     as varchar)        as record_type,
    cast(portfolio_id    as varchar)        as portfolio_id,
    cast(instrument_id   as varchar)        as instrument_id,
    cast(as_of_date      as date)           as as_of_date,
    cast(amount_usd      as decimal(18, 2)) as amount_usd,
    cast(currency        as varchar)        as currency,
    cast(ref             as varchar)        as ref
from source
