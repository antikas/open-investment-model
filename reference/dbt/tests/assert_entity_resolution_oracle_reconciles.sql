-- The labelled entity-resolution oracle reconciles to the feed AND the E-01 master, two-way —
-- the oracle-integrity invariant the cascade is scored against.
--
-- The oracle-integrity discipline: a labelled oracle whose labels were drawn INDEPENDENTLY of the data is
-- corrupt (a label with no backing record; a real record left unlabelled; a label whose value bears
-- no relation to the data). This test closes that defect-class for the entity-resolution oracle: it
-- FAILS (returns a row) on any of —
--   (1) an inbound feed record with NO label (an unlabelled record);
--   (2) a label with NO backing feed record (a phantom label);
--   (3) a `resolved` label whose true_entity_id is NOT a real E-01 master (a dangling resolution);
--   (4) an `exact_lei` label whose feed record carries NO LEI, or whose LEI does NOT match the
--       resolved master's LEI (the tier contradicts the data — the answer would be unreachable);
--   (5) a `name_variant_no_id` / `alias_match` label whose feed record DOES carry an LEI (the tier
--       claims a no-ID path but the data has an ID — a mislabelled tier);
--   (6) an `ambiguous`-outcome label that carries a true_entity_id, or a `new`/`ambiguous` label
--       whose feed record carries an LEI (a net-new/ambiguous case cannot have resolved to a master
--       and cannot carry a clean ID).
--
-- It is REVERT-SENSITIVE: drop a feed record (or its label), or mislabel a tier, and the relevant
-- CTE returns a row and this test FAILS. The labels are derived from the construction INTENT, never
-- read back from the feed — this invariant is what makes that claim checkable.

with feed as (
    select source_record_id, raw_lei, raw_name, raw_domicile
    from {{ ref('stg_entity_resolution_feed') }}
),

labels as (
    select source_record_id, true_entity_id, resolution_outcome, difficulty_tier
    from {{ ref('stg_entity_resolution_labels') }}
),

masters as (
    select entity_id, lei
    from {{ ref('stg_e01_legal_entity') }}
),

-- (1) an inbound feed record with no label
feed_unlabelled as (
    select
        f.source_record_id as detail,
        'feed-record-not-labelled' as failure
    from feed f
    left join labels l on f.source_record_id = l.source_record_id
    where l.source_record_id is null
),

-- (2) a label with no backing feed record
label_phantom as (
    select
        l.source_record_id as detail,
        'label-has-no-feed-record' as failure
    from labels l
    left join feed f on l.source_record_id = f.source_record_id
    where f.source_record_id is null
),

-- (3) a `resolved` label whose true_entity_id is not a real E-01 master
resolved_dangling as (
    select
        l.source_record_id as detail,
        'resolved-label-points-at-no-master' as failure
    from labels l
    left join masters m on l.true_entity_id = m.entity_id
    where l.resolution_outcome = 'resolved'
      and m.entity_id is null
),

-- (4) an `exact_lei` label whose feed record has no LEI, or whose LEI != the resolved master's LEI
exact_lei_inconsistent as (
    select
        l.source_record_id as detail,
        'exact_lei-tier-contradicts-the-data' as failure
    from labels l
    join feed f on l.source_record_id = f.source_record_id
    left join masters m on l.true_entity_id = m.entity_id
    where l.difficulty_tier = 'exact_lei'
      and (
            f.raw_lei is null or f.raw_lei = ''
            or m.lei is null or m.lei = ''
            or f.raw_lei <> m.lei
          )
),

-- (5) a no-ID tier (`name_variant_no_id` / `alias_match`) whose feed record nonetheless carries an LEI
no_id_tier_has_lei as (
    select
        l.source_record_id as detail,
        'no-id-tier-but-feed-record-carries-an-lei' as failure
    from labels l
    join feed f on l.source_record_id = f.source_record_id
    where l.difficulty_tier in ('name_variant_no_id', 'alias_match')
      and f.raw_lei is not null and f.raw_lei <> ''
),

-- (6) a net-new/ambiguous outcome that nonetheless resolved to a master, or carries an LEI
ambiguous_outcome_inconsistent as (
    select
        l.source_record_id as detail,
        'new-or-ambiguous-outcome-but-resolved-or-has-id' as failure
    from labels l
    join feed f on l.source_record_id = f.source_record_id
    where l.resolution_outcome in ('new', 'ambiguous')
      and (
            (l.true_entity_id is not null and l.true_entity_id <> '')
            or (f.raw_lei is not null and f.raw_lei <> '')
          )
)

select detail, failure from feed_unlabelled
union all
select detail, failure from label_phantom
union all
select detail, failure from resolved_dangling
union all
select detail, failure from exact_lei_inconsistent
union all
select detail, failure from no_id_tier_has_lei
union all
select detail, failure from ambiguous_outcome_inconsistent
