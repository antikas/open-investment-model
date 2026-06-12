"""The end-to-end analytics demo — the multi-step task, orchestrated as one pipeline.

Composes the data reader (``marts``) and the substrate dispatcher (``restate_client``) into one
runnable task: for a chosen fund over a window, compute the total return, then break it down by
asset class, and reconcile the breakdown back to the total return.

The orchestration is **hand-coded** and **explicit**: it calls the two *named* operations
(``SO-09-01`` then ``SO-09-05``) in sequence. It does not decide which operations to call — there
is no planning loop here. That deciding loop is a separate piece of work and is not part of this
demo.

The pipeline, link by link:

1. **data → derivation.** ``read_fund_window`` queries the canonical marts for the per-segment
   begin/end NAV and the fund begin/end NAV, and cross-checks the end NAV against the fund-NAV
   mart.
2. **SO-09-01 over the substrate.** The fund begin/end NAV (no external flows) is dispatched to
   the ``bd09`` service's ``execute_so`` over the Restate ingress — the journaled path. The total
   return comes back stamped with the service provenance.
3. **SO-09-05 over the substrate.** The per-segment weights + returns (the same derivation) are
   dispatched to ``execute_so`` over the ingress. The contribution breakdown comes back stamped
   with the service provenance.
4. **reconcile.** The sum of the per-segment contributions is checked against the total return
   from step 2; they agree within a tight tolerance because both draw on one underlying
   per-segment NAV-delta derivation.

Latency: each operation is timed over the substrate. The first dispatch warms the connection
(and the service's lazy paths), so the demo reports both a warm and a cold figure and asserts the
warm bound.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from decimal import Decimal

from agentinvest_demo.marts import (
    DEFAULT_BEGIN_DATE,
    DEFAULT_END_DATE,
    DEFAULT_FUND_ID,
    FundWindowData,
    MartsUnavailableError,
    read_fund_window,
)
from agentinvest_demo.restate_client import (
    DispatchError,
    ExecuteSoCall,
    RestateDispatcher,
)

# The reconciliation tolerance: the per-segment contributions reconcile to the total return by
# construction (both derive from one per-segment NAV-delta set), so the only gap is decimal
# rounding in the weight and return ratios. 1e-9 is far tighter than any 1-bp (1e-4) reporting
# tolerance — the reconciliation here is exact-by-construction, not an approximation.
RECONCILIATION_TOLERANCE = Decimal("0.000000001")

# The per-operation warm latency bar the demo asserts (the success criterion).
LATENCY_BAR_S = 2.0

# A machine-readable result line the demo prints to stdout on its final line, on EVERY exit
# path. The fresh-checkout runner parses this to learn the demo's pass/fail outcome, because the
# uv layer the runner wraps the demo in does not propagate the process exit code in the WSL2
# launch environment (it masks every non-zero child exit to 0) — but it cannot eat stdout. The
# demo's own ``SystemExit(rc)`` (in ``__main__``) is kept intact for direct invocation and the
# integration test; this line is additive, for the runner's benefit. It is a deliberate machine
# line, consistent with the honest-boundary banner — not consumer prose.
RESULT_SENTINEL_PREFIX = "PHASE2_DEMO_RESULT:"


def _emit_result_sentinel(rc: int) -> None:
    """Print the machine-readable result line the runner parses, on the demo's final stdout line.

    ``rc == 0`` -> PASS; any non-zero -> FAIL. Flushed so it survives a buffered pipe through the
    uv / wsl launch layers. This is the channel the runner reads the outcome from, since the
    process exit code is masked by ``uv run`` in the launch environment.
    """
    outcome = "PASS" if rc == 0 else "FAIL"
    print(f"{RESULT_SENTINEL_PREFIX} {outcome} rc={rc}", flush=True)


@dataclass(frozen=True)
class StepLatency:
    """The cold (first) and warm (subsequent) round-trip latency for one operation, in seconds."""

    so_id: str
    cold_s: float
    warm_s: float


@dataclass(frozen=True)
class DemoResult:
    """The full result of the end-to-end task — the figures, the reconciliation, the latencies.

    ``reconciles`` is the load-bearing cross-step check: the per-segment contributions sum
    (``contribution_sum``) equals the fund total return (``total_return``) within
    ``RECONCILIATION_TOLERANCE``. ``total_return_call`` / ``breakdown_call`` carry the service
    provenance proving each step went through the ``bd09`` service over the substrate.
    """

    data: FundWindowData
    total_return: Decimal
    contribution_sum: Decimal
    reconciliation_diff: Decimal
    reconciles: bool
    total_return_call: ExecuteSoCall
    breakdown_call: ExecuteSoCall
    latencies: tuple[StepLatency, StepLatency]


def _total_return_args(data: FundWindowData) -> dict[str, object]:
    """SO-09-01 inputs — begin/end NAV, the window length, and an empty cash-flow series.

    The seed carries no external cash-flow series, so the total return takes the no-external-flow
    path: ``cash_flows`` is empty and the Modified-Dietz figure reduces to ``(end - begin) /
    begin`` over the window. The values are JSON-serialised as strings to preserve decimal
    precision across the envelope.
    """
    return {
        "beginning_value": str(data.begin_nav),
        "ending_value": str(data.end_nav),
        "period_days": data.period_days,
        "cash_flows": [],
    }


def _breakdown_args(data: FundWindowData) -> dict[str, object]:
    """SO-09-05 inputs — the per-asset-class segments (label, weight, segment return).

    The weights (segment begin NAV / fund begin NAV) sum to 1 and the returns are the segments'
    own window returns — both from the same derivation the total-return inputs came from, so the
    contributions reconcile to the total return.
    """
    return {
        "segments": [
            {
                "segment": seg.asset_class_label,
                "weight": str(seg.weight),
                "segment_return": str(seg.segment_return),
            }
            for seg in data.segments
        ],
    }


def run_phase2_demo(
    fund_id: str = DEFAULT_FUND_ID,
    begin_date: str = DEFAULT_BEGIN_DATE,
    end_date: str = DEFAULT_END_DATE,
    dispatcher: RestateDispatcher | None = None,
) -> DemoResult:
    """Run the full end-to-end task for one fund over one window and return the result.

    Reads the canonical marts, dispatches ``SO-09-01`` then ``SO-09-05`` to the ``bd09`` service
    over the substrate, reconciles the breakdown to the total return, and measures per-operation
    latency (a warm-up dispatch precedes the timed pair, so both a cold and a warm figure are
    captured). Raises ``MartsUnavailableError`` if the data layer is not provisioned, or
    ``DispatchError`` if the substrate / ``bd09`` service is not reachable.
    """
    dispatcher = dispatcher or RestateDispatcher()
    data = read_fund_window(fund_id=fund_id, begin_date=begin_date, end_date=end_date)

    tr_args = _total_return_args(data)
    cb_args = _breakdown_args(data)

    # Cold dispatch (warms the connection + the service's lazy import/registration paths), then a
    # warm re-dispatch, so the reported latency separates the one-off cold cost from the steady
    # per-operation cost the bar applies to. The warm calls are the figures the result carries.
    tr_cold = dispatcher.execute_so("SO-09-01", tr_args)
    tr_warm = dispatcher.execute_so("SO-09-01", tr_args)
    cb_cold = dispatcher.execute_so("SO-09-05", cb_args)
    cb_warm = dispatcher.execute_so("SO-09-05", cb_args)

    total_return = Decimal(str(tr_warm.result["total_return"]))
    contribution_sum = Decimal(str(cb_warm.result["total_return"]))
    diff = (contribution_sum - total_return).copy_abs()
    reconciles = diff <= RECONCILIATION_TOLERANCE

    return DemoResult(
        data=data,
        total_return=total_return,
        contribution_sum=contribution_sum,
        reconciliation_diff=diff,
        reconciles=reconciles,
        total_return_call=tr_warm,
        breakdown_call=cb_warm,
        latencies=(
            StepLatency("SO-09-01", cold_s=tr_cold.latency_s, warm_s=tr_warm.latency_s),
            StepLatency("SO-09-05", cold_s=cb_cold.latency_s, warm_s=cb_warm.latency_s),
        ),
    )


# --- consumer-facing rendering (clean of build framing) --------------------------------------


_BANNER = """\
agentINVEST — total return, then a breakdown by sector
======================================================
This runs a two-step analyst task across the analytics stack as one pipeline:
the canonical data is read, the inputs are derived, and two named operations are
dispatched to the bd09 service over the durable substrate — first the fund total
return, then its breakdown by asset class — and the breakdown is reconciled back
to the total return.

