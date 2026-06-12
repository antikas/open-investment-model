# agentINVEST eval substrate (`reference/evals/`) — builder runbook

> **Builder surface.** This directory is the agentINVEST **eval substrate** — the
> measuring instrument, built before the things it measures (the eval-first
> thesis). It is a builder-facing surface: eval cards and this README carry bar
> provenance and build framing. The reader-facing description of agentINVEST
> lives in `../README.md` and stays clean of this.

## What this is — and the one thing it is not (the honest boundary)

The eval harness is the **measuring instrument**: an offline, deterministic,
replay-stable golden-set runner that loads an eval set, runs a `Selector` over
each case, and reports a **tool-selection accuracy number against a write-time
bar**. It is built *before* the thing it measures (the eval-first thesis): the
substrate the whole proof staircase stands on.

**The harness is what is proven here.** At this stage it measures a
**declared deterministic baseline** selector (token-overlap). That baseline's
accuracy is a **harness-validation datapoint** — it calibrates the instrument. It
is **NOT** agentINVEST's tool-selection accuracy, and it is **NOT** a verdict on
the single-orchestrator bet (the architecture's one open risk: a single
orchestrating loop's tool-RAG mis-selecting near-duplicate operations).

The real measurement exists **only** when the production LLM `.plan()` tool-RAG
selector's selections are scored through this same harness against the same golden
set (via the record-then-score adapter described under "How a selector is scored"
— the production `.plan()` is async/durable, so it is *recorded then scored*, not
wrapped in a synchronous proxy). A green from the baseline would say the baseline
is decent on this set; a red says
the baseline is weak. Neither is a statement about the production selector. Do not
read the baseline's number as "tool selection proven" or "cross-office risk
retired" — that substitution (proving an adjacent construct and narrating it as
the production one) is the equivalence-substitution failure the build is armoured
against: a system's own success claims are not verification; evaluation must run
against an independent oracle.

The runner prints this honest-boundary statement on every run, so the number is
never read in isolation.

## Run it

From `reference/` (Windows host launches into WSL2 automatically, same as
`dbt:build`; native Mac/Linux runs locally):

```sh
pnpm evals                 # run the intra-domain eval with the baseline selector
pnpm evals -- --check-replay   # also assert two in-process runs are byte-identical
pnpm evals -- --gap        # run the gate-E gap metric over the cross-office set
pnpm evals -- --gap --replay-hash   # the gap run's portable, encoding-independent CI key
```

Or directly in the uv env (inside WSL2 on Windows):

```sh
cd reference/python
uv run python -m agentinvest_evals --check-replay
```

**Exit code:** `0` iff the selector's accuracy `>=` the declared bar; **non-zero
on a bar miss** (so it is CI-gate-ready) or on a malformed / one-sided set. The
`reference/` CI pipeline that would invoke this on every push is a **later item —
named here, not built**: the harness is wired to fail a build; nothing yet runs it
as a gate.

**Replay / regression property:** the report carries no timestamps, paths, PIDs or
randomness; the baseline selector is exact-integer and order-stable; so two runs
are byte-identical *within one output encoding*. `--check-replay` proves it
in-process; two separate process invocations of `pnpm evals` produce identical
output on the same machine.

