"""The gate-E runner — the first real gate-E number on the single-orchestrator bet.

``python -m agentinvest_evals.gate_e record`` runs the REAL ``.plan()`` planner
(Sonnet 4.6) over the OIM-105 intra-domain set AND the OIM-106 cross-office set,
records its per-case primary tool selections to fixed transcript files. This is
the one live, non-deterministic step (one Anthropic call per case).

``python -m agentinvest_evals.gate_e score`` (the default) scores the recorded
transcripts through the EXISTING harness (``run_eval`` for the within-office set,
``gap_metric`` for the cross-office set) and prints the gate-E verdict: within-
office accuracy (vs >=95%), cross-office accuracy, the gap (vs >5pp), and whether
the §E two-part trigger fires. Scoring is deterministic + replay-stable (it reads
the transcript; no model call).

The gate-E number is whatever the planner ACTUALLY scored — reported HONESTLY. A
miss (within < 95%, or gap > 5pp / cross < 90%) is a real architectural signal
(the eval-gated office-split, or an Opus escalation — the coordinator's/owner's
call), NEVER something to fudge. The runner does not tweak the eval, the prompt,
the candidate set, or the scoring to manufacture a pass.
"""

from __future__ import annotations

import sys

from agentinvest_evals.record_then_score import (
    TranscriptSelector,
    load_transcript,
    record_transcript,
    save_transcript,
)
from agentinvest_evals.runner import (
    _load_cross_office,
    _load_intra_domain,
    format_gap_report,
    format_report,
    gap_metric,
    run_eval,
)

# The recorded selector's label — the model that produced the transcripts. The
# transcripts are named with it, so a model bump records a distinct transcript.
from agentinvest_orchestrator.planner import PLANNER_MODEL


def _record() -> int:
    """Run the REAL planner over both sets; record the transcripts (live, once)."""
    intra_set, _ = _load_intra_domain()
    cross_set, _ = _load_cross_office()

    sys.stderr.write(
        f"[gate-e] recording REAL planner ({PLANNER_MODEL}) over "
        f"{len(intra_set.cases)} intra-domain + {len(cross_set.cases)} cross-office cases "
        "(one Anthropic call per case)...\n"
    )
    for label, eval_set in (("intra-domain", intra_set), ("cross-office", cross_set)):
        sys.stderr.write(f"[gate-e]   recording {label} ({len(eval_set.cases)} cases)...\n")
        transcript = record_transcript(eval_set, model_label=PLANNER_MODEL)
        path = save_transcript(transcript)
        sys.stderr.write(f"[gate-e]   wrote {path}\n")
    sys.stderr.write("[gate-e] recording complete. Run `score` to score the transcripts.\n")
    return 0


def _score() -> int:
    """Score the recorded transcripts through the EXISTING harness; print gate-E.

    Within-office set scored via ``run_eval`` (accuracy vs the >=95% bar);
    cross-office set scored via ``gap_metric`` (within / cross / gap + two-part
    trigger). The honest gate-E verdict is printed; a miss is reported, not fudged.
    """
    intra_set, intra_card = _load_intra_domain()
    cross_set, cross_card = _load_cross_office()

    intra_t = load_transcript(intra_set.set_id, PLANNER_MODEL)
    cross_t = load_transcript(cross_set.set_id, PLANNER_MODEL)

    intra_selector = TranscriptSelector(intra_t, intra_set)
    cross_selector = TranscriptSelector(cross_t, cross_set)

    # Within-office single-set accuracy (the >=95% bar) on the intra-domain set.
    intra_result = run_eval(intra_set, intra_card, intra_selector)
    # The gate-E gap metric on the office-arm-tagged cross-office set.
    gap_result = gap_metric(cross_set, cross_card, cross_selector)

    out = sys.stdout.write
    out("=" * 68 + "\n")
    out(f"agentINVEST gate-E — the REAL .plan() selector ({PLANNER_MODEL})\n")
    out("record-then-score: the planner's recorded selections, scored through the\n")
    out("existing within-office / cross-office harness ")
    out("(NOT a sync proxy, NOT an async-ified interface)\n")
    out("=" * 68 + "\n\n")

    out("--- intra-domain (within-office) single-set accuracy ---\n")
    out(format_report(intra_result, intra_card) + "\n\n")

    out("--- cross-office gate-E gap metric ---\n")
    out(format_gap_report(gap_result, cross_card) + "\n\n")

    # The gate-E headline — honest, whatever it is.
    within_acc = gap_result.within_accuracy
    cross_acc = gap_result.cross_accuracy
    out("=" * 68 + "\n")
    out("GATE-E HEADLINE (the first real number on the single-orchestrator bet):\n")
    out(
        f"  within-office accuracy (gap set): {gap_result.within_correct}/{gap_result.within_total}"
        f" = {within_acc * 100:.2f}%   (bar: >= 95%)\n"
    )
    out(
        f"  intra-domain accuracy           : {intra_result.correct}/{intra_result.total}"
        f" = {intra_result.accuracy * 100:.2f}%   (bar: >= 95%)\n"
    )
    out(
        f"  cross-office accuracy           : {gap_result.cross_correct}/{gap_result.cross_total}"
        f" = {cross_acc * 100:.2f}%\n"
    )
    out(f"  gap (within - cross)            : {gap_result.gap_pp:.2f}pp   (split if > 5pp)\n")
    within_ok = gap_result.within_correct * 100 >= 95 * gap_result.within_total
    intra_ok = intra_result.correct * 100 >= 95 * intra_result.total
    split = gap_result.split_indicated
    out(
        f"  within-office bar  : {'MET' if within_ok else 'MISSED'}"
        f"   intra-domain bar: {'MET' if intra_ok else 'MISSED'}"
        f"   gate-E split trigger: {'FIRES (split-indicated)' if split else 'clear (no-split)'}\n"
    )
    out("=" * 68 + "\n")
    out(
        "HONEST BOUNDARY: this IS the real selector's number (record-then-score). A miss\n"
        "is a genuine architectural signal (the eval-gated office-split, or an Opus\n"
        "escalation) — the coordinator's/owner's call, surfaced not fudged. The plan is\n"
        "generated, not executed; this scores TOOL SELECTION, not outcomes.\n"
        "On a small SYNTHETIC eval; the model is non-deterministic (re-recording may shift\n"
        "the number). v0.1 is frontier-only — no fine-tuning, no fleet, no office-split.\n"
    )
    # Exit code: this is a REPORT of the real number. It does not fail CI on a miss
    # (a miss is an architectural signal to surface, not a build break) — but it
    # DOES fail on a structural problem (a missing/mismatched transcript raises
    # before here). The coordinator/owner decides what a miss means.
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    mode = argv[0] if argv else "score"
    if mode == "record":
        return _record()
    if mode in ("score", ""):
        return _score()
    sys.stderr.write(f"usage: python -m agentinvest_evals.gate_e [record|score]\n(got: {mode!r})\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
