"""Tests for the eval harness.

Cover the three load-bearing properties:
1. **Replay stability** — running the report twice is byte-identical (the
   regression+replay property the harness must prove).
2. **The bar bites** — the CLI exits non-zero on a bar miss and zero on a pass
   (CI-gate-ready), and `RunResult.passed` follows the >= bar rule.
3. **The toy-set guards fire** — a malformed set and a one-sided set both raise
   rather than silently scoring (the "100%-pass is suspect" failure mode).

Plus a faithfulness check that the intra-domain set loads, is well-formed and
two-sided, and that the Selector contract is satisfiable by a trivial alternate
selector (the interface walk, in code).

The gap metric tests include the boundary tests that pin the two trigger limbs as
**float-robust**: an exact-5pp gap does not fire the primary, an exact-90% cross
does not fire the backstop, just-over / just-under do fire, and — the load-bearing
one — three mathematically-equal-but-float-different 5pp gap constructions give the
SAME verdict (the bug the integer-percentage-point limbs fix).
"""

from __future__ import annotations

import json

import pytest

from agentinvest_evals.runner import (
    _load_cross_office,
    _load_intra_domain,
    format_gap_report,
    format_report,
    gap_metric,
    gap_replay_hash,
    main,
    run_eval,
    two_sidedness_problems,
)
from agentinvest_evals.schema import (
    CROSS_OFFICE,
    WITHIN_OFFICE,
    EvalCard,
    EvalCase,
    EvalSet,
    ToolSpec,
)
from agentinvest_evals.selector import Selector, TokenOverlapBaselineSelector, tokenize

# --- A tiny hand-built fixture (independent of the shipped intra-domain set) ---


def _toy_set() -> EvalSet:
    tools = (
        ToolSpec("T-A", "Alpha return", "compute the alpha return removing cash flow timing"),
        ToolSpec(
            "T-B", "Beta return", "compute the beta internal rate of return on dated cash flows"
        ),
    )
    cases = (
        EvalCase("c1", "alpha return removing cash flow timing", "T-A", ("T-B",), "lexical"),
        EvalCase(
            "c2", "beta internal rate of return on dated cash flows", "T-B", ("T-A",), "lexical"
        ),
    )
    return EvalSet("toy", "toy two-sided set", tools, cases)


def _toy_card(bar: float) -> EvalCard:
    return EvalCard(
        eval_id="toy",
        measures="toy",
        metric="accuracy",
        bar=bar,
        oracle="hand-built",
        author="author-x",
        blesser="blesser-y",
        set_ref="n/a",
        focus_tool_ids=("T-A", "T-B"),
    )


# --- 1. Replay stability -----------------------------------------------------


def test_report_is_byte_identical_across_runs() -> None:
    eval_set, card = _load_intra_domain()
    sel = TokenOverlapBaselineSelector()
    r1 = format_report(run_eval(eval_set, card, sel), card)
    r2 = format_report(run_eval(eval_set, card, sel), card)
    assert r1 == r2


def test_cli_check_replay_exit_consistent(capsys: pytest.CaptureFixture[str]) -> None:
    # --check-replay must not change the verdict (exit code), only assert replay.
    rc_plain = main([])
    capsys.readouterr()
    rc_replay = main(["--check-replay"])
    out = capsys.readouterr().out
    assert "byte-identical" in out
    assert rc_plain == rc_replay


# --- 2. The bar bites --------------------------------------------------------


def test_passed_follows_bar_rule() -> None:
    eval_set = _toy_set()
    sel = TokenOverlapBaselineSelector()
    # The toy set is lexically separable -> baseline gets both -> 100%.
    res_easy = run_eval(eval_set, _toy_card(bar=0.95), sel)
    assert res_easy.accuracy == 1.0
    assert res_easy.passed
    # A bar above the achieved accuracy fails.
    res_hard = run_eval(eval_set, _toy_card(bar=1.01), sel)
    assert not res_hard.passed


