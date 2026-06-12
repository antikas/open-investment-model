-- stg_e20_performance_result — E-20 Performance Result (model/entities/core/E-20-performance-result.md).
--
-- A stored point-in-time return figure with inputs, methodology version and
-- provenance. A 1:1 typed staging view over raw_e20_performance_result,
-- column-faithful to the model file's Attribute schema. Single owner (SD-09.1).
--
-- APPEND-ONLY / AS-OF PERIOD GRAIN: the model file declares E-20 append-only (the
-- performance analogue of E-07/E-19; a recomputed return for a prior period is a
-- NEW row — GIPS verification needs the as-struck figure preserved). The bi-temporal
-- GRAIN is declared:
--   grain = (performance_result_id) primary key; as-of period = (period_start, period_end).
--
-- ** MATERIALISATION IS AN OIM-110 COORDINATION POINT — NOT PICKED HERE. ** A flat
-- staging view, NOT a snapshot/incremental model; the strategy is OIM-110's.
--
-- Parity-aware SQL: `decimal(18,8)` for the `return_value` rate (a return is a
-- rate, so more fractional precision than money — NOT `double`); `double precision`
-- for the `float` `confidence_score`; `varchar`/`date` for the rest. All portable
-- across duckdb and postgres. No duckdb-only idiom.

with source as (
    select * from {{ ref('raw_e20_performance_result') }}
)

select
    cast(performance_result_id as varchar)          as performance_result_id,
    cast(subject_type          as varchar)          as subject_type,
    cast(subject_id            as varchar)          as subject_id,
    cast(period_start          as date)             as period_start,
    cast(period_end            as date)             as period_end,
    cast(return_basis          as varchar)          as return_basis,
    cast(return_method         as varchar)          as return_method,
    cast(return_value          as decimal(18, 8))   as return_value,
    cast(currency              as varchar)          as currency,
    cast(metric_definition_id  as varchar)          as metric_definition_id,
    cast(composite_id          as varchar)          as composite_id,
    cast(valuation_source      as varchar)          as valuation_source,
    cast(confidence_score      as double precision) as confidence_score
from source
