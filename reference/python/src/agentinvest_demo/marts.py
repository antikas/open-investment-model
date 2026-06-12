"""The demo's canonical-data reader — queries the dbt-built marts for the task inputs.

This is the **data** end of the pipeline. It reads the canonical store the dbt marts are
materialised into and derives, for one fund over one window:

- the per-asset-class **begin** and **end** market value (the segment NAV deltas), from the
  holdings mart (``mart_portfolio_holdings`` — the asset-class axis and the position→fund
  mapping) joined to the canonical valuation series at the two window dates;
- the **fund** begin and end NAV (the sum over its segments), used as the total-return inputs;
- a cross-check against the published ``mart_fund_nav`` so the derived end NAV is tied to the
  fund-NAV mart, not only the underlying series.

Why the valuation **series** and not only the two marts: ``mart_fund_nav`` and
``mart_portfolio_holdings`` are *point-in-time* surfaces (the current strike, or one as-of
knowledge date per build). A return over a window needs the value at **two** dates, which the
canonical valuation series carries (a monthly mark trajectory per holding) and a single
point-in-time mart cannot. The reader therefore reads the holdings mart for the segmentation
and the canonical valuation data for the begin/end values, and asserts the derived end NAV
equals ``mart_fund_nav``'s — so the window endpoints reconcile to the published fund-NAV mart.

Store location: the duckdb file path is resolved from ``AGENTINVEST_DUCKDB_PATH`` when set
(the launcher / CI override), else from the checkout-keyed default the data-layer launchers use
(``~/.local/share/agentinvest/duckdb/canonical-<token>.duckdb``, the token a stable hash of the
repo-root path). The path is never hard-coded.

``duckdb`` is imported lazily inside the connect helper so importing this module does not require
the data toolchain — a caller without the duckdb dependency installed gets a clear, catchable
error only when it actually tries to read the store (which is what lets the integration test
skip cleanly when the data layer is not provisioned).
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

# The two window endpoints the demo measures the return over. A clean one-year window on the
# synthetic monthly mark trajectory (the seed carries marks from 2024-04-30 to 2026-03-31); the
# end date is the latest mark, so the derived end NAV equals the current-strike fund-NAV mart.
DEFAULT_BEGIN_DATE = "2025-03-31"
DEFAULT_END_DATE = "2026-03-31"

# The default fund the demo runs for when none is named: the multi-asset fund, which carries the
# richest asset-class spread (six segments) so the contribution breakdown is non-trivial.
DEFAULT_FUND_ID = "PF-0003"


class MartsUnavailableError(RuntimeError):
    """The canonical store cannot be read — duckdb missing, the file absent, or the marts unbuilt.

    Raised with an actionable message so the caller (the CLI, or the integration test's skip
    guard) can distinguish "the data layer is not provisioned" (run ``pnpm dbt:build``) from a
    genuine query failure.
    """


@dataclass(frozen=True)
class SegmentNav:
    """One asset-class segment's begin/end market value and derived weight + return.

    ``weight`` is the segment's share of the fund's *begin* NAV; ``segment_return`` is the
    segment's own return over the window. ``weight * segment_return`` is its contribution to the
    fund total return, and the contributions sum to the total by construction (a single
    underlying per-segment NAV-delta derivation feeds both the total-return and the
    contribution-breakdown inputs).
    """

    asset_class_code: str
    asset_class_label: str
    begin_market_value: Decimal
    end_market_value: Decimal
    weight: Decimal
    segment_return: Decimal


@dataclass(frozen=True)
class FundWindowData:
    """The derived inputs for one fund over one window — the data feeding both tool calls."""

    fund_id: str
    fund_name: str
    begin_date: str
    end_date: str
    period_days: int
    begin_nav: Decimal
    end_nav: Decimal
    mart_fund_nav: Decimal
    segments: tuple[SegmentNav, ...]


def _repo_root_token(repo_root: Path) -> str:
    """The checkout-keyed token the data-layer launchers use — sha256 of the repo-root path.

    Mirrors ``agentinvest_repo_token`` in ``scripts/lib/agentinvest-venv-path.sh`` (the SSOT for
    the keyed-store path): a stable 12-char hex prefix of the sha256 of the absolute repo-root
    path string, so two checkouts get distinct stores and a re-run from the same checkout reuses
    one. Only used when ``AGENTINVEST_DUCKDB_PATH`` is unset.
    """
    return hashlib.sha256(str(repo_root).encode("utf-8")).hexdigest()[:12]


def _default_duckdb_path() -> Path:
    """The checkout-keyed default duckdb path, matching the data-layer launcher convention.

    Resolves the repo root from this file's location (``reference/python/src/agentinvest_demo`` →
    up four to the repo root) and keys the store on it, under the same
    ``~/.local/share/agentinvest/duckdb`` parent the launchers write. ``AGENTINVEST_VENV_PARENT``
    overrides the parent (the launcher honours it too).
    """
    repo_root = Path(__file__).resolve().parents[4]
    parent = os.environ.get("AGENTINVEST_VENV_PARENT")
    base = Path(parent) if parent else Path.home() / ".local" / "share" / "agentinvest"
    return base / "duckdb" / f"canonical-{_repo_root_token(repo_root)}.duckdb"


def resolve_duckdb_path() -> Path:
    """Resolve the canonical duckdb file path — the env override, else the checkout-keyed default.

    ``AGENTINVEST_DUCKDB_PATH`` (set by the launchers / a CI runner) wins; otherwise the
    checkout-keyed default. Never hard-coded.
    """
    override = os.environ.get("AGENTINVEST_DUCKDB_PATH")
    if override:
        return Path(override)
    return _default_duckdb_path()


def _connect(path: Path):  # type: ignore[no-untyped-def]  # duckdb is an optional data-layer dep
    """Open a read-only connection to the canonical store, or raise ``MartsUnavailableError``.

    duckdb is imported here (not at module import) so this module imports without the data
    toolchain; the import error is turned into a clear, catchable ``MartsUnavailableError``.
    """
    try:
        import duckdb  # noqa: PLC0415 - lazy: the data toolchain is an optional layer
    except ImportError as exc:  # pragma: no cover - exercised only without the dbt dep group
        raise MartsUnavailableError(
            "the 'duckdb' package is not installed — install the data toolchain "
            "(uv sync --group dbt) to read the canonical marts"
        ) from exc

    if not path.exists():
        raise MartsUnavailableError(
            f"the canonical store does not exist at {path} — build it first "
            f"(pnpm dbt:build, from reference/)"
        )
    try:
        return duckdb.connect(str(path), read_only=True)
    except Exception as exc:  # pragma: no cover - genuine connect failure
        raise MartsUnavailableError(f"could not open the canonical store at {path}: {exc}") from exc


def list_funds(duckdb_path: Path | None = None) -> list[tuple[str, str]]:
    """Return the ``(fund_id, fund_name)`` pairs present in ``mart_fund_nav``, ordered by id."""
    path = duckdb_path or resolve_duckdb_path()
    con = _connect(path)
    try:
        rows = con.execute(
            "select fund_id, fund_name from main_marts.mart_fund_nav order by fund_id"
        ).fetchall()
    finally:
        con.close()
    return [(str(r[0]), str(r[1])) for r in rows]


def _days_between(begin_date: str, end_date: str) -> int:
    """The day count of the window — the Modified-Dietz weighting denominator (period_days)."""
    from datetime import date  # noqa: PLC0415 - tiny local use

    begin = date.fromisoformat(begin_date)
    end = date.fromisoformat(end_date)
    days = (end - begin).days
    if days <= 0:
        raise ValueError(f"end date {end_date} must be after begin date {begin_date}")
    return days


def read_fund_window(
    fund_id: str = DEFAULT_FUND_ID,
    begin_date: str = DEFAULT_BEGIN_DATE,
    end_date: str = DEFAULT_END_DATE,
    duckdb_path: Path | None = None,
) -> FundWindowData:
    """Derive the per-segment + fund begin/end NAV for ``fund_id`` over the window, from the marts.

    The single SQL join is the data derivation both tool calls draw on:

    - ``mart_portfolio_holdings`` supplies the **segmentation** (each abor position's
      ``asset_class_code`` / ``asset_class_label``) and the position→fund mapping;
    - the canonical valuation series supplies each position's **begin** and **end** market value
      at the two window dates;
    - the per-asset-class begin/end market values are the segment NAV deltas; their sums are the
      fund begin/end NAV.

    From these: the fund total return is ``(end_nav - begin_nav) / begin_nav`` (no external
    flows); each segment's weight is ``segment_begin / fund_begin`` and its return is
    ``(segment_end - segment_begin) / segment_begin``. The cross-check asserts the derived
    ``end_nav`` equals ``mart_fund_nav``'s ``gross_market_value`` — tying the window end to the
    published fund-NAV mart. A position missing a mark at either endpoint is a hard error (the
    derivation must be over a complete constituent set, not a silent partial).
    """
    path = duckdb_path or resolve_duckdb_path()
    period_days = _days_between(begin_date, end_date)
    con = _connect(path)
    try:
        # Guard: every position in the fund must be valued at BOTH window endpoints, else the
        # begin/end NAV would silently omit a holding (a constituent-set error). Fail loud.
        missing = con.execute(
            """
            select count(*)
            from (
                select position_id from main_marts.mart_portfolio_holdings where fund_id = ?
            ) s
            left join (
                select position_id from main_intermediate.int_e07_valuation_current
                where valuation_date = ?
            ) vb using (position_id)
            left join (
                select position_id from main_intermediate.int_e07_valuation_current
                where valuation_date = ?
            ) ve using (position_id)
            where vb.position_id is null or ve.position_id is null
            """,
            [fund_id, begin_date, end_date],
        ).fetchone()
        if missing is None:
            raise MartsUnavailableError(f"no holdings found for fund {fund_id}")
        if int(missing[0]) > 0:
            raise MartsUnavailableError(
                f"{missing[0]} position(s) in {fund_id} lack a mark at {begin_date} or "
                f"{end_date}; the window endpoints must cover the full constituent set"
            )

        seg_rows = con.execute(
            """
            with seg as (
                select position_id, asset_class_code, asset_class_label
                from main_marts.mart_portfolio_holdings
                where fund_id = ?
            ),
            valb as (
                select position_id, value_usd
                from main_intermediate.int_e07_valuation_current
                where valuation_date = ?
            ),
            vale as (
                select position_id, value_usd
                from main_intermediate.int_e07_valuation_current
                where valuation_date = ?
            )
            select
                s.asset_class_code,
                s.asset_class_label,
                sum(vb.value_usd) as begin_mv,
                sum(ve.value_usd) as end_mv
            from seg s
            join valb vb on s.position_id = vb.position_id
            join vale ve on s.position_id = ve.position_id
            group by s.asset_class_code, s.asset_class_label
            order by s.asset_class_code
            """,
            [fund_id, begin_date, end_date],
        ).fetchall()

        if not seg_rows:
            raise MartsUnavailableError(
                f"no segment data derived for fund {fund_id} — is the fund id correct and the "
                f"store built (pnpm dbt:build)?"
            )

        fund_row = con.execute(
            "select fund_name, gross_market_value from main_marts.mart_fund_nav where fund_id = ?",
            [fund_id],
        ).fetchone()
        if fund_row is None:
            raise MartsUnavailableError(f"fund {fund_id} is not present in mart_fund_nav")
        fund_name = str(fund_row[0])
        mart_fund_nav = Decimal(str(fund_row[1]))
    finally:
        con.close()

    begin_nav = sum((Decimal(str(r[2])) for r in seg_rows), Decimal(0))
    end_nav = sum((Decimal(str(r[3])) for r in seg_rows), Decimal(0))
    if begin_nav == 0:
        raise MartsUnavailableError(
            f"fund {fund_id} has a zero begin NAV at {begin_date} — the return is undefined"
        )

    segments = tuple(
        SegmentNav(
            asset_class_code=str(code),
            asset_class_label=str(label),
            begin_market_value=Decimal(str(begin_mv)),
            end_market_value=Decimal(str(end_mv)),
            weight=Decimal(str(begin_mv)) / begin_nav,
            segment_return=(Decimal(str(end_mv)) - Decimal(str(begin_mv))) / Decimal(str(begin_mv)),
        )
        for code, label, begin_mv, end_mv in seg_rows
    )

    return FundWindowData(
        fund_id=fund_id,
        fund_name=fund_name,
        begin_date=begin_date,
        end_date=end_date,
        period_days=period_days,
        begin_nav=begin_nav,
        end_nav=end_nav,
        mart_fund_nav=mart_fund_nav,
        segments=segments,
    )