def test_report_states_honest_boundary() -> None:
    eval_set, card = _load_intra_domain()
    report = format_report(run_eval(eval_set, card, TokenOverlapBaselineSelector()), card)
    assert "HONEST BOUNDARY" in report
    assert "NOT agentINVEST's tool-selection" in report
    # The real-measurement follow-on is stated in plain prose (the report is a
    # consumer surface: it names the LLM planner's real selector + the
    # record-then-score integration, carrying NO backlog identifiers).
    assert "the LLM planner's real" in report
    assert "record-then-score" in report


# --- 3. The toy-set guards fire ---------------------------------------------


def test_malformed_set_raises() -> None:
    bad = EvalSet(
        "bad",
        "expected id not in catalogue",
        (ToolSpec("T-A", "A", "a"),),
        (EvalCase("c1", "q", "T-MISSING", (), "r"),),
    )
    with pytest.raises(ValueError, match="malformed"):
        run_eval(bad, _toy_card(0.95), TokenOverlapBaselineSelector())


def test_one_sided_set_raises() -> None:
    # T-B never appears as a confuser -> one-sided -> toy-set guard fires.
    one_sided = EvalSet(
        "one-sided",
        "T-B is only ever the answer",
        (ToolSpec("T-A", "A", "alpha"), ToolSpec("T-B", "B", "beta")),
        (
            EvalCase("c1", "alpha", "T-A", ("T-B",), "r"),
            EvalCase("c2", "beta", "T-B", ("T-A",), "r"),
        ),
    )
    # Make it genuinely one-sided: drop T-B from confusers everywhere.
    one_sided = EvalSet(
        one_sided.set_id,
        one_sided.description,
        one_sided.tools,
        (
            EvalCase("c1", "alpha", "T-A", (), "r"),
            EvalCase("c2", "beta", "T-B", ("T-A",), "r"),
        ),
    )
    problems = two_sidedness_problems(one_sided, ("T-A", "T-B"))
    assert any("never a confuser" in p for p in problems)
    with pytest.raises(ValueError, match="one-sided"):
        run_eval(one_sided, _toy_card(0.95), TokenOverlapBaselineSelector())


# --- Faithfulness + the interface walk in code -------------------------------


def test_intra_domain_set_is_wellformed_and_two_sided() -> None:
    eval_set, card = _load_intra_domain()
    assert eval_set.validate() == []
    assert two_sidedness_problems(eval_set, card.focus_tool_ids) == []
    # The 4 focus tools are exactly the SD-09.1 return-tool family.
    assert set(card.focus_tool_ids) == {
        "SO-09-01-twr",
        "SO-09-01-mwr",
        "SO-09-01-period-linking",
        "SO-09-01-gross-net",
    }


def test_card_makes_single_actor_visible() -> None:
    same = _toy_card(0.95)
    same = EvalCard(
        same.eval_id, same.measures, same.metric, same.bar, same.oracle,
        author="solo", blesser="solo", set_ref="n/a", focus_tool_ids=same.focus_tool_ids,
    )
    assert same.single_actor_authored_and_blessed()
    diff = _toy_card(0.95)
    assert not diff.single_actor_authored_and_blessed()


def test_selector_interface_is_satisfiable_by_an_alternate() -> None:
    # The interface walk, in code: a DIFFERENT mechanism (here a trivial
    # first-token-match selector — a stand-in for "any other selector", e.g.
    # the production LLM one) satisfies the SAME `Selector` Protocol. The contract is
    # (query, tools) -> tool_id with no coupling to the baseline's internals.
    class FirstTokenSelector:
        name = "first-token-stub"

        def select(self, query: str, tools: tuple[ToolSpec, ...]) -> str:
            q = tokenize(query)
            for tool in sorted(tools, key=lambda t: t.tool_id):
                if q & tokenize(tool.search_text()):
                    return tool.tool_id
            return sorted(tools, key=lambda t: t.tool_id)[0].tool_id

    alt: Selector = FirstTokenSelector()
    assert isinstance(alt, Selector)  # runtime_checkable Protocol
    eval_set, card = _load_intra_domain()
    # It runs through the SAME runner over the SAME set and produces a number.
    res = run_eval(eval_set, card, alt)
    assert 0.0 <= res.accuracy <= 1.0