**Cross-machine CI replay key (encoding-robust):** the *rendered console stdout*
is NOT a safe cross-machine key — the report's non-ASCII (em-dashes, `>=`)
serialises to different bytes under a Windows cp1252 console vs a Linux UTF-8 CI
runner, so hashing stdout would spuriously differ across machines on an identical
run. The portable key is the **canonical JSON of the structured `RunResult`**
(`sort_keys`, `ensure_ascii` → pure ASCII, SHA-256'd):

```sh
pnpm evals -- --replay-hash    # prints ONLY the encoding-independent hash
```

This hash is identical on Windows-console and Linux-CI for the same run. A CI gate
pins THIS hash, not the stdout hash. `--check-replay` also asserts the two
in-process runs share this hash (not just identical stdout strings).

## Where the code lives (and why)

The harness **code** lives in the existing Python workspace, not in a second uv
project — one lockfile, one toolchain (SSOT). The eval **content** (sets + cards)
lives here under `reference/evals/sets/`.

```
reference/evals/
  README.md                                  # this builder runbook (author≠blesser + the honest boundary)
  sets/
    intra-domain-bd09-returns.json           # the within-office eval SET (tool catalogue + golden cases)
    intra-domain-bd09-returns.card.md         # its eval CARD (measures / bar / oracle / author / blesser)
    cross-office-front-vs-middle.json         # the cross-office torture SET + within-office control arm (office-arm-tagged)
    cross-office-front-vs-middle.card.md       # its eval CARD (the gate-E gap metric / oracle / author / blesser)
  transcripts/                                 # recorded real-planner selections (record-then-score inputs)
    intra-domain-bd09-returns.claude-sonnet-4-6.transcript.json
    cross-office-front-vs-middle.claude-sonnet-4-6.transcript.json

reference/python/src/agentinvest_evals/      # the harness package (in the one uv workspace)
  __init__.py
  __main__.py                                # `python -m agentinvest_evals`
  schema.py                                  # EvalCase / EvalSet / EvalCard — the SSOT format
  selector.py                                # the Selector Protocol + the deterministic baseline
  runner.py                                  # the offline runner: single-set accuracy>=bar + the gate-E gap metric; non-zero on a bar miss
  record_then_score.py                       # the record-then-score adapter: real-planner transcript -> deterministic re-score
reference/python/tests/test_evals_harness.py  # replay-stability, bar-bites, toy-set-guard, interface-walk, gap-metric + two-part-trigger tests
reference/scripts/evals-run.sh + evals-run.mjs # the Windows->WSL2 launcher (mirrors dbt-build.*)
```

## The eval-set + eval-card format (the reused SSOT)

- **Eval set** (`*.json`): a `tools` catalogue (`tool_id` / `name` / `description`)
  + `cases`, each a `query` → `expected_tool_id` + the near-duplicate `confusers`
  + a `rationale`. Parsed by `EvalSet.from_dict`.
- **Eval card** (`*.card.md`): a `--- key: value ---` front-matter block declaring
  `eval_id` / `measures` / `metric` / `bar` / `oracle` / `author` / `blesser` /
  `set_ref` / `focus_tool_ids`, plus a human-readable body. Parsed by
  `EvalCard.from_markdown`.

**What extends additively, and what does not.** The eval-set / eval-card **data
format** is the reused SSOT and *does* extend additively: a cross-office set is
just another `EvalSet`, cross-office confuser *pairs* are just more confuser ids,
the **office-arm tag** is one additive `office_arm` field on each case
that defaults to `within-office` (so the original untagged set parses unchanged),
and the production selector consumes exactly this `EvalSet` shape (its selections
scored via the record-then-score adapter above). Adding fields is additive — keep
the existing fields stable.

**The gate-E gap metric was NOT an additive eval set — it is
net-new runner/verdict structural work.** Gate-E's
cross-office verdict is *two* sub-population accuracies (within-office and
cross-office), their *difference* (the gap), and a *two-part trigger* (gap `> 5pp`
primary OR cross-office `< 90%` backstop). None of that is expressible through the
original single-set runner: `RunResult.passed` is a single `accuracy >= bar`, and
the default `main` path runs one set against one `bar`. So the runner gained a
partitioned-by-office-arm run path (`gap_metric` → `GapResult`), the gap
computation, the two-limb trigger, and a `--gap` CLI mode —
**structural runner work, not just another set file** — while the
single-set `accuracy >= bar` default path is kept working unchanged alongside it.

## How a selector is scored (and how the production selector integrates)

What the harness actually does is narrow and precise: it **scores a set of
selections against the golden set**. For each case it needs one thing — the
`tool_id` a selector picked for that query — and it checks it against the label.

The `Selector` contract — `Selector.select(query, tools) -> selected_tool_id`, no
`.fit()`, no precomputed index, no score vector, no shared state — is the
**deterministic-selector contract**: it is the interface a *synchronous,
in-process, deterministic* selector implements directly, scored case-by-case
inside `run_eval`'s plain loop. The lexical token-overlap baseline
implements it directly.

**The production selector does NOT implement this synchronous contract
directly.** Per the project's stack-and-topology decision record,
it is the `InvestmentOperation` virtual object's `.plan()` step — an LLM tool-RAG
call that is **async, network-bound, durably journaled, and non-deterministic**.
It cannot be wrapped in a synchronous `Selector` proxy and scored live: doing that
would score a synchronous stand-in, not the real durable `.plan()` step — the
**probe-substitution failure** the build is armoured against (a stand-in's
success is not verification of the production construct). Nor is the answer to
make this interface `async` — the synchronous,
pure, replay-stable `run_eval` is exactly what gives the harness its
byte-identical-replay property.

The production selector integrates via a **record-then-score adapter**
(`agentinvest_evals/record_then_score.py`, built): run the real `.plan()` selector once over the set,
**record its per-query selections as a fixed transcript** (a `query -> tool_id`
record, captured from the production durable run), then **score that transcript
through this same harness** — the same scoring code, the same golden set, the same
bar. The harness scores selections; what differs between the baseline and the
production selector
is *how the selections are produced* (live sync call vs recorded async transcript),
not the scoring. So the reused SSOT is the **golden set + the scoring/verdict
code**, fed by a recorded transcript for the async production selector.

(The synchronous-contract reuse is verified in code for *deterministic* selectors:
`test_selector_interface_is_satisfiable_by_an_alternate` runs a different
synchronous mechanism through the same runner. That test does NOT exercise the
async/durable path — that fit is the record-then-score adapter, built with the
production selector.)

## The gate-E gap metric — the make-or-break instrument

`pnpm evals -- --gap` runs the **gate-E gap metric** over the cross-office set.
In one run, the runner partitions the cases by their `office_arm` tag and computes:

- **within-office accuracy** — selection accuracy on the **control** cases (the
  near-duplicate confusers all sit inside one office);
- **cross-office accuracy** — selection accuracy on the **torture** cases (the
  confusers straddle the front-office ↔ middle-office boundary);
- the **gap** = within-office − cross-office (the primary split signal — the
  cross-office degradation the ~5-per-office split specifically fixes);
- the **two-part trigger** (gate-E's declared rule): *split-indicated* if **gap > 5pp**
  (primary) **OR** **cross-office < 90%** (backstop).

The gap is measured **apples-to-apples in one run**: the same selector ranks over
the same single catalogue for both arms; the only difference is whether the
near-duplicate sits across the office boundary. That surfaces *cross-office*
degradation relative to a **difficulty-matched** within-office control. The
cross-office torture families are authored from the SD specs (the oracle):
front-office desk mark (BD-06) vs middle-office independent mark / IPV (SD-08.6)
and the other middle-office valuation producers (SD-08.1/08.2/08.3); and
front-office mandate self-monitoring (SD-05.2) vs middle-office risk-limit
governance (SD-07.7) / concentration limits (SD-07.4) / the pre-trade compliance
engine (SD-10.1). The within-office control arm reuses **all 16 BD-09
return cases from the intra-domain set verbatim — including its three hard misses
(C05/C10/C13)** so
the control is difficulty-matched, not easier than the cross arm — and adds a
within-middle-office BD-08 valuation family.

**Two honest qualifications (see the eval card for detail).** (1) Of the three
cross-office misses, X01 and X04 are genuine front-office text-echo wins; **X05 is
a dead-Jaccard-tie tie-break artefact** (its candidates tie at exactly 0.2500 and
the deterministic smallest-`tool_id` tie-break decides it — the intra-domain
set's C13/C14 precedent). The tie-break logic is deliberately unchanged; renaming `MO-risk-limit`
would flip X05 and move the gap 22.5pp → 10pp, but both limbs fire either way so
the verdict is unchanged. (2) With 8 cross-office cases the arm resolves at 12.5pp
per case, so the 90% backstop cannot be hit exactly at its boundary (it means
"≤ 7/8"); densifying the cross arm to ≥ ~16–20 cases is a forward improvement
before the production selector is scored through this metric.

**The trigger is computed in integer percentage-point space**: the
primary fires iff the gap strictly exceeds 5pp and the backstop iff cross-office
strictly drops below 90%, both via exact integer cross-multiplication of the raw
counts (the discipline `selector.py` uses for its Jaccard ranking) — never a float
`>` / `<`. A float gap (`within_acc − cross_acc`) is representation-fragile at the
boundary: `1.0 − 0.95` and `0.10 − 0.05` are the same 5pp gap but land on
different sides of a float `> 5.0`. The integer limbs give the same (correct)
verdict for every construction of an equal gap, and honor the rule's strictness
(an exact 5pp gap / exact 90% cross does NOT fire).

**The honest boundary for the gap metric — load-bearing.** What is
**proven** here is the **gap metric**: that it computes the two sub-population
accuracies + the gap + the two-part trigger, and **fires correctly**. The
**baseline selector's within / cross / gap numbers are a harness-validation
datapoint, NOT a verdict on whether to split the architecture.** Specifically:

- gate-E's **"within-office < 95% ⇒ the catalogue / tool-RAG is broken"** applies
  to **the real (production) selector**, not to a lexical baseline — a lexical baseline
  below 95% within-office is *expected* and says nothing about the catalogue;
- gate-E's **"gap > 5pp ⇒ split the architecture"** applies to the **real
  selector**, not the baseline — a baseline `SPLIT-INDICATED` does **not** mean
  "the single-orchestrator bet is lost" or "cross-office risk confirmed."

Reading the baseline's gap as a split verdict is the **equivalence-substitution**
failure — a system's own success claims are not verification; evaluation must run
against an independent oracle. The real split /
no-split decision exists **only** when the production `.plan()` selector runs through
this same metric (via the record-then-score adapter above). For that reason
`--gap` **does not exit non-zero on a baseline split-indicated** — its exit code
guards only the harness's own integrity (that the gap computed cleanly over both
arms; non-zero on a malformed / one-sided / single-arm set or a replay failure).
The real-selector gate decides the exit semantics of a split-indicated verdict
when the production selector runs through the metric.

If gate-E ever does fire for the real selector, the upgrade is **~5 specialist
*selectors* behind a router** (the model's office tags) — never "agents" — the
escalation path named in the project's stack-and-topology decision record,
built then, not here.

## Author ≠ blesser (three-role eval governance)

Each eval set/card records two **distinct** roles:

- **author** — who wrote the set and labelled the cases.
- **blesser** — a *different* actor who certifies the set is genuinely adversarial
  (the confusers are near-duplicates per the source spec) and correctly labelled.

A single-actor author-and-bless is **visible by construction**: the card carries
both fields, and the runner prints a `GOVERNANCE WARNING` when `author ==
blesser`. Each set is authored by one actor and blessed by a **different,
independent reviewer in fresh context** (three-role separation): the reviewer
reads the set without the author's narration, independently certifies
adversariality + labelling against the source specs, and is recorded as the
blesser in the card only once that independent review is clean (an unblessed set
carries `blesser: UNBLESSED` until then). Authoring-and-blessing a set in one
actor's context is the
exact single-actor trust collapse the three-role discipline forbids — so the
substrate makes the absence of a blesser loud, not silent.

## The intra-domain eval

`sets/intra-domain-bd09-returns.{json,card.md}` — within-office tool-selection over
**BD-09 SD-09.1 Performance Measurement's** four near-duplicate return tools
(time-weighted / money-weighted / strike-period-linking / gross-vs-net). The tool
differentiae are **derived from the SD-09.1 Service Operation descriptions** (the
oracle: `model/service-domains/BD-09-performance-and-analytics/SD-09.1-performance-measurement.md`),
not asserted. Bar: **gate-E within-office ≥ 95%** (the declared write-time bar). Each of
the four focus tools appears as both a correct answer and a confuser (the
two-sidedness guard rejects a one-sided toy set). The composite / currency /
reconcile Service Operations sit in the catalogue as additional tools so selection
is realistic.

## The cross-office torture eval + gap metric

`sets/cross-office-front-vs-middle.{json,card.md}` — the make-or-break gate-E set.
Cross-office torture pairs spanning the front-office ↔ middle-office boundary, plus
a within-office control arm, in one office-arm-tagged set so the gap is computed
apples-to-apples (see "The gate-E gap metric" above for the families and the
honest boundary). The differentiae are **derived from the BD-05/06/07/08/10 SD
specs** (the oracle named in the card), not asserted. Run with `pnpm evals --
--gap`. Each cross-office case's confusers genuinely straddle the office boundary
(a `FO-*` tool paired with an `MO-*` tool); the within-office arm is a real,
difficulty-matched same-office control (it carries the intra-domain set's hard
misses). The
baseline is genuinely stressed (it does not pass or fail by construction): it
scores 85% on the within-office control arm (it misses the same hard cases the
intra-domain run
does) and degrades to 62.5% on the cross-office torture arm — a 22.5pp gap — so the
gap metric demonstrably **fires** — proving the *instrument* bites, **not** that
the architecture must split (the honest boundary).

## What is out of scope here (named, not absorbed)

- Treating a recorded planner score as the **of-record architecture verdict**. The
  record-then-score adapter is built (`record_then_score.py`) and recorded
  transcripts of the real planner ship under `transcripts/` — but the baseline
  numbers measured by the harness-validation selector remain harness validation,
  and a gate-E verdict on the production selector is taken only when that gate is
  formally run, not implied by the transcripts' presence here.
- The **actual ~5-per-office specialist split** — gate-E *fires* the split as a
  verdict (for the real selector); **building** the split is the escalation path
  named in the project's stack-and-topology decision record, not this work.
- The `reference/` **CI pipeline** that runs the harness as a gate — a later item.
- The further eval arms (breach detection, shadow-accounting and compliance
  oracles) and real-tool execution (the eval here is over the tool *specs*) —
  later items.
