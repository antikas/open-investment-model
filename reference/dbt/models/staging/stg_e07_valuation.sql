-- stg_e07_valuation — E-07 Valuation (model/entities/core/E-07-valuation.md).
--
-- A point-in-time value of a holding, with how it was arrived at. A 1:1 typed
-- staging view over raw_e07_valuation, column-faithful to the model file's
-- Attribute schema.
--
-- APPEND-ONLY / AS-OF GRAIN: the model file declares E-07 append-only — the set
-- of valuations for a holding is its value trajectory; a restatement for a prior
-- `valuation_date` is a NEW row, never an overwrite (the seed shows POS-0005 with
-- two manager_mark rows on different dates AND a same-date mark_to_model row — the
-- multi-mark trajectory). The bi-temporal GRAIN is declared here:
--   grain = (valuation_id) primary key; as-of axis = valuation_date.
--
-- ** MATERIALISATION IS AN OIM-110 COORDINATION POINT — NOT PICKED HERE. **
-- This staging model is a view (the staging default), NOT a dbt snapshot or an
-- incremental model. Whether the as-of/append-only entities materialise as dbt
-- snapshots (SCD-2), incremental appends, or views over an append-only seed is
-- the OIM-110 bi-temporal-materialisation decision (OIM-102 P-R4 carry-forward).
-- This cycle DECLARES the grain (the columns + this note) and seeds flat; it does
-- NOT silently inherit OIM-102's flat drop-recreate as the forever strategy.
--
-- Parity-aware SQL: `decimal(18,2)` for `value_usd` (NOT `double`);
-- `double precision` for `confidence_score` (the model's only `float` column —
-- `double precision` renders on both duckdb and postgres, unlike duckdb's bare
-- `double`). `varchar`/`date` casts are portable. No duckdb-only idiom.

with source as (
    select * from {{ ref('raw_e07_valuation') }}
)

select
    cast(valuation_id     as varchar)          as valuation_id,
    cast(position_id      as varchar)          as position_id,
    cast(instrument_id    as varchar)          as instrument_id,
    cast(valuation_date   as date)             as valuation_date,
    cast(value_usd        as decimal(18, 2))   as value_usd,
    cast(method           as varchar)          as method,
    cast(valuation_level  as varchar)          as valuation_level,
    cast(source           as varchar)          as source,
    cast(confidence_score as double precision) as confidence_score
from source
