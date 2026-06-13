"""agentINVEST eval harness.

The offline, deterministic, replay-stable golden-set runner that is the first
architecture-proving move. This package is the *measuring instrument*: it loads an
eval set, runs a `Selector` over each case, and reports a within-office
tool-selection accuracy number against a write-time bar. Re-running it is
byte-identical (the regression+replay property).

What this package is NOT: it is not agentINVEST's tool-selection answer. It
measures a *declared deterministic baseline* selector behind the pluggable
`Selector` interface — a harness-validation datapoint, never a verdict on the
single-orchestrator bet. The harness *scores selections against a golden set*; a
deterministic selector implements `Selector` directly, but the real LLM `.plan()`
tool-RAG selector is async / durable / non-deterministic and so integrates via a
**record-then-score adapter** (record its selections as a fixed transcript, score
that through this same harness — NOT a synchronous proxy). Only when those
selections are scored here does the number become a statement about agentINVEST.
See `reference/evals/README.md`.

Public surface (the reused SSOT):

- `schema`   — `EvalCase`, `EvalSet`, `EvalCard` (the eval-set + eval-card format).
- `selector` — the `Selector` Protocol + `TokenOverlapBaselineSelector` (the
               declared deterministic baseline).
- `runner`   — `run_eval` (the single-set `accuracy >= bar` path) and
               `gap_metric` (the gap-metric path: within / cross /
               gap + two-part trigger over an `office_arm`-tagged set), plus the
               CLI entry (`python -m agentinvest_evals` default; `--gap` for the
               gap metric).
"""

from __future__ import annotations

__all__ = [
    "CROSS_OFFICE",
    "WITHIN_OFFICE",
    "EvalCard",
    "EvalCase",
    "EvalSet",
    "GapResult",
    "RunResult",
    "Selector",
    "TokenOverlapBaselineSelector",
    "ToolSpec",
    "gap_metric",
    "run_eval",
]

from agentinvest_evals.runner import GapResult, RunResult, gap_metric, run_eval
from agentinvest_evals.schema import (
    CROSS_OFFICE,
    WITHIN_OFFICE,
    EvalCard,
    EvalCase,
    EvalSet,
    ToolSpec,
)
from agentinvest_evals.selector import Selector, TokenOverlapBaselineSelector