def test_intra_domain_json_loads_cleanly() -> None:
    eval_set, _ = _load_intra_domain()
    # Round-trips through from_dict; tool ids unique; >= 12 cases (not a toy 3-case set).
    assert len(set(eval_set.tool_ids())) == len(eval_set.tool_ids())
    assert len(eval_set.cases) >= 12
    # Sanity: the raw JSON is valid and matches the parsed shape.
    from agentinvest_evals.runner import _SETS_DIR

    raw = json.loads((_SETS_DIR / "intra-domain-bd09-returns.json").read_text(encoding="utf-8"))
    assert raw["set_id"] == eval_set.set_id


# === The gap metric (the net-new runner/verdict work) ========================


def _gap_card(focus: tuple[str, ...]) -> EvalCard:
    return EvalCard(
        eval_id="gap-toy",
        measures="toy gap",
        metric="gap",
        bar=0.95,
        oracle="hand-built",
        author="author-x",
        blesser="UNBLESSED",
        set_ref="n/a",
        focus_tool_ids=focus,
    )


def _two_arm_set(
    within_correct: int, within_total: int, cross_correct: int, cross_total: int
) -> EvalSet:
    """A hand-built two-arm set whose baseline outcome is *controlled*.

    A tool whose text echoes the query verbatim is selected (lexically separable);
    a query that echoes the WRONG tool's text forces a miss. Two tools, T-A / T-B,
    each two-sided. Builds exactly the requested correct/total per arm so the gap
    is a known number under the deterministic baseline.
    """
    tools = (
        ToolSpec("T-A", "Alpha", "alpha alpha alpha distinctive-a"),
        ToolSpec("T-B", "Beta", "beta beta beta distinctive-b"),
    )
    cases: list[EvalCase] = []

    def add(prefix: str, arm: str, correct: int, total: int) -> None:
        # `total` cases for the arm: `correct` hits (query echoes the right tool),
        # the rest misses (query echoes the other tool). Alternate A/B so each
        # focus tool is both an answer and a confuser (two-sidedness).
        for i in range(total):
            want_hit = i < correct
            ans, other = ("T-A", "T-B") if i % 2 == 0 else ("T-B", "T-A")
            echo = ans if want_hit else other
            text = "alpha distinctive-a" if echo == "T-A" else "beta distinctive-b"
            cases.append(EvalCase(f"{prefix}{i}", text, ans, (other,), "toy", office_arm=arm))

    add("w", WITHIN_OFFICE, within_correct, within_total)
    add("x", CROSS_OFFICE, cross_correct, cross_total)
    return EvalSet("two-arm", "hand-built two-arm gap fixture", tools, tuple(cases))


def test_office_arm_is_additive_default_within() -> None:
    # An untagged case (the intra-domain JSON shape) parses as within-office — additive.
    raw = {
        "set_id": "s",
        "description": "d",
        "tools": [{"tool_id": "T-A", "name": "A", "description": "a"}],
        "cases": [
            {
                "case_id": "c1",
                "query": "q",
                "expected_tool_id": "T-A",
                "confusers": [],
                "rationale": "r",
            }
        ],
    }
    s = EvalSet.from_dict(raw)
    assert s.cases[0].office_arm == WITHIN_OFFICE
    # The intra-domain set (untagged) loads with every case within-office.
    intra, _ = _load_intra_domain()
    assert all(c.office_arm == WITHIN_OFFICE for c in intra.cases)


def test_unknown_office_arm_is_rejected() -> None:
    bad = EvalSet(
        "bad",
        "bad arm",
        (ToolSpec("T-A", "A", "a"), ToolSpec("T-B", "B", "b")),
        (
            EvalCase("c1", "a", "T-A", ("T-B",), "r", office_arm="back-office"),
            EvalCase("c2", "b", "T-B", ("T-A",), "r", office_arm=WITHIN_OFFICE),
        ),
    )
    assert any("office_arm" in p for p in bad.validate())


