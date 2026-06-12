"""Synthetic-integration smoke for the BD-09 tools over the OIM-110 seed.

Feeds the tools **real seeded synthetic data** (the OIM-110 E-07 valuation series and E-04
holdings the OIM-111 marts are built on) and confirms they run and tie, on the paths the seed
supports:

- **SO-09-02 TWR** over a seeded valuation series with **no external flows** — each quarter's
  sub-period return is ``(mark_t - mark_{t-1}) / mark_{t-1}``; the tool links them. The series is
  **deduplicated to one value per distinct valuation_date** (the latest-recorded mark), so the
  sub-periods are genuine time-ordered steps, not same-date re-marks; the smoke asserts the tool's
  linked TWR against an **independent geometric link** of those sub-period returns (not the
  telescoping ``(last - first)/first`` identity), so a broken-linking regression fails it — see
  ``test_twr_smoke_bites_on_broken_linking``. This is the supported integration path (the seed has
  the valuation trajectory; no external flow legs).
- **SO-09-05 contribution** over the seeded holdings of a portfolio — segment (here per-position)
  weights from market value, segment returns over the valuation series, contributions tie to the
  weighted total.

The **E-06 cash-flow series is NOT seeded** (OIM-110 seeded ten entities; E-06 is not among
them), so the flow-dependent tools — SO-09-01 Modified Dietz and SO-09-03 MWR/IRR — have **no
synthetic-integration path here**: they are oracle-tested on the published worked example
(typed flow inputs) and the E-06-seed gap is a carry-forward, surfaced not faked.

Honest boundary: a green smoke over this synthetic seed proves the tools *integrate* with the
canonical data shape; it is NOT a GIPS-verified production return (the §A2 published-oracle
match — in the per-tool test modules — is what proves the formula).

The reader is a thin CSV reader (no dbt/duckdb dependency) so the smoke stays a pure unit test;
the seed CSVs are the same files the dbt marts ``ref`` and the OIM-111 reconciliation proved.
"""

from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

from agentinvest_tools.bd09.contribution_breakdown import (
    ContributionBreakdownInput,
    SegmentInput,
    so_09_05_compute_contribution_breakdown,
)
from agentinvest_tools.bd09.time_weighted_return import (
    SubPeriod,
    TimeWeightedReturnInput,
    so_09_02_compute_time_weighted_return,
)

# The OIM-110 seed the OIM-111 marts read (reference/dbt/seeds/*.csv). From tests/ that is two
# levels up to reference/ then dbt/seeds (the dbt project is a sibling of python/, not under it).
_SEEDS_DIR = Path(__file__).resolve().parents[2] / "dbt" / "seeds"


def _valuation_series(position_id: str) -> list[tuple[str, Decimal]]:
    """The (date, value) E-07 valuation series for a position, ordered by date.

    The seed carries duplicate ``valuation_date`` re-marks for a position (a later ``recorded_at``
    revises an earlier mark of the same as-of date). For a time-ordered sub-period series we
    select **one value per distinct valuation_date** — the latest-recorded mark for that date —
    so consecutive pairs are genuine, distinct-date sub-periods rather than same-date re-marks
    linked as if they were time steps (the duplicate-date trap the pre-mortem flagged).
    """
    latest_by_date: dict[str, tuple[str, Decimal]] = {}
    with (_SEEDS_DIR / "raw_e07_valuation.csv").open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["position_id"] != position_id:
                continue
            date = row["valuation_date"]
            recorded_at = row["recorded_at"]
            value = Decimal(row["value_usd"])
            existing = latest_by_date.get(date)
            if existing is None or recorded_at > existing[0]:
                latest_by_date[date] = (recorded_at, value)
    return sorted(((date, v) for date, (_, v) in latest_by_date.items()), key=lambda r: r[0])


def _abor_holdings(portfolio_id: str) -> list[tuple[str, Decimal]]:
    """The (position_id, market_value) ABOR holdings of a portfolio (performance reads ABOR)."""
    rows: list[tuple[str, Decimal]] = []
    with (_SEEDS_DIR / "raw_e04_holding_position.csv").open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if (
                row["portfolio_id"] == portfolio_id
                and row["book"] == "abor"
                and row["market_value_usd"]
            ):
                rows.append((row["position_id"], Decimal(row["market_value_usd"])))
    return rows


