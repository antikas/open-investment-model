"""agentINVEST end-to-end demo — the analytics stack composed as one pipeline.

A runnable, hand-coded multi-step analyst task that exercises the whole analytics stack as
one pipeline: read the canonical marts, derive the inputs, dispatch two named Service
Operations to the ``bd09`` service over the Restate substrate, and reconcile the results.

The task: **compute a fund's total return, then break it down by sector** —

1. derive begin/end NAV per asset class from the canonical holdings + valuation data, then
   invoke ``SO-09-01`` (total return) via ``bd09.execute_so`` over the substrate;
2. derive the per-asset-class segment weights + segment returns from the same data, then
   invoke ``SO-09-05`` (contribution breakdown) via ``bd09.execute_so`` over the substrate;
3. reconcile: the per-segment contributions sum to the fund total return.

The two steps share one underlying per-segment NAV-delta derivation, so the contributions
reconcile to the total return by construction — the reconciliation proves the pipeline carried
consistent data through both tools.

Honest boundary (stated on the demo's consumer surface): the data is **synthetic**; the
multi-step glue is **hand-coded** (it calls the two *named* operations explicitly — it does not
*decide* which to call); and the input derivation is **bounded by the seed** (no external
cash-flow series is present, so the total-return step takes the no-external-flow path).
"""

from __future__ import annotations

from agentinvest_demo.marts import (
    FundWindowData,
    SegmentNav,
    list_funds,
    read_fund_window,
)
from agentinvest_demo.phase2_demo import (
    DemoResult,
    StepLatency,
    run_phase2_demo,
)
from agentinvest_demo.restate_client import (
    ExecuteSoCall,
    RestateDispatcher,
)

__all__ = [
    "DemoResult",
    "ExecuteSoCall",
    "FundWindowData",
    "RestateDispatcher",
    "SegmentNav",
    "StepLatency",
    "list_funds",
    "read_fund_window",
    "run_phase2_demo",
]