def test_gap_metric_computes_both_arms_gap_and_trigger() -> None:
    # within 9/10 = 90%, cross 6/10 = 60% -> gap 30pp; both limbs fire.
    s = _two_arm_set(within_correct=9, within_total=10, cross_correct=6, cross_total=10)
    g = gap_metric(s, _gap_card(("T-A", "T-B")), TokenOverlapBaselineSelector())
    assert (g.within_correct, g.within_total) == (9, 10)
    assert (g.cross_correct, g.cross_total) == (6, 10)
    assert g.within_accuracy == 0.9
    assert g.cross_accuracy == 0.6
    assert round(g.gap_pp, 6) == 30.0
    assert g.primary_gap_fires  # 30pp > 5pp
    assert g.backstop_fires  # 60% < 90%
    assert g.split_indicated


def test_gap_primary_limb_alone_fires() -> None:
    # within 10/10 = 100%, cross 10/11 ~= 90.9% -> gap ~9.1pp > 5pp (primary fires)
    # while cross >= 90% (backstop clear). Proves the primary limb fires alone.
    s = _two_arm_set(within_correct=10, within_total=10, cross_correct=10, cross_total=11)
    g = gap_metric(s, _gap_card(("T-A", "T-B")), TokenOverlapBaselineSelector())
    assert g.cross_accuracy >= 0.90  # backstop clear
    assert g.primary_gap_fires  # gap > 5pp
    assert not g.backstop_fires
    assert g.split_indicated


def test_gap_backstop_limb_alone_fires() -> None:
    # within 8/10 = 80%, cross 8/11 ~= 72.7% -> gap ~7.3pp. To isolate the backstop
    # we need cross < 90% with gap <= 5pp; build within 7/10=70%, cross 7/11~=63.6%
    # gives gap ~6.4pp (both). Instead within 6/10=60%, cross 6/10=60% -> gap 0pp,
    # cross 60% < 90% -> backstop alone fires, primary clear.
    s = _two_arm_set(within_correct=6, within_total=10, cross_correct=6, cross_total=10)
    g = gap_metric(s, _gap_card(("T-A", "T-B")), TokenOverlapBaselineSelector())
    assert round(g.gap_pp, 6) == 0.0
    assert not g.primary_gap_fires  # gap not > 5pp
    assert g.backstop_fires  # cross 60% < 90%
    assert g.split_indicated


def test_gap_primary_boundary_exact_5pp_does_not_fire() -> None:
    # The primary limb fires on a gap STRICTLY > 5pp; an EXACT 5pp
    # gap must NOT fire. The float-fragile `gap_pp > 5.0` got this wrong for some
    # constructions (e.g. 20/20 vs 19/20, where 1.0 − 0.95 = 5.000…004). The
    # integer-pp limb gets it right for every construction.
    # within 20/20 = 100%, cross 19/20 = 95% -> gap exactly 5pp.
    s = _two_arm_set(within_correct=20, within_total=20, cross_correct=19, cross_total=20)
    g = gap_metric(s, _gap_card(("T-A", "T-B")), TokenOverlapBaselineSelector())
    assert not g.primary_gap_fires  # exactly 5pp -> strictly NOT > 5pp -> clear
    assert not g.backstop_fires  # cross 95% >= 90% -> clear
    assert not g.split_indicated


def test_gap_primary_boundary_just_over_5pp_fires() -> None:
    # A gap one increment over 5pp must fire the primary limb.
    # within 100/100 = 100%, cross 94/100 = 94% -> gap exactly 6pp (> 5pp).
    s = _two_arm_set(within_correct=100, within_total=100, cross_correct=94, cross_total=100)
    g = gap_metric(s, _gap_card(("T-A", "T-B")), TokenOverlapBaselineSelector())
    assert g.primary_gap_fires  # 6pp > 5pp
    assert not g.backstop_fires  # cross 94% >= 90%
    assert g.split_indicated


