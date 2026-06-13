-- int_position_valuation — a holding (E-04) resolved to its current valuation (E-07)
-- and its asset class (E-09, via the instrument E-02). The position-level fact the
-- holdings mart and the NAV roll-up read.
--
-- GRAIN: one row per E-04 book-row — (position_id, book). E-04 is key-partitioned by
-- book (ADR-0022): a logical holding carries an IBOR row and an ABOR row that may
-- differ on market value / accrual. Both are kept here so a consumer can choose its
-- book (the NAV strike reads abor; the front office reads ibor).
--
-- THE VALUATION ATTACH IS BOOK-AGNOSTIC. E-07 has no `book` column — a mark is a
-- property of the logical holding (model/entities/core/E-07-valuation.md: the
-- valuation references position_id, the logical-holding identity shared across both
-- books, not the composite). So the valuation joins on position_id alone, and the
-- SAME current mark attaches to both the ibor and abor row of a holding. The
-- book-specific number on E-04 (market_value_usd) can diverge from the mark; both are
-- carried (e04_market_value_usd vs current_valuation_usd) so the consumer is explicit.
--
-- THE ASSET-CLASS JOIN IS integer = integer. The asset class reaches the holding via
-- the instrument (E-02.asset_class, an int FK -> E-09.asset_class_key, an int PK). The
-- predicate is instrument.asset_class = asset_class.asset_class_key — integer =
-- integer, valid on postgres. NOT the varchar = integer predicate postgres rejects.
--
-- THE AS-OF PATH IS PRESERVED. This model carries the CURRENT-knowledge valuation
-- (what the firm believes now), via int_e07_valuation_current. The as-of-knowledge
-- (past-strike) path is int_e07_valuation_versioned (system-time bounds) — the NAV
-- mart reads it directly to strike a past NAV, so the bi-temporal axis is not lost
-- by collapsing to current here.

with holdings as (
    select
        position_id,
        book,
        portfolio_id,
        instrument_id,
        as_of_date,
        quantity,
        commitment_usd,
        cost_basis_usd,
        market_value_usd as e04_market_value_usd,
        accrued_income_usd,
        currency
    from {{ ref('stg_e04_holding_position') }}
),

instruments as (
    select
        instrument_id,
        instrument_name,
        instrument_class,
        asset_class as asset_class_key   -- int FK -> E-09 (integer = integer)
    from {{ ref('stg_e02_instrument_asset') }}
),

asset_classes as (
    select
        asset_class_key,                 -- int PK
        asset_class_code,
        asset_class_label,
        markets
    from {{ ref('stg_e09_asset_class') }}
),

-- The CURRENT-knowledge mark per holding: the latest-recorded value at the holding's
-- most recent valuation_date. int_e07_valuation_current is already
-- one-current-per-(position_id, valuation_date); we pick the latest valuation_date.
current_valuation as (
    select
        position_id,
        value_usd          as current_valuation_usd,
        valuation_date     as current_valuation_date,
        method             as valuation_method,
        valuation_level,
        source             as valuation_source,
        confidence_score   as valuation_confidence
    from (
        select
            position_id,
            value_usd,
            valuation_date,
            method,
            valuation_level,
            source,
            confidence_score,
            row_number() over (
                partition by position_id
                order by valuation_date desc, valuation_id desc
            ) as rn
        from {{ ref('int_e07_valuation_current') }}
    ) ranked
    where rn = 1
)

select
    h.position_id,
    h.book,
    h.portfolio_id,
    h.instrument_id,
    i.instrument_name,
    i.instrument_class,
    i.asset_class_key,
    ac.asset_class_code,
    ac.asset_class_label,
    ac.markets                 as asset_class_markets,
    h.as_of_date,
    h.quantity,
    h.commitment_usd,
    h.cost_basis_usd,
    h.e04_market_value_usd,
    h.accrued_income_usd,
    h.currency,
    cv.current_valuation_usd,
    cv.current_valuation_date,
    cv.valuation_method,
    cv.valuation_level,
    cv.valuation_source,
    cv.valuation_confidence
from holdings h
left join instruments i
    on h.instrument_id = i.instrument_id
left join asset_classes ac
    on i.asset_class_key = ac.asset_class_key            -- integer = integer
left join current_valuation cv
    on h.position_id = cv.position_id                    -- book-agnostic attach