How to read this:
  * The data is synthetic. A green run proves the stack composes end to end over
    this dataset; it is not a production performance figure.
  * The two steps are called explicitly (total return, then the breakdown) — the
    pipeline runs the named operations; it does not decide which to run.
  * The window return uses the no-external-flow path (the dataset carries no
    external cash-flow series), so it is the value change over the window.
"""


def _fmt_pct(value: Decimal) -> str:
    """Render a rate as a percentage to four decimal places (e.g. 0.165102 -> '16.5102%')."""
    return f"{value * Decimal(100):.4f}%"


def _fmt_usd(value: Decimal) -> str:
    """Render a USD amount with thousands separators to two decimals."""
    return f"${value:,.2f}"


def render_result(result: DemoResult) -> str:
    """Render the demo result as clean consumer text (no build/provenance framing).

    Shows the fund + window, the total return (with the operation it came from and the substrate
    provenance), the per-segment contributions, the reconciliation check, and the per-operation
    latency. The provenance line names the substrate round-trip so a reader can see each figure
    came from the service, not a local compute.
    """
    data = result.data
    lines: list[str] = [_BANNER, ""]
    lines.append(f"Fund:   {data.fund_id} — {data.fund_name}")
    lines.append(f"Window: {data.begin_date} to {data.end_date} ({data.period_days} days)")
    lines.append(
        f"NAV:    {_fmt_usd(data.begin_nav)} -> {_fmt_usd(data.end_nav)} "
        f"(fund-NAV check: {_fmt_usd(data.mart_fund_nav)})"
    )
    lines.append("")
    lines.append(
        f"Step 1 — total return ({result.total_return_call.provenance.get('methodology')}): "
        f"{_fmt_pct(result.total_return)}"
    )
    lines.append(
        f"         via {result.total_return_call.so_id} over the substrate "
        f"[{result.total_return_call.computed_by}]"
    )
    lines.append("")
    lines.append("Step 2 — breakdown by sector (asset class):")
    for seg, contribution in zip(
        data.segments, result.breakdown_call.result["contributions"], strict=True
    ):
        weight = Decimal(str(contribution["weight"]))
        seg_return = Decimal(str(contribution["segment_return"]))
        contrib = Decimal(str(contribution["contribution"]))
        lines.append(
            f"  {seg.asset_class_label:<34} weight {_fmt_pct(weight):>10}  "
            f"return {_fmt_pct(seg_return):>10}  contribution {_fmt_pct(contrib):>10}"
        )
    lines.append(
        f"         via {result.breakdown_call.so_id} over the substrate "
        f"[{result.breakdown_call.computed_by}]"
    )
    lines.append("")
    lines.append("Reconciliation — do the sector contributions sum to the total return?")
    lines.append(
        f"  sum of contributions {_fmt_pct(result.contribution_sum)} vs "
        f"total return {_fmt_pct(result.total_return)}  "
        f"(difference {result.reconciliation_diff:.2e})"
    )
    lines.append(f"  reconciles: {'YES' if result.reconciles else 'NO'}")
    lines.append("")
    lines.append("Latency per operation (over the substrate):")
    for lat in result.latencies:
        lines.append(
            f"  {lat.so_id}  warm {lat.warm_s * 1000:7.1f} ms   cold {lat.cold_s * 1000:7.1f} ms"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """CLI entry — run the task, then emit the machine-readable result sentinel on every path.

    Wraps :func:`_run` so the ``PHASE2_DEMO_RESULT:`` line is printed on EVERY exit path (a clean
    pass, a substrate/data failure, a reconciliation/latency failure, or an unexpected exception),
    because the fresh-checkout runner reads the outcome from that stdout line rather than the
    process exit code (which ``uv run`` masks in the WSL2 launch environment). The integer return
    value is unchanged — ``__main__`` still does ``raise SystemExit(main())`` so a direct
    invocation and the integration test keep their exit-code contract.
    """
    try:
        rc = _run(argv)
    except SystemExit as exc:  # argparse --help/usage exits via SystemExit; surface its code.
        rc = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
        _emit_result_sentinel(rc)
        raise
    except BaseException:  # any unexpected crash must NOT be silently greened by the masked exit.
        _emit_result_sentinel(1)
        raise
    _emit_result_sentinel(rc)
    return rc


def _run(argv: list[str] | None = None) -> int:
    """Run the task for a fund over a window and print the clean result; return the exit code.

    Exits non-zero (with a clear message) if the data layer is not built or the substrate /
    ``bd09`` service is not reachable, or if the reconciliation or the latency bar is not met.
    """
    parser = argparse.ArgumentParser(
        prog="agentinvest-demo",
        description=(
            "Run the agentINVEST analytics task: a fund's total return, then its breakdown by "
            "sector, dispatched to the bd09 service over the durable substrate. Synthetic data; "
            "the two named operations are called explicitly (no planning); the window return uses "
            "the no-external-flow path."
        ),
    )
    parser.add_argument("--fund", default=DEFAULT_FUND_ID, help="fund id (default: %(default)s)")
    parser.add_argument(
        "--begin", default=DEFAULT_BEGIN_DATE, help="window begin date YYYY-MM-DD"
    )
    parser.add_argument("--end", default=DEFAULT_END_DATE, help="window end date YYYY-MM-DD")
    args = parser.parse_args(argv)

    dispatcher = RestateDispatcher()
    if not dispatcher.ingress_healthy():
        sys.stderr.write(
            "The durable substrate / bd09 service is not reachable. Bring the stack up first:\n"
            "  1. cd reference && pnpm dev:restate        (start the substrate)\n"
            "  2. register the bd09 service               (pnpm demo:phase2 does this for you)\n"
            "Or run the whole task from a clean state with: pnpm demo:phase2\n"
        )
        return 2

    try:
        result = run_phase2_demo(fund_id=args.fund, begin_date=args.begin, end_date=args.end)
    except MartsUnavailableError as exc:
        sys.stderr.write(f"Canonical data not available: {exc}\n")
        return 2
    except DispatchError as exc:
        sys.stderr.write(f"Dispatch failed: {exc}\n")
        return 2

    print(render_result(result))

    failed = False
    if not result.reconciles:
        sys.stderr.write(
            f"\nReconciliation FAILED: contributions {result.contribution_sum} != total return "
            f"{result.total_return} (diff {result.reconciliation_diff}).\n"
        )
        failed = True
    slow = [lat for lat in result.latencies if lat.warm_s >= LATENCY_BAR_S]
    if slow:
        names = ", ".join(f"{lat.so_id} ({lat.warm_s:.3f}s)" for lat in slow)
        sys.stderr.write(f"\nLatency bar ({LATENCY_BAR_S:.0f}s warm) exceeded: {names}.\n")
        failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
