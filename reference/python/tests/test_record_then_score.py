"""Record-then-score — the real planner integrates via a recorded transcript.

These tests prove the integration is record-then-score (NOT a sync proxy, NOT an
async-ified ``Selector`` interface), offline (no live model call — the recording
step is exercised with a fake planner via a recorded transcript fixture):

- a ``TranscriptSelector`` implements the existing ``Selector`` contract by reading
  a recorded transcript — deterministic, replay-stable, no model call;
- it scores through the EXISTING ``run_eval`` / ``gap_metric`` runner unchanged;
- a transcript scored twice is byte-identical (replay-stable);
- a transcript for the wrong set, or a partial transcript, is a loud error.
"""

from __future__ import annotations

import pytest

from agentinvest_evals.record_then_score import (
    PlanTranscript,
    TranscriptSelector,
)
from agentinvest_evals.runner import _load_cross_office, _load_intra_domain, gap_metric, run_eval
from agentinvest_evals.selector import Selector


def _perfect_transcript(eval_set) -> PlanTranscript:  # type: ignore[no-untyped-def]
    """A transcript where every case selects its expected (correct) tool."""
    return PlanTranscript(
        selector_label="fake-perfect",
        set_id=eval_set.set_id,
        model="fake-perfect",
        selections={c.case_id: c.expected_tool_id for c in eval_set.cases},
    )


def test_transcript_selector_satisfies_the_selector_protocol() -> None:
    eval_set, _ = _load_intra_domain()
    sel = TranscriptSelector(_perfect_transcript(eval_set), eval_set)
    assert isinstance(sel, Selector)  # runtime-checkable Protocol


def test_perfect_transcript_scores_100_through_run_eval() -> None:
    eval_set, card = _load_intra_domain()
    sel = TranscriptSelector(_perfect_transcript(eval_set), eval_set)
    result = run_eval(eval_set, card, sel)
    assert result.accuracy == 1.0
    assert result.correct == result.total


def test_perfect_transcript_scores_through_gap_metric_both_arms() -> None:
    eval_set, card = _load_cross_office()
    sel = TranscriptSelector(_perfect_transcript(eval_set), eval_set)
    gap = gap_metric(eval_set, card, sel)
    assert gap.within_total > 0 and gap.cross_total > 0  # both arms present
    assert gap.within_accuracy == 1.0
    assert gap.cross_accuracy == 1.0
    assert not gap.split_indicated


def test_scoring_is_replay_stable() -> None:
    eval_set, card = _load_intra_domain()
    t = _perfect_transcript(eval_set)
    r1 = run_eval(eval_set, card, TranscriptSelector(t, eval_set))
    r2 = run_eval(eval_set, card, TranscriptSelector(t, eval_set))
    assert r1 == r2  # the recorded transcript scores byte-identically


def test_wrong_set_transcript_is_a_loud_error() -> None:
    intra, _ = _load_intra_domain()
    cross, _ = _load_cross_office()
    t = _perfect_transcript(intra)
    with pytest.raises(ValueError):
        TranscriptSelector(t, cross)  # set_id mismatch


def test_partial_transcript_is_a_loud_error() -> None:
    eval_set, _ = _load_intra_domain()
    t = _perfect_transcript(eval_set)
    # drop one selection
    partial = PlanTranscript(
        selector_label=t.selector_label,
        set_id=t.set_id,
        model=t.model,
        selections={k: v for i, (k, v) in enumerate(t.selections.items()) if i > 0},
    )
    with pytest.raises(ValueError):
        TranscriptSelector(partial, eval_set)


def test_transcript_json_round_trips() -> None:
    eval_set, _ = _load_intra_domain()
    t = _perfect_transcript(eval_set)
    assert PlanTranscript.from_json(t.to_json()) == t
