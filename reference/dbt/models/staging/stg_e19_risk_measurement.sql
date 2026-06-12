-- stg_e19_risk_measurement — E-19 Risk Measurement (model/entities/core/E-19-risk-measurement.md).
--
-- A point-in-time risk result with its method and provenance. A 1:1 typed staging
-- view over raw_e19_risk_measurement, column-faithful to the model file's
-- Attribute schema.
--
-- APPEND-ONLY / AS-OF GRAIN: the model file declares E-19 append-only (the risk
-- analogue of E-07; a re-run for a prior date is a NEW row — the seed shows the
-- total-fund VaR at two as-of dates). The bi-temporal GRAIN is declared:
--   grain = (measurement_id) primary key; as-of axis = as_of_date.
--
-- ** MATERIALISATION IS AN OIM-110 COORDINATION POINT — NOT PICKED HERE. ** As
-- with E-07, this is a flat staging view, NOT a dbt snapshot/incremental model;
-- the snapshot-vs-incremental decision is OIM-110's.
--
-- KEY-PARTITIONED by `risk_type` (ADR-0022 / ownership-map): the model file's
-- Attribute schema now carries the `risk_type` column — the risk *domain* (market
-- / credit / counterparty / liquidity / concentration / scenario / stress /
-- climate) that determines the single producing capability. `measure_type` (the
-- *kind of number* — var / exposure / stress_loss / ...) is the orthogonal axis
-- and is kept alongside. Both columns are realised here, column-faithful.
--
-- Parity-aware SQL: `decimal(18,2)` for `value` (NOT `double`);
-- `double precision` for the `float` `confidence_score`; `varchar`/`date` for the
-- rest. All portable across duckdb and postgres. No duckdb-only idiom.

with source as (
    select * from {{ ref('raw_e19_risk_measurement') }}
)

select
    cast(measurement_id   as varchar)          as measurement_id,
    cast(risk_type        as varchar)          as risk_type,
    cast(subject_type     as varchar)          as subject_type,
    cast(subject_id       as varchar)          as subject_id,
    cast(measure_type     as varchar)          as measure_type,
    cast(as_of_date       as date)             as as_of_date,
    cast(value            as decimal(28, 8))   as value,
    cast(currency         as varchar)          as currency,
    cast(method           as varchar)          as method,
    cast(scenario_id      as varchar)          as scenario_id,
    cast(model_id         as varchar)          as model_id,
    cast(confidence_score as double precision) as confidence_score
from source