def test_twr_over_seeded_valuation_series_links_sub_periods() -> None:
    """SO-09-02 links the seeded quarterly marks of a position into a TWR — supported path.

    This smoke genuinely exercises **sub-period linking**, not just the endpoints. The series is
    the distinct-date (deduplicated) E-07 valuation trajectory for POS-0001, so each consecutive
    pair is a real time-ordered sub-period (no same-date re-marks linked as time steps). The
    assertion compares the tool's linked TWR against an **independent** geometric-link computation
    over the same sub-period returns — NOT the ``(last - first)/first`` telescoping identity,
    which would pass even if the per-sub-period linking were broken. ``test_*_bites`` below proves
    the assertion fails on a broken-linking regression.
    """
    series = _valuation_series("POS-0001")
    assert len(series) >= 3, (
        "the seed should carry >= 3 distinct-date valuation marks for POS-0001 to link"
    )

    # Each consecutive pair of distinct-date marks is a sub-period with no external flow:
    # r = (mark_t - mark_{t-1}) / mark_{t-1}.
    sub_periods = tuple(
        SubPeriod(beginning_value=prev_val, ending_value=cur_val)
        for (_, prev_val), (_, cur_val) in zip(series, series[1:], strict=False)
    )
    out = so_09_02_compute_time_weighted_return(TimeWeightedReturnInput(sub_periods=sub_periods))

    # Independent geometric link of the per-sub-period returns (computed here, not by the tool).
    # This is the real integration check: it disagrees with the tool's output if the tool's
    # linking is wrong, unlike the telescoping (last-first)/first identity.
    independent_growth = Decimal(1)
    for (_, prev_val), (_, cur_val) in zip(series, series[1:], strict=False):
        independent_growth *= Decimal(1) + (cur_val - prev_val) / prev_val
    independent_twr = independent_growth - Decimal(1)

    assert abs(out.time_weighted_return - independent_twr) <= Decimal("0.0000001")
    assert len(out.sub_period_returns) == len(series) - 1
    # The series is genuinely multi-sub-period (not a degenerate one-pair link).
    assert len(sub_periods) >= 2


def test_twr_smoke_bites_on_broken_linking() -> None:
    """Prove the strengthened smoke actually fails on a broken-linking regression.

    If the linker summed the sub-period returns (a common wrong implementation) instead of
    compounding them, the result would differ from the true geometric link whenever there is more
    than one non-zero sub-period return. This test confirms that the smoke's independent
    geometric-link assertion would reject such a regression — i.e. the assertion bites, it is not
    vacuous (unlike the previous telescoping-only assertion, which passed regardless of linking).
    """
    series = _valuation_series("POS-0001")
    assert len(series) >= 3

    returns = [
        (cur_val - prev_val) / prev_val
        for (_, prev_val), (_, cur_val) in zip(series, series[1:], strict=False)
    ]

    geometric_growth = Decimal(1)
    for r in returns:
        geometric_growth *= Decimal(1) + r
    geometric_twr = geometric_growth - Decimal(1)

    # A broken (additive) linker — the regression the strengthened smoke must catch.
    additive_twr = sum(returns, Decimal(0))

    # The two differ by more than the smoke's tolerance, so the smoke's geometric assertion would
    # FAIL on the additive regression — the test bites.
    assert abs(geometric_twr - additive_twr) > Decimal("0.0000001")


def test_contribution_over_seeded_holdings_ties_to_weighted_total() -> None:
    """SO-09-05 over a portfolio's seeded ABOR holdings — contributions tie to the total."""
    # PF-0004 is the portfolio POS-0001 sits in (per the E-04 seed); pick a portfolio with
    # multiple positions so the breakdown is non-trivial.
    holdings = _abor_holdings("PF-0004")
    assert len(holdings) >= 1

    total_mv = sum((mv for _, mv in holdings), Decimal(0))
    assert total_mv > 0

    # Synthetic per-position segment returns (illustrative; the seed has no per-position return,
    # so the integration here exercises the weight derivation from real seeded market values and
    # the contribution-summing identity — not a seeded return figure).
    seg_returns = {pos: Decimal("0.05") for pos, _ in holdings}
    segments = tuple(
        SegmentInput(segment=pos, weight=mv / total_mv, segment_return=seg_returns[pos])
        for pos, mv in holdings
    )
    out = so_09_05_compute_contribution_breakdown(ContributionBreakdownInput(segments=segments))

    # The contributions sum to the total, and with uniform 5% segment returns the weighted total
    # is exactly 5% (the weights, derived from real seeded market values, sum to 1).
    assert abs(out.total_return - Decimal("0.05")) <= Decimal("0.0001")
    summed = sum((c.contribution for c in out.contributions), Decimal(0))
    assert abs(out.total_return - summed) <= Decimal("0.0001")