def test_gap_backstop_boundary_exact_90pct_does_not_fire() -> None:
    # The backstop fires on cross STRICTLY < 90%; an EXACT 90% cross
    # must NOT fire. within 10/10 = 100%, cross 9/10 = 90% -> backstop clear.
    s = _two_arm_set(within_correct=10, within_total=10, cross_correct=9, cross_total=10)
    g = gap_metric(s, _gap_card(("T-A", "T-B")), TokenOverlapBaselineSelector())
    assert not g.backstop_fires  # exactly 90% -> strictly NOT < 90% -> clear
    # (the primary fires here — 10pp gap — so split_indicated is True; this test
    # pins the BACKSTOP boundary alone.)
    assert g.primary_gap_fires


def test_gap_backstop_boundary_just_under_90pct_fires() -> None:
    # Cross one increment under 90% must fire the backstop.
    # within 10/10, cross 89/100 = 89% -> backstop fires.
    s = _two_arm_set(within_correct=10, within_total=10, cross_correct=89, cross_total=100)
    g = gap_metric(s, _gap_card(("T-A", "T-B")), TokenOverlapBaselineSelector())
    assert g.backstop_fires  # 89% < 90%


def test_gap_trigger_is_float_robust_equal_verdict_for_equal_gaps() -> None:
    # THE load-bearing test: three constructions of a mathematically
    # EQUAL 5pp gap must give the SAME verdict. Under the old float `gap_pp > 5.0`,
    # 20/20-vs-19/20 (1.0−0.95=5.000…004) FIRED while 10/100-vs-5/100 (0.10−0.05=
    # 0.05) did NOT — different verdicts for the same gap. The integer-pp limb
    # gives all three the same (correct, clear) verdict.
    a = gap_metric(
        _two_arm_set(within_correct=20, within_total=20, cross_correct=19, cross_total=20),
        _gap_card(("T-A", "T-B")),
        TokenOverlapBaselineSelector(),
    )
    b = gap_metric(
        _two_arm_set(within_correct=10, within_total=100, cross_correct=5, cross_total=100),
        _gap_card(("T-A", "T-B")),
        TokenOverlapBaselineSelector(),
    )
    c = gap_metric(
        _two_arm_set(within_correct=11, within_total=20, cross_correct=10, cross_total=20),
        _gap_card(("T-A", "T-B")),
        TokenOverlapBaselineSelector(),
    )
    # All three are an exact 5pp gap -> primary must be clear for ALL three.
    assert a.primary_gap_fires == b.primary_gap_fires == c.primary_gap_fires is False
    # And the at-least-one of these floats genuinely differs from a clean 5.0,
    # proving the integer limb is not just getting lucky on the representation.
    assert a.gap_pp != 5.0 or c.gap_pp != 5.0  # at least one float-mis-represents 5pp


def test_gap_no_split_when_both_limbs_clear() -> None:
    # within 10/10 = 100%, cross 10/10 = 100% -> gap 0pp, cross >= 90% -> NO-SPLIT.
    s = _two_arm_set(within_correct=10, within_total=10, cross_correct=10, cross_total=10)
    g = gap_metric(s, _gap_card(("T-A", "T-B")), TokenOverlapBaselineSelector())
    assert not g.primary_gap_fires
    assert not g.backstop_fires
    assert not g.split_indicated


def test_gap_metric_requires_both_arms() -> None:
    # A single-arm set cannot compute a gap (the goal-(f)/T0 "no defensible
    # within-office control" guard) -> raises rather than fabricating a number.
    within_only = _two_arm_set(within_correct=5, within_total=10, cross_correct=0, cross_total=0)
    with pytest.raises(ValueError, match="BOTH office arms"):
        gap_metric(within_only, _gap_card(("T-A", "T-B")), TokenOverlapBaselineSelector())


