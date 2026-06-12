-- int_e07_valuation_versioned — the E-07 bi-temporal log with system-time BOUNDS.
--
-- Reads the append-only log (int_e07_valuation_bitemporal) and derives the
-- system-time (knowledge) validity interval per mark, over the FULL log:
--
--   system_valid_from  : when this mark was recorded (from the log).
--   system_valid_to    : when it was superseded — the recorded_at of the NEXT mark for
--                         the same (position_id, valuation_date); null = still current.
--   is_current_knowledge: true for the latest-recorded mark of each (position_id,
--                         valuation_date) — what the firm believes the value is NOW.
--
-- This is a VIEW (cheap; the staging default), correct after an incremental append
-- because the window is computed over the whole log, not just the new rows. It is the
-- bi-temporal access surface:
--   * current value         : where is_current_knowledge  (see int_e07_valuation_current)
--   * value as-of a KNOWLEDGE date K (what we believed on K):
--        where system_valid_from <= K and (system_valid_to is null or K < system_valid_to)
--   * value as-of a BUSINESS date (valid-time) is just valuation_date <= D.
-- Both axes are queryable — genuinely bi-temporal.

with bounded as (
    select
        valuation_id,
        position_id,
        valuation_date,
        value_usd,
        method,
        valuation_level,
        source,
        confidence_score,
        system_valid_from,
        lead(system_valid_from) over (
            partition by position_id, valuation_date
            order by system_valid_from, valuation_id
        ) as system_valid_to
    from {{ ref('int_e07_valuation_bitemporal') }}
)

select
    valuation_id,
    position_id,
    valuation_date,
    value_usd,
    method,
    valuation_level,
    source,
    confidence_score,
    system_valid_from,
    system_valid_to,
    (system_valid_to is null) as is_current_knowledge
from bounded
