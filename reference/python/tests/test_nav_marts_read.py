"""Tests for the NAV-strike workflow's marts read (``nav_marts_read``).

Two surfaces:

1. The §A1 IDENTITY over the real ``mart_fund_nav`` — for every seed fund, the read returns
   components whose ``gross_market_value + accrued_income - fees`` equals the mart's published
   ``nav_usd`` to the penny. This is the data foundation the TS workflow's roll-up reconciles
   to. SKIPS cleanly if the canonical store is not provisioned (duckdb missing or the marts
   unbuilt) — the same skip-guard ``marts.py``'s integration reads use, so the unit suite runs
   without the data toolchain.
2. The PAST-AS-OF BOUND — a non-null ``nav_knowledge_date`` is REFUSED (a
   ``MartsUnavailableError``), so the workflow can never silently strike an unsound past
   NAV on the latest-holdings path. This needs no store (the refusal is checked before any read).

Honest boundary: a green identity here proves the data-layer arithmetic, NOT a struck
production NAV (oracle-anchored production is the named arc).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from agentinvest_demo.marts import MartsUnavailableError
from agentinvest_demo.nav_marts_read import (
    list_fund_ids,
    read_fund_holdings_gross,
    read_fund_nav_components,
)


def _store_available() -> bool:
    """True iff the canonical store can be read (duckdb installed + the marts built)."""
    try:
        list_fund_ids()
    except MartsUnavailableError:
        return False
    return True


pytestmark = pytest.mark.filterwarnings("ignore")


def test_past_as_of_strike_is_refused() -> None:
    """A past-as-of knowledge date is REFUSED — never a silently-struck unsound NAV.

    The latest-holdings path cannot soundly strike a past NAV (unbounded constituent-set error
    on real holding history), so the reader refuses a non-null date before any read. This needs
    no store.
    """
    with pytest.raises(MartsUnavailableError) as exc:
        read_fund_nav_components("PF-0003", nav_knowledge_date="2025-03-31")
    assert "past-as-of" in str(exc.value).lower()
    assert "holding history" in str(exc.value).lower()


@pytest.mark.skipif(not _store_available(), reason="store not provisioned")
def test_nav_components_satisfy_the_a1_identity_for_every_seed_fund() -> None:
    """For every seed fund, gross_market_value + accrued_income − fees == mart nav_usd (§A1).

    The components the workflow checkpoints reconcile, by construction, to the mart's published
    NAV — the invariant the TS roll-up step asserts to the penny.
    """
    fund_ids = list_fund_ids()
    assert fund_ids, "expected at least one fund in mart_fund_nav"
    for fund_id in fund_ids:
        c = read_fund_nav_components(fund_id)
        rolled_up = c.gross_market_value + c.accrued_income - c.fees
        assert rolled_up == c.nav_usd, (
            f"{fund_id}: roll-up {rolled_up} != mart nav_usd {c.nav_usd} "
            f"(gross={c.gross_market_value} accruals={c.accrued_income} fees={c.fees})"
        )
        # Per-fund single-class on this seed (no share classes).
        assert c.share_class is None
        # The NAV is positive and the position count is real.
        assert c.nav_usd > Decimal(0)
        assert c.n_positions > 0


@pytest.mark.skipif(not _store_available(), reason="store not provisioned")
def test_unknown_fund_is_a_clean_error() -> None:
    """An unknown fund id is a clear ``MartsUnavailableError`` (not a silent None)."""
    with pytest.raises(MartsUnavailableError) as exc:
        read_fund_nav_components("PF-9999")
    assert "PF-9999" in str(exc.value)


@pytest.mark.skipif(not _store_available(), reason="store not provisioned")
def test_holdings_gross_reconciles_to_nav_mart_gross_for_every_fund() -> None:
    """The GENUINE cross-mart reconcile: Σ holdings mart gross == mart_fund_nav.gross_market_value.

    ``read_fund_holdings_gross`` rolls the fund's gross up from the HOLDINGS mart — an INDEPENDENT
    mart and SQL path from ``mart_fund_nav``'s gross. The two must tie (the
    ``assert_marts_reconcile_holdings_to_nav`` invariant). This is the FALSIFIABLE check the
    workflow's roll-up runs, NOT a within-row X==X re-read.
    """
    fund_ids = list_fund_ids()
    assert fund_ids, "expected at least one fund"
    for fund_id in fund_ids:
        nav = read_fund_nav_components(fund_id)
        hold = read_fund_holdings_gross(fund_id)
        assert hold.fund_id == fund_id
        assert hold.n_positions > 0
        # The independent holdings roll-up ties to the NAV mart's gross (two marts, two paths).
        assert hold.holdings_gross_market_value == nav.gross_market_value, (
            f"{fund_id}: holdings gross {hold.holdings_gross_market_value} != "
            f"mart_fund_nav gross {nav.gross_market_value}"
        )


@pytest.mark.skipif(not _store_available(), reason="store not provisioned")
def test_unknown_fund_holdings_is_a_clean_error() -> None:
    """An unknown fund to the holdings roll-up is a clear error (not a silent zero gross)."""
    with pytest.raises(MartsUnavailableError) as exc:
        read_fund_holdings_gross("PF-9999")
    assert "PF-9999" in str(exc.value)
