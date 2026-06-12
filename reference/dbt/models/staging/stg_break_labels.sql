-- stg_break_labels — the labelled-break oracle (the zero-missed-breaks ground truth).
--
-- A typed staging view over break_labels.csv — the manifest cataloguing every deliberately-
-- injected break between the internal book and the synthetic external comparator feed. This
-- is the ORACLE a reconciliation eval scores a reconciliation engine against: the engine,
-- run over the feed, must detect exactly these breaks and no others (zero missed, zero
-- spurious). The taxonomy is E-24 Reconciliation Break's own vocabulary:
--   * reconciliation_type ∈ position / cash / transaction / ibor_abor / custodian / counterparty
--   * cause_classification ∈ timing / pricing / missing_transaction / data_error / fx / fees / unexplained
--   * materiality          ∈ low / medium / high
-- so the eval can compare the engine's E-24 output to this manifest directly.
--
-- The same manifest is emitted as break_labels.json (the JSON form the engine / eval read);
-- this view is the dbt-/analyst-readable form. Not a canonical entity — it labels the feed,
-- it is not part of the book. Out of the schema-drift scope.

with source as (
    select * from {{ ref('break_labels') }}
)

select
    cast(break_id             as varchar)        as break_id,
    cast(reconciliation_type  as varchar)        as reconciliation_type,
    cast(cause_classification as varchar)        as cause_classification,
    cast(record_ref           as varchar)        as record_ref,
    cast(expected_side        as varchar)        as expected_side,
    cast(difference_amount    as decimal(18, 2)) as difference_amount,
    cast(difference_qty       as decimal(28, 8)) as difference_qty,
    cast(materiality          as varchar)        as materiality,
    cast(description          as varchar)        as description
from source
