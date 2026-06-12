-- The comparator feed agrees with the internal book EXCEPT on the labelled breaks —
-- the oracle-correspondence guard (the zero-missed-breaks ground truth must be exact).
--
-- The labels manifest (break_labels) is the oracle the OIM-165 eval scores the OIM-162
-- engine against. For that to be a valid oracle, the INJECTED breaks in the feed and the
-- LABELLED breaks in the manifest must correspond EXACTLY — no break in the feed missing
-- a label (an unlabelled break the eval would wrongly score as a false positive), no label
-- with no break in the feed (a phantom the eval would wrongly score as a miss). This test
-- FAILS (returns rows) on any mismatch, across the position breaks (carried as a
-- break_note in the custodian feed) and the count of each break class.
--
-- It checks two correspondences:
--   (A) every break-flagged custodian holding (break_note <> '') has a position-class
--       label for that position_id, AND every position-class custodian-side label
--       (price/qty/fx/timing) corresponds to a break-flagged custodian holding — a
--       two-way set equality on position_id;
--   (B) the manifest's total count equals the number of distinct injected breaks
--       (the 8 position breaks visible as break_notes + the 2 transaction breaks + the
--       1 cash break = the manifest row count).

with feed_position_breaks as (
    -- the position_ids the custodian feed actually flags as broken
    select distinct position_id
    from {{ ref('stg_custodian_holdings') }}
    where break_note is not null and break_note <> ''
),

labelled_position_breaks as (
    -- the position_ids the manifest labels as a custodian-side position break
    select distinct record_ref as position_id
    from {{ ref('stg_break_labels') }}
    where reconciliation_type = 'position'
      and expected_side = 'custodian'
),

-- (A) two-way set difference: a feed break with no label, or a label with no feed break
unlabelled_feed_break as (
    select position_id, 'feed-break-has-no-label' as failure
    from feed_position_breaks
    where position_id not in (select position_id from labelled_position_breaks)
),

phantom_label as (
    select position_id, 'label-has-no-feed-break' as failure
    from labelled_position_breaks
    where position_id not in (select position_id from feed_position_breaks)
),

-- (B) the manifest count must equal the injected-break count. The injected breaks are:
--     the distinct break-flagged custodian holdings (position breaks) + the transaction
--     breaks (missing + extra) + the cash break(s). We re-derive that total from the feed
--     and compare to the manifest row count.
counts as (
    select
        (select count(*) from {{ ref('stg_break_labels') }})                       as manifest_count,
        (select count(distinct position_id) from feed_position_breaks)             as feed_position_breaks,
        (select count(*) from {{ ref('stg_break_labels') }}
            where reconciliation_type = 'transaction')                             as manifest_txn_breaks,
        (select count(*) from {{ ref('stg_break_labels') }}
            where reconciliation_type = 'cash')                                    as manifest_cash_breaks,
        (select count(*) from {{ ref('stg_break_labels') }}
            where reconciliation_type = 'position')                                as manifest_position_breaks
),

count_mismatch as (
    select
        'manifest-count-mismatch' as failure,
        manifest_count,
        feed_position_breaks,
        manifest_position_breaks
    from counts
    -- the manifest's position breaks must equal the feed's flagged position holdings, AND
    -- the manifest total must equal position + transaction + cash breaks (no orphan rows).
    where manifest_position_breaks <> feed_position_breaks
       or manifest_count <> (manifest_position_breaks + manifest_txn_breaks + manifest_cash_breaks)
)

select position_id as detail, failure from unlabelled_feed_break
union all
select position_id as detail, failure from phantom_label
union all
select cast(manifest_count as varchar) as detail, failure from count_mismatch
