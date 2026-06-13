"""The offline golden-set runner — the measuring instrument.

`run_eval(eval_set, card, selector)` runs the selector over every case, scores
within-office selection accuracy, and returns a `RunResult`. The CLI
(`python -m agentinvest_evals`) loads the set + card from `reference/evals/sets/`,
runs the declared baseline selector, prints a **byte-identical** report, and
**exits non-zero when the bar is missed** (CI-gate-ready — the `reference/` CI
pipeline that would invoke it is a later item, not built here).

`gap_metric(eval_set, card, selector)` (the net-new runner/verdict work) runs the
selector over an **office-arm-tagged** set and returns a `GapResult`: within-office
accuracy, cross-office accuracy, the **gap** (within − cross), and the **two-part
trigger** (gap `> 5pp` primary OR cross-office `< 90%` backstop). The `--gap` CLI
path runs it over the cross-office set. This is a distinct result/verdict shape —
it is NOT expressible through `RunResult.passed`'s single `accuracy >= bar` — and
the single-set default path is kept working unchanged alongside it (additive, not
a rewrite).

Determinism / replay (the regression+replay property the brief requires):

- cases are scored in the set's declared order; no dict iteration leaks into
  output; no timestamps, no paths, no PIDs, no randomness in the report;
- the baseline selector is exact-integer and order-stable (see `selector.py`);
- floats appear only as the final accuracy, formatted to a fixed precision.

Result: running the suite twice produces byte-identical stdout *within one output
encoding*. The CLI proves this itself with `--check-replay` (runs the report twice
in-process and asserts the two strings are identical), so the replay property is
part of what the one command demonstrates rather than a claim made elsewhere.

Encoding-robust replay identity: the *rendered console stdout* is not
a safe cross-machine replay key — the report carries non-ASCII (em-dashes etc.)
which serialises to different bytes under cp1252 (a Windows console) vs UTF-8 (a
Linux CI runner), so hashing stdout would spuriously differ across machines even
on an identical run. The portable replay key is therefore the **canonical JSON of
the structured `RunResult`** (`replay_hash`, `--replay-hash`): `json.dumps(...,
sort_keys=True, ensure_ascii=True)` over the result dataclass, SHA-256'd. Because
`ensure_ascii=True` escapes every non-ASCII char to a `\\uXXXX` form and
`sort_keys` pins key order, this hash is identical on Windows-console and Linux-CI
regardless of the console's locale. That is the hash a CI gate should pin, not the
stdout hash.

The honest boundary: the accuracy this runner emits is the *baseline selector's*
accuracy — a harness-validation datapoint. It is NOT agentINVEST's tool-selection
accuracy and NOT a verdict on the single-orchestrator bet. The report states this
in terms; the runner never narrates a green/red as "tool selection proven" /
"cross-office risk retired". The same boundary holds for the gap metric: the
proven thing is that the GAP METRIC computes the two sub-population accuracies +
the gap + the two-part trigger and fires correctly; the baseline's
"split-indicated" / "no-split" is a harness datapoint, NOT the architecture's
split decision. The "within-office < 95% => catalogue broken" and "gap > 5pp =>
split" interpretations apply to the REAL (production) selector, not to a lexical
baseline (a baseline below 95% within-office is expected). That is why `_main_gap`
does NOT exit non-zero on a baseline split-indicated — it would be the
equivalence-substitution failure to treat the baseline's gap as the CI-gating
architecture verdict. The number becomes a statement about agentINVEST only when
the production selector's selections are scored here. The production `.plan()`
selector is async/durable/non-deterministic, so it integrates by **recording its
per-query selections as a fixed transcript and scoring that** through this same
scoring code — NOT by wrapping the async selector in a synchronous `Selector`
proxy (that would score a stand-in). The synchronous `Selector` contract scored
live in the loop below is the *deterministic-selector* contract; `run_eval` stays
synchronous and pure precisely to keep replay stable.
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from agentinvest_evals.schema import CROSS_OFFICE, WITHIN_OFFICE, EvalCard, EvalSet
from agentinvest_evals.selector import Selector, TokenOverlapBaselineSelector

# The eval-content home. Resolved relative to this file so the runner works from
# any cwd: .../reference/python/src/agentinvest_evals/runner.py
# -> .../reference/evals/sets.
_SETS_DIR = Path(__file__).resolve().parents[3] / "evals" / "sets"

_INTRA_DOMAIN_SET = "intra-domain-bd09-returns.json"
_INTRA_DOMAIN_CARD = "intra-domain-bd09-returns.card.md"

_CROSS_OFFICE_SET = "cross-office-front-vs-middle.json"
_CROSS_OFFICE_CARD = "cross-office-front-vs-middle.card.md"

# Gap-metric tolerances (the SSOT). The split is indicated (for the REAL selector
# — see the honest boundary) when EITHER limb fires: the gap exceeds 5 percentage
# points (primary), OR cross-office accuracy drops below 90% (backstop).
#
# The two threshold constants are held as exact integer rationals so the trigger
# can be computed in integer percentage-point space (see `GapResult`'s
# `primary_gap_fires` / `backstop_fires`). The float forms `_GAP_PRIMARY_PP` /
# `_CROSS_OFFICE_BACKSTOP` remain ONLY for the report's display strings — they are
# never used in a trigger comparison (that avoids the float-fragility trap:
# `gap_pp > 5.0` on a float-subtracted gap gives different verdicts for
# mathematically-equal inputs, e.g. `1.0 − 0.95` fires but `0.10 − 0.05` does not).
_GAP_PRIMARY_PP = 5.0  # DISPLAY ONLY — the primary 5pp threshold as a float string
_CROSS_OFFICE_BACKSTOP = 0.90  # DISPLAY ONLY — the backstop 90% threshold as a float string

# The same two thresholds as exact integer rationals (numerator / denominator),
# used for the trigger comparisons. `5pp` of a fraction = 5/100; the 90% backstop
# = 90/100 = 9/10. Held this way so the limbs compare via integer cross-
# multiplication (the discipline `selector.py` already uses for its Jaccard
# ranking) — exact and stable at the boundary, never a float `>` / `<`.
_GAP_PRIMARY_PP_NUM = 5  # primary threshold = 5/100 of a fraction (i.e. 5pp)
_GAP_PRIMARY_PP_DEN = 100
_CROSS_BACKSTOP_NUM = 9  # backstop threshold = 9/10 (i.e. 90%)
_CROSS_BACKSTOP_DEN = 10


@dataclass(frozen=True)
class CaseOutcome:
    case_id: str
    query: str
    expected: str
    selected: str
    correct: bool


@dataclass(frozen=True)
class RunResult:
    eval_id: str
    set_id: str
    selector_name: str
    metric: str
    bar: float
    total: int
    correct: int
    outcomes: tuple[CaseOutcome, ...]

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0

    @property
    def passed(self) -> bool:
        return self.accuracy >= self.bar


def canonical_json(result: RunResult) -> str:
    """Encoding-independent canonical serialisation of a `RunResult`.

    The replay/identity key must be platform-stable. Hashing the *rendered console
    stdout* is not safe across machines: the report's non-ASCII (em-dashes, `>=`,
    section marks) serialises to different bytes under cp1252 (Windows console) vs
    UTF-8 (Linux CI), so a cross-machine stdout hash would spuriously differ. This
    function serialises the *structured result* with `sort_keys=True` (pins key
    order) and `ensure_ascii=True` (escapes every non-ASCII char to `\\uXXXX`, so
    the output is pure ASCII regardless of locale). SHA-256 over this string is
    therefore identical on Windows-console and on Linux-CI for the same run.
    """
    return json.dumps(asdict(result), sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def replay_hash(result: RunResult) -> str:
    """SHA-256 of the canonical (encoding-independent) `RunResult` serialisation.

    The portable CI replay key: a CI gate pins THIS hash, not the stdout hash —
    it is the same across Windows-console and Linux-CI for an identical run.
    """
    return hashlib.sha256(canonical_json(result).encode("ascii")).hexdigest()


@dataclass(frozen=True)
class GapResult:
    """The gap-metric verdict (the net-new runner/verdict work).

    The cross-office verdict is NOT a single `accuracy >= bar`. It is two
    sub-population accuracies, their difference, and a two-part trigger — none
    expressible through `RunResult.passed`. So this is a distinct result shape
    computed over an office-arm-tagged set.

    Fields:
      - `within_total` / `within_correct` / `cross_total` / `cross_correct` — the
        two sub-populations' raw counts, partitioned by each case's `office_arm`.
      - `within_accuracy` / `cross_accuracy` — the two sub-population accuracies.
      - `gap` — within_accuracy − cross_accuracy, a fraction (the degradation the
        office-split specifically fixes; the cleaner of the two signals).
      - `gap_pp` — the same gap in percentage points.
      - the two trigger limbs, computed against the SSOT tolerances in
        **integer percentage-point space** (exact cross-multiplication of the
        raw counts — never a float `>` / `<`): the primary
        fires iff the gap STRICTLY exceeds 5pp; the backstop fires iff cross-office
        accuracy STRICTLY drops below 90%. `gap` / `gap_pp` (floats) are for the
        report's display only and are never used in a trigger comparison.
      - `split_indicated` — True iff EITHER limb fires (the rule: primary OR
        backstop). **See the honest boundary below: for a LEXICAL BASELINE this
        flag is a harness-validation datapoint, NOT a verdict that the architecture
        must split. The split interpretation is reserved for the real selector run
        through this metric (via record-then-score).**

    `outcomes` carries every case outcome (both arms) so the report and the
    replay hash are complete and deterministic.
    """

    within_total: int
    within_correct: int
    cross_total: int
    cross_correct: int
    outcomes: tuple[CaseOutcome, ...]

    @property
    def within_accuracy(self) -> float:
        return self.within_correct / self.within_total if self.within_total else 0.0

    @property
    def cross_accuracy(self) -> float:
        return self.cross_correct / self.cross_total if self.cross_total else 0.0

    @property
    def gap(self) -> float:
        """within − cross, as a fraction (positive = cross-office is worse).

        DISPLAY ONLY — float-subtracted, so it carries the usual representation
        error. It is what the report prints; it is NOT used in either trigger
        comparison (those are exact integer cross-multiplications, see below).
        """
        return self.within_accuracy - self.cross_accuracy

    @property
    def gap_pp(self) -> float:
        """The gap in percentage points (DISPLAY ONLY — see `gap`)."""
        return self.gap * 100.0

    @property
    def primary_gap_fires(self) -> bool:
        """Primary limb: the gap STRICTLY exceeds 5 percentage points.

        Computed in integer percentage-point space to be exact and stable at the
        boundary. The float gap `within_acc − cross_acc` is
        representation-fragile: `1.0 − 0.95` and `0.10 − 0.05` are mathematically
        the same 5pp gap but land on different sides of a float `> 5.0`, giving
        different verdicts for equal inputs. Instead, fire iff

            (within − cross) > 5/100             [both as exact fractions]
          ⇔ within_correct/within_total − cross_correct/cross_total > 5/100
          ⇔ (within_correct·cross_total − cross_correct·within_total)·100
                > 5·within_total·cross_total      [×100·within_total·cross_total,
                                                    all strictly positive]

        — an all-integer comparison. STRICT `>`: an exact 5.000…pp gap does NOT
        fire (honoring the rule's "exceeds 5 percentage points"). `within_total` and
        `cross_total` are both ≥ 1 (the both-arms guard in `gap_metric`), so the
        multipliers are positive and the inequality direction is preserved. A
        negative gap (cross-office better than within) yields a negative left side
        and correctly does not fire.
        """
        if not self.within_total or not self.cross_total:
            return False
        gap_numerator = (
            self.within_correct * self.cross_total - self.cross_correct * self.within_total
        )
        return gap_numerator * _GAP_PRIMARY_PP_DEN > _GAP_PRIMARY_PP_NUM * (
            self.within_total * self.cross_total
        )

    @property
    def backstop_fires(self) -> bool:
        """Backstop limb: cross-office accuracy STRICTLY drops below 90%.

        Integer comparison (consistent with the primary limb):
        fire iff cross_correct/cross_total < 9/10 ⇔ cross_correct·10 < 9·cross_total
        (cross_total ≥ 1, so the multiplier is positive). STRICT `<`: an exact 90%
        cross-office accuracy does NOT fire (honoring the rule's "drops below 90%").
        """
        if not self.cross_total:
            return False
        return self.cross_correct * _CROSS_BACKSTOP_DEN < _CROSS_BACKSTOP_NUM * self.cross_total

    @property
    def split_indicated(self) -> bool:
        """The two-part trigger: primary OR backstop. (Honest boundary: for the
        baseline this is a harness datapoint, NOT the architecture verdict.)"""
        return self.primary_gap_fires or self.backstop_fires


def gap_metric(eval_set: EvalSet, card: EvalCard, selector: Selector) -> GapResult:
    """Run `selector` over an office-arm-tagged set and compute the gap.

    Pure; deterministic; no I/O. Partitions every case by its `office_arm`,
    scores each case identically (selected == label), and assembles the two
    sub-population accuracies, the gap, and the two-part trigger into a
    `GapResult`. Raises if the set is malformed, one-sided over the focus tools,
    or does not actually carry BOTH arms (a gap needs both sub-populations — a
    single-arm set cannot compute a gap, the "no defensible control" guard).
    """
    structural = eval_set.validate()
    if structural:
        raise ValueError("eval set is malformed:\n  " + "\n  ".join(structural))
    two_sided = two_sidedness_problems(eval_set, card.focus_tool_ids)
    if two_sided:
        raise ValueError("eval set is one-sided (toy-set guard):\n  " + "\n  ".join(two_sided))

    arms = {c.office_arm for c in eval_set.cases}
    if WITHIN_OFFICE not in arms or CROSS_OFFICE not in arms:
        raise ValueError(
            "gap metric needs BOTH office arms in one set (apples-to-apples control); "
            f"found only: {sorted(arms)}. A single-arm set cannot compute a gap."
        )

    outcomes: list[CaseOutcome] = []
    within_correct = within_total = cross_correct = cross_total = 0
    for case in eval_set.cases:
        selected = selector.select(case.query, eval_set.tools)
        correct = selected == case.expected_tool_id
        outcomes.append(
            CaseOutcome(
                case_id=case.case_id,
                query=case.query,
                expected=case.expected_tool_id,
                selected=selected,
                correct=correct,
            )
        )
        if case.office_arm == WITHIN_OFFICE:
            within_total += 1
            within_correct += int(correct)
        else:  # CROSS_OFFICE (validate() guarantees no third value)
            cross_total += 1
            cross_correct += int(correct)

    return GapResult(
        within_total=within_total,
        within_correct=within_correct,
        cross_total=cross_total,
        cross_correct=cross_correct,
        outcomes=tuple(outcomes),
    )


def gap_replay_hash(result: GapResult) -> str:
    """Encoding-independent canonical replay hash of a `GapResult`.

    Same portable-CI-key discipline as `replay_hash` for `RunResult`: canonical
    JSON (`sort_keys`, `ensure_ascii` → pure ASCII), SHA-256'd, so the hash is
    identical on a Windows cp1252 console and a Linux UTF-8 CI runner for an
    identical run. A CI gate pins THIS hash for the gap run, not the stdout hash.
    """
    payload = json.dumps(asdict(result), sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def two_sidedness_problems(eval_set: EvalSet, focus_tool_ids: tuple[str, ...]) -> list[str]:
    """Assert each focus tool appears as BOTH a correct answer and a confuser.

    A one-sided set (a tool that is only ever the answer, or only ever a confuser)
    is a toy set — each of the 4 return tools must play both roles. Returns a list
    of problems (empty == genuinely two-sided).
    """
    as_expected: set[str] = {c.expected_tool_id for c in eval_set.cases}
    as_confuser: set[str] = {cf for c in eval_set.cases for cf in c.confusers}
    problems: list[str] = []
    for tid in focus_tool_ids:
        if tid not in as_expected:
            problems.append(f"focus tool '{tid}' is never a correct answer (one-sided set)")
        if tid not in as_confuser:
            problems.append(f"focus tool '{tid}' is never a confuser (one-sided set)")
    return problems


def run_eval(eval_set: EvalSet, card: EvalCard, selector: Selector) -> RunResult:
    """Score `selector` over `eval_set`. Pure; deterministic; no I/O."""
    structural = eval_set.validate()
    if structural:
        raise ValueError("eval set is malformed:\n  " + "\n  ".join(structural))
    two_sided = two_sidedness_problems(eval_set, card.focus_tool_ids)
    if two_sided:
        raise ValueError("eval set is one-sided (toy-set guard):\n  " + "\n  ".join(two_sided))

    outcomes: list[CaseOutcome] = []
    for case in eval_set.cases:
        selected = selector.select(case.query, eval_set.tools)
        outcomes.append(
            CaseOutcome(
                case_id=case.case_id,
                query=case.query,
                expected=case.expected_tool_id,
                selected=selected,
                correct=selected == case.expected_tool_id,
            )
        )
    correct = sum(1 for o in outcomes if o.correct)
    return RunResult(
        eval_id=card.eval_id,
        set_id=eval_set.set_id,
        selector_name=selector.name,
        metric=card.metric,
        bar=card.bar,
        total=len(outcomes),
        correct=correct,
        outcomes=tuple(outcomes),
    )


def format_report(result: RunResult, card: EvalCard) -> str:
    """Render the byte-identical report. No timestamps / paths / randomness."""
    lines: list[str] = []
    lines.append("agentINVEST eval harness")
    lines.append("=" * 60)
    lines.append(f"eval        : {result.eval_id}")
    lines.append(f"set         : {result.set_id}")
    lines.append(f"selector    : {result.selector_name}  (declared deterministic baseline)")
    lines.append(f"metric      : {result.metric}")
    lines.append(f"oracle      : {card.oracle}")
    lines.append(f"author      : {card.author}")
    lines.append(f"blesser     : {card.blesser}")
    if card.single_actor_authored_and_blessed():
        lines.append("  GOVERNANCE WARNING: author == blesser (single-actor author-and-bless)")
    lines.append("-" * 60)
    for o in result.outcomes:
        mark = "ok  " if o.correct else "MISS"
        lines.append(f"  [{mark}] {o.case_id}: expected={o.expected} selected={o.selected}")
    lines.append("-" * 60)
    # Accuracy formatted to a fixed precision so the line is byte-stable.
    acc_pct = f"{result.accuracy * 100:.2f}%"
    bar_pct = f"{result.bar * 100:.2f}%"
    lines.append(f"accuracy    : {result.correct}/{result.total} = {acc_pct}")
    lines.append(f"bar (within-office) : >= {bar_pct}")
    verdict = "PASS" if result.passed else "FAIL"
    lines.append(f"verdict     : {verdict} (selector accuracy vs the bar)")
    lines.append("")
    lines.append("HONEST BOUNDARY: this is the BASELINE selector's accuracy —")
    lines.append("a harness-validation datapoint. It is NOT agentINVEST's tool-selection")
    lines.append("accuracy and NOT a verdict on the single-orchestrator bet. The harness is")
    lines.append("what is proven here. The real measurement comes when the LLM planner's real")
    lines.append(".plan() selector's selections are scored here against this same set. That")
    lines.append(
        "selector is async/durable on the substrate, so it integrates via a record-then-score"
    )
    lines.append("adapter (record its selections, score the transcript) — NOT a sync proxy.")
    lines.append("See reference/evals/README.md.")
    return "\n".join(lines)


def format_gap_report(result: GapResult, card: EvalCard) -> str:
    """Render the byte-identical gap-metric report. No timestamps/paths.

    Shows the two sub-population accuracies, the gap, BOTH trigger limbs (so the
    metric is visibly the whole two-part trigger, not half of it), the combined
    split-indicated verdict, and — load-bearing — the honest-boundary statement
    that the baseline's gap is a harness datapoint, NOT the architecture verdict.
    """
    lines: list[str] = []
    lines.append("agentINVEST gap metric")
    lines.append("=" * 64)
    lines.append(f"eval        : {result_eval_id(card)}")
    lines.append(f"set         : {card.set_ref}")
    lines.append("selector    : token-overlap-baseline  (declared deterministic baseline)")
    lines.append(f"oracle      : {card.oracle}")
    lines.append(f"author      : {card.author}")
    lines.append(f"blesser     : {card.blesser}")
    if card.single_actor_authored_and_blessed():
        lines.append("  GOVERNANCE WARNING: author == blesser (single-actor author-and-bless)")
    lines.append("-" * 64)
    lines.append("per-case outcomes (arm-tagged):")
    # Stable order: the set's declared case order is preserved in `outcomes`.
    for o in result.outcomes:
        mark = "ok  " if o.correct else "MISS"
        lines.append(f"  [{mark}] {o.case_id}: expected={o.expected} selected={o.selected}")
    lines.append("-" * 64)
    within_pct = f"{result.within_accuracy * 100:.2f}%"
    cross_pct = f"{result.cross_accuracy * 100:.2f}%"
    gap_pct = f"{result.gap_pp:.2f}pp"
    lines.append(
        f"within-office accuracy : {result.within_correct}/{result.within_total} = {within_pct}"
    )
    lines.append(
        f"cross-office  accuracy : {result.cross_correct}/{result.cross_total} = {cross_pct}"
    )
    lines.append(f"gap (within - cross)   : {gap_pct}")
    lines.append("-" * 64)
    lines.append("two-part trigger:")
    primary = "FIRES" if result.primary_gap_fires else "clear"
    backstop = "FIRES" if result.backstop_fires else "clear"
    lines.append(
        f"  primary  (gap > {_GAP_PRIMARY_PP:.0f}pp)            : {primary}  "
        f"(gap = {gap_pct})"
    )
    lines.append(
        f"  backstop (cross-office < {_CROSS_OFFICE_BACKSTOP * 100:.0f}%)   : {backstop}  "
        f"(cross-office = {cross_pct})"
    )
    verdict = "SPLIT-INDICATED" if result.split_indicated else "NO-SPLIT"
    lines.append(f"  trigger verdict (primary OR backstop) : {verdict}")
    lines.append("")
    lines.append("HONEST BOUNDARY: the GAP METRIC is what is proven here —")
    lines.append("it computes within-office accuracy, cross-office accuracy, the gap, and the")
    lines.append("two-part trigger, and fires correctly. The numbers above are the BASELINE")
    lines.append("selector's — a harness-validation datapoint. They are NOT a verdict on")
    lines.append("whether to split the architecture. The interpretations — 'within-office")
    lines.append("< 95% => the catalogue/retrieval is broken' and 'gap > 5pp => split the")
    lines.append(
        "architecture' — apply to the LLM planner's REAL selector, not to a lexical baseline."
    )
    lines.append("A lexical baseline scoring < 95% within-office is EXPECTED and says nothing")
    lines.append("about the catalogue; a baseline 'SPLIT-INDICATED' above does NOT mean the")
    lines.append("single-orchestrator bet is lost. The real split / no-split decision exists")
    lines.append("only when the LLM planner's async/durable .plan() selector runs through")
    lines.append("this same metric via a record-then-score adapter (record its selections,")
    lines.append("score the transcript) — NOT a synchronous proxy. See reference/evals/README.md.")
    return "\n".join(lines)


def result_eval_id(card: EvalCard) -> str:
    """The card's eval_id (tiny indirection kept so the report reads cleanly)."""
    return card.eval_id


def _load_intra_domain() -> tuple[EvalSet, EvalCard]:
    set_path = _SETS_DIR / _INTRA_DOMAIN_SET
    card_path = _SETS_DIR / _INTRA_DOMAIN_CARD
    eval_set = EvalSet.from_dict(json.loads(set_path.read_text(encoding="utf-8")))
    card = EvalCard.from_markdown(card_path.read_text(encoding="utf-8"))
    return eval_set, card


def _load_cross_office() -> tuple[EvalSet, EvalCard]:
    set_path = _SETS_DIR / _CROSS_OFFICE_SET
    card_path = _SETS_DIR / _CROSS_OFFICE_CARD
    eval_set = EvalSet.from_dict(json.loads(set_path.read_text(encoding="utf-8")))
    card = EvalCard.from_markdown(card_path.read_text(encoding="utf-8"))
    return eval_set, card


def _main_gap(argv: list[str]) -> int:
    """The gap-metric path over the cross-office tagged set.

    Computes within-office accuracy, cross-office accuracy, the gap, and the
    two-part trigger, then prints the gap report. The same `--check-replay` /
    `--replay-hash` flags apply, over the `GapResult` (encoding-independent).

    Exit code: this path reports the gap metric; it does NOT exit non-zero on a
    "split-indicated" baseline result, because — per the honest boundary — a
    baseline split-indicated is a harness datapoint, not a CI-failing
    architecture verdict. The exit code instead guards the HARNESS's own
    integrity: 0 when the gap metric computed cleanly over both arms; non-zero
    only on a malformed / one-sided / single-arm set (the metric could not be
    computed) or a replay failure. (The real-selector gate decides what exit
    semantics a split-indicated verdict carries when the production selector
    runs through this metric — not the baseline.)
    """
    check_replay = "--check-replay" in argv
    hash_only = "--replay-hash" in argv

    eval_set, card = _load_cross_office()
    selector = TokenOverlapBaselineSelector()
    result = gap_metric(eval_set, card, selector)

    if hash_only:
        sys.stdout.write(gap_replay_hash(result) + "\n")
        return 0

    report = format_gap_report(result, card)

    if check_replay:
        result2 = gap_metric(eval_set, card, selector)
        report2 = format_gap_report(result2, card)
        if report != report2:
            sys.stderr.write("REPLAY FAILURE: two gap runs produced different output\n")
            return 3
        if gap_replay_hash(result) != gap_replay_hash(result2):
            sys.stderr.write("REPLAY FAILURE: two gap runs produced different replay hashes\n")
            return 3
        sys.stdout.write("replay check: two in-process gap runs are byte-identical\n")
        sys.stdout.write(
            "gap replay hash (encoding-independent, the portable CI key): "
            + gap_replay_hash(result)
            + "\n"
        )

    sys.stdout.write(report + "\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry. Default: the intra-domain single-set eval.

    Modes:
      (default)       the within-office single-set `accuracy >= bar` path
                      over the intra-domain BD-09 returns set — exit non-zero on a
                      bar miss (CI-gate-ready).
      --gap           the gap-metric path over the cross-office office-arm-tagged
                      set: within / cross / gap + two-part trigger. (See
                      `_main_gap` for its distinct exit semantics.)

    Flags (apply to both modes):
      --check-replay  run the report twice in-process and assert byte-identical
                      output (the regression+replay proof), then print it once.
      --replay-hash   print ONLY the encoding-independent canonical replay hash
                      (the portable CI key) and exit — nothing else, so a CI gate
                      can capture exactly one stable line across machines.

    Exit code (default mode): 0 iff selector accuracy >= the bar; non-zero on a
    bar miss (CI-gate-ready) or on a malformed/one-sided set.
    """
    argv = sys.argv[1:] if argv is None else argv

    if "--gap" in argv:
        return _main_gap(argv)

    check_replay = "--check-replay" in argv
    hash_only = "--replay-hash" in argv

    eval_set, card = _load_intra_domain()
    selector = TokenOverlapBaselineSelector()

    result = run_eval(eval_set, card, selector)

    if hash_only:
        # The portable replay key — pure ASCII, locale-independent.
        sys.stdout.write(replay_hash(result) + "\n")
        return 0 if result.passed else 1

    report = format_report(result, card)

    if check_replay:
        result2 = run_eval(eval_set, card, selector)
        report2 = format_report(result2, card)
        if report != report2:
            sys.stderr.write("REPLAY FAILURE: two runs produced different output\n")
            return 3
        # The encoding-robust identity check: the structured-result hash is stable
        # across output encodings (cp1252 / UTF-8), unlike the rendered stdout.
        if replay_hash(result) != replay_hash(result2):
            sys.stderr.write("REPLAY FAILURE: two runs produced different replay hashes\n")
            return 3
        sys.stdout.write("replay check: two in-process runs are byte-identical\n")
        sys.stdout.write(
            "replay hash (encoding-independent, the portable CI key): "
            + replay_hash(result)
            + "\n"
        )

    sys.stdout.write(report + "\n")
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