def test_gap_report_shows_both_limbs_and_honest_boundary() -> None:
    s = _two_arm_set(within_correct=9, within_total=10, cross_correct=6, cross_total=10)
    g = gap_metric(s, _gap_card(("T-A", "T-B")), TokenOverlapBaselineSelector())
    report = format_gap_report(g, _gap_card(("T-A", "T-B")))
    # The metric is visibly the WHOLE two-part trigger, not half of it.
    assert "within-office accuracy" in report
    assert "cross-office  accuracy" in report
    assert "gap (within - cross)" in report
    assert "primary  (gap > 5pp)" in report
    assert "backstop (cross-office < 90%)" in report
    assert "trigger verdict" in report
    # The honest boundary is stated in terms.
    assert "HONEST BOUNDARY" in report
    assert "NOT a verdict on" in report
    # The real split / no-split decision is attributed in plain prose (the report
    # is a consumer surface: it names the LLM planner's real selector + the
    # record-then-score integration, carrying NO backlog identifiers).
    assert "the LLM planner's REAL selector" in report
    assert "record-then-score" in report


def test_gap_report_is_byte_identical_across_runs() -> None:
    s = _two_arm_set(within_correct=9, within_total=10, cross_correct=6, cross_total=10)
    card = _gap_card(("T-A", "T-B"))
    r1 = format_gap_report(gap_metric(s, card, TokenOverlapBaselineSelector()), card)
    r2 = format_gap_report(gap_metric(s, card, TokenOverlapBaselineSelector()), card)
    assert r1 == r2
    g1 = gap_metric(s, card, TokenOverlapBaselineSelector())
    g2 = gap_metric(s, card, TokenOverlapBaselineSelector())
    assert gap_replay_hash(g1) == gap_replay_hash(g2)


def test_cross_office_set_is_wellformed_two_sided_and_two_armed() -> None:
    eval_set, card = _load_cross_office()
    assert eval_set.validate() == []
    assert two_sidedness_problems(eval_set, card.focus_tool_ids) == []
    arms = {c.office_arm for c in eval_set.cases}
    assert arms == {WITHIN_OFFICE, CROSS_OFFICE}  # both arms present (gap computable)
    # The cross-office confusers genuinely straddle the FO<->MO boundary: every
    # cross-office case pairs a front-office tool (FO-*) with a middle-office one
    # (MO-*) somewhere in {expected} U {confusers}.
    for c in eval_set.cases:
        if c.office_arm != CROSS_OFFICE:
            continue
        members = {c.expected_tool_id, *c.confusers}
        has_fo = any(m.startswith("FO-") for m in members)
        has_mo = any(m.startswith("MO-") for m in members)
        assert has_fo and has_mo, f"{c.case_id} is tagged cross-office but does not span FO<->MO"


def test_cross_office_set_is_genuinely_adversarial_not_a_toy() -> None:
    # The baseline must NOT score 100% on the cross-office arm (a 100%-pass is the
    # "100%-pass is suspect" toy failure) and NOT 0% (impossibly hard);
    # a genuinely adversarial set lands strictly in between.
    eval_set, card = _load_cross_office()
    g = gap_metric(eval_set, card, TokenOverlapBaselineSelector())
    assert 0 < g.cross_correct < g.cross_total
    # And it bites: the baseline degrades cross-office relative to within-office,
    # so the gap metric demonstrably fires (the instrument is proven to bite).
    assert g.split_indicated


def test_cli_gap_path_runs_and_default_path_unchanged(capsys: pytest.CaptureFixture[str]) -> None:
    # The single-set default path still exits non-zero on its bar miss.
    rc_default = main([])
    capsys.readouterr()
    assert rc_default == 1  # intra-domain baseline FAILs the 95% bar (unchanged)
    # The --gap path runs and exits 0 (it does NOT CI-fail on a baseline
    # split-indicated — the honest boundary; exit guards harness integrity only).
    rc_gap = main(["--gap"])
    out = capsys.readouterr().out
    assert rc_gap == 0
    assert "gap metric" in out
    assert "SPLIT-INDICATED" in out  # the baseline result on this set
    assert "HONEST BOUNDARY" in out
