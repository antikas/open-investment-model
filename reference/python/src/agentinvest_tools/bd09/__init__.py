"""BD-09 Performance & Analytics tools — the first five typed tool-catalogue entries.

These are the first real entries in the typed *tool catalogue* the per-Service-Operation
dispatch service wires over and the planning loop selects across. Each tool realises one
Service Operation of SD-09.1 Performance Measurement as a **pure, deterministic Python
function** with a **Pydantic input and output model**:

- ``so_09_01_compute_total_return``        — total return over a window (Modified Dietz).
- ``so_09_02_compute_time_weighted_return`` — true time-weighted return (sub-period returns
  linked geometrically, removing external-flow timing).
- ``so_09_03_compute_money_weighted_return`` — money-weighted return (the IRR of the dated
  cash-flow series).
- ``so_09_04_compute_benchmark_relative_return`` — active/excess return (portfolio − benchmark).
- ``so_09_05_compute_contribution_breakdown``  — segment contributions (weight × segment
  return) summing to the total return.

Shape (so the dispatch service can wrap each as ``tool(input_model)`` and a journaled step):
each function takes exactly one Pydantic input model and returns one Pydantic output model.
The input model is the source of truth for the auto-generated tool descriptor and API
surface; the output carries the figure, the method label and an echo of the inputs.

The correctness contract is the **external oracle**: the three return computations are matched
to a *published* GIPS / CFA-CIPM worked example to <= 1 bp absolute in the test suite — a tool
agreeing only with its own synthetic data has proven nothing. A green result over synthetic
data proves the *computation*, not a verified production performance figure.
"""

from __future__ import annotations

from agentinvest_tools.bd09.benchmark_relative_return import (
    BenchmarkRelativeReturnInput,
    BenchmarkRelativeReturnOutput,
    so_09_04_compute_benchmark_relative_return,
)
from agentinvest_tools.bd09.contribution_breakdown import (
    ContributionBreakdownInput,
    ContributionBreakdownOutput,
    SegmentContribution,
    SegmentInput,
    so_09_05_compute_contribution_breakdown,
)
from agentinvest_tools.bd09.money_weighted_return import (
    DatedCashFlow,
    MoneyWeightedReturnInput,
    MoneyWeightedReturnOutput,
    NonConventionalCashFlowError,
    so_09_03_compute_money_weighted_return,
)
from agentinvest_tools.bd09.time_weighted_return import (
    SubPeriod,
    TimeWeightedReturnInput,
    TimeWeightedReturnOutput,
    so_09_02_compute_time_weighted_return,
)
from agentinvest_tools.bd09.total_return import (
    TotalReturnInput,
    TotalReturnOutput,
    WeightedCashFlow,
    so_09_01_compute_total_return,
)

__all__ = [
    "BenchmarkRelativeReturnInput",
    "BenchmarkRelativeReturnOutput",
    "ContributionBreakdownInput",
    "ContributionBreakdownOutput",
    "DatedCashFlow",
    "MoneyWeightedReturnInput",
    "MoneyWeightedReturnOutput",
    "NonConventionalCashFlowError",
    "SegmentContribution",
    "SegmentInput",
    "SubPeriod",
    "TimeWeightedReturnInput",
    "TimeWeightedReturnOutput",
    "TotalReturnInput",
    "TotalReturnOutput",
    "WeightedCashFlow",
    "so_09_01_compute_total_return",
    "so_09_02_compute_time_weighted_return",
    "so_09_03_compute_money_weighted_return",
    "so_09_04_compute_benchmark_relative_return",
    "so_09_05_compute_contribution_breakdown",
]
