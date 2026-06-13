---
eval_id: cross-office-front-vs-middle-gap
measures: the gap metric -- within-office vs cross-office tool-selection accuracy, the gap, and the two-part split trigger -- over front-office vs middle-office near-duplicate operations
metric: gap = within-office accuracy - cross-office accuracy; two-part trigger (gap > 5pp primary OR cross-office < 90% backstop)
bar: 0.95
oracle: model/service-domains/BD-05-portfolio-management/SD-05.2-portfolio-management-and-monitoring.md, BD-06-trading-and-execution/SD-06.2-trade-execution.md + SD-06.6-derivatives-and-otc-trade-management.md, BD-07-investment-risk/SD-07.4-concentration-and-exposure-risk.md + SD-07.7-investment-risk-reporting-and-limits-governance.md, BD-08-valuation-and-pricing/SD-08.1-security-pricing.md + SD-08.2-independent-mark-to-model-valuation.md + SD-08.3-private-asset-valuation.md + SD-08.6-independent-price-verification-and-price-challenge.md, BD-10-investment-compliance-and-guideline-monitoring/SD-10.1-investment-guideline-monitoring.md, and BD-09 SD-09.1 for the reused within-office return family (the differentiae are derived from these SD specs, not asserted)
author: set authors
blesser: independent review (blessed 2026-05-31; author != blesser satisfied)
set_ref: cross-office-front-vs-middle.json
focus_tool_ids: [FO-mark-desk, MO-ipv, FO-monitor-mandate, MO-risk-limit, MO-mark-to-model, MO-price-source, MO-private-mark, MO-concentration-limit, MO-compliance-engine]
notes: The selector measured here is a declared deterministic baseline (token-overlap) -- the gap NUMBERS are a harness-validation datapoint, NOT a verdict on whether to split the architecture. The split interpretation is reserved for the real selector run through this metric via record-then-score.
---

# Eval card — cross-office (front vs middle) tool-RAG torture set + the gap metric

## What this eval measures

The **gap metric** over front-office ↔ middle-office
near-duplicate operations. In one office-arm-tagged run, the harness computes:

- **within-office accuracy** — selection accuracy on the **control** cases (the
  near-duplicate confusers all sit inside one office);
- **cross-office accuracy** — selection accuracy on the **torture** cases (the
  near-duplicate confusers straddle the front-office ↔ middle-office boundary);
- the **gap** = within-office − cross-office (the primary signal — the
  degradation the ~5-per-office split specifically fixes);
- the **two-part trigger**: *split-indicated* if **gap > 5pp** (primary) **OR**
  **cross-office < 90%** (backstop).

The gap is measured **apples-to-apples in one run**: the same selector ranks over
the same single tool catalogue for both arms; the only difference between the arms
is whether the near-duplicate sits across the office boundary. That is the whole
point of running a within-office control arm in the same set — it surfaces the
*cross-office* degradation **relative to a difficulty-matched within-office
control**.

**The within-office control is difficulty-matched (not a cleaner-than-cross
baseline).** It reuses the BD-09 intra-domain cases **verbatim — all 16,
including the three the BD-09 baseline genuinely misses** (C05, C10, C13, which
mis-pick the `composite` tool on the "composite" bait), with their
`composite`/`currency`/`reconcile` confusers carried into the catalogue so they
behave exactly as in the BD-09 set. So the within-office arm reproduces the BD-09 hard
misses (13/16 on the BD-09 cases) rather than scoring an inflated 100% — the gap
measures cross-office degradation, not a set-difficulty difference between the
arms. (An earlier draft of this set dropped C05/C10 and removed C13's confuser,
inflating the within-office arm to 100% and the gap to 37.5pp; the difficulty-
matched control gives a fair gap of 22.5pp.)

## The cross-office torture families (and why they are genuinely adversarial)

Authored from the SD specs (the oracle). Two families:

**Family 1 — front-office mark vs middle-office independent mark / IPV.** The
front-office desk mark (`FO-mark-desk`, BD-06: the trader's own valuation to run
the book) vs the middle-office **independent price verification** (`MO-ipv`,
SD-08.6). This is the sharpest cross-office near-duplicate in the model: SD-08.6
*verifies "the front-office or model marks"* — i.e. the **same instrument value**
is produced by the desk for its own decisions and independently re-checked by the
middle office as a control. They share all the valuation vocabulary; the
differentia is *who produces it and for what governance purpose* (front-office
self-mark vs middle-office independent control), which spans the office boundary.
The middle-office valuation **producers** — `MO-price-source` (SD-08.1, sources a
quote), `MO-mark-to-model` (SD-08.2, models a value), `MO-private-mark` (SD-08.3,
private-asset fair value) — are the within-office siblings carried as confusers so
the selector cannot win on office-tag vocabulary alone.

**Family 2 — front-office mandate/guideline self-monitoring vs middle-office
regulatory pre-trade rule / risk limit.** The front-office portfolio
mandate-and-guideline self-monitoring (`FO-monitor-mandate`, SD-05.2: the
manager's *own* oversight) vs the middle-office independent functions:
`MO-risk-limit` (SD-07.7, the independent risk function's governed limit
framework), `MO-concentration-limit` (SD-07.4, concentration-and-exposure limits)
and `MO-compliance-engine` (SD-10.1, the authoritative pre-trade compliance gate
over the coded mandate and regulatory rules). The SD-05.2 spec itself names both
boundaries as confusable in its open extensions: *"SD-05.2 monitors as the
manager's own oversight; BD-07 is the independent risk function"* and *"SD-05.2
monitors drift and risk; SD-10.1 runs the compliance rule engine."* All four
"monitor the portfolio against limits/mandate"; the differentia — the manager's
own watch vs the independent governed gate — is exactly the office boundary.

Each cross-office family is built **two-sided** (the front-office tool is both a
correct answer and a confuser; so is the middle-office one), so the set cannot be
gamed by a one-directional bias. The within-office control arm reuses **all 16
of** the BD-09 SD-09.1 return cases verbatim (TWR / MWR / period-linking /
gross-net, all middle office — including the BD-09 baseline's three hard misses, so the
control is difficulty-matched, not easier than the cross arm) and adds a
within-middle-office BD-08 valuation family (`MO-price-source` /
`MO-mark-to-model` / `MO-ipv` / `MO-private-mark`) — a third confuser family,
*within* one office.

## Two honest qualifications on the baseline's misses and resolution

**The cross-office misses are X01, X04, X05 — but only two are text-echo wins.**
On this set the baseline misses three cross-office cases. X01 (desk-mark-vs-IPV)
and X04 (desk-mark-vs-model) are genuine **text-echo wins**: the front-office
`FO-mark-desk` tool's text lexically dominates the query ("desk", "marked"), so
the wrong-office near-duplicate out-matches. **X05 (FO-monitor-vs-risk-limit) is
not a text-echo win — it is a dead-Jaccard-tie tie-break artefact.** Its two
candidates `FO-monitor-mandate` and `MO-risk-limit` tie at **exactly** Jaccard
0.2500; X05 misses only because `FO-monitor-mandate` sorts before `MO-risk-limit`
and the deterministic tie-break takes the lexicographically smallest `tool_id`
(it carries no query signal — see `selector.py`, the BD-09 C13/C14 precedent).
The tie-break logic is **deliberately not changed** (changing it would move the
number; the BD-09 C14 precedent). The dependence is recorded so it is not a
silent surprise: **renaming `MO-risk-limit` (e.g. to `AO-risk-limit`) would flip
X05 to a pass**, moving cross-office 62.5% → 75% and the gap 22.5pp → 10pp — a
deterministic-but-arbitrary tie-break dependence. With the difficulty-matched
control, both trigger limbs fire on either outcome (22.5pp and 10pp both exceed
5pp, 62.5% and 75% both below 90%), so the rename does not change the *verdict*,
only the headline number.

**The cross-office arm's resolution is 12.5pp per case at n=8.** With 8
cross-office cases, cross-office accuracy can only take values in {0, 12.5, 25, …,
87.5, 100}%. The 90% backstop sits **between** 87.5% (7/8) and 100% (8/8), so it
cannot be hit *exactly* at its boundary — it effectively means "≤ 7/8 cross-office
correct," a one-miss-tolerance gate. Each cross-office case is worth 12.5pp of the
gap. This is fine for a baseline-validation run (the gap-primary limb is
doing the work; the backstop is the degenerate-uniformly-hard-set guard), but
**densifying the cross-office arm to ≥ ~16–20 cases is a forward improvement**
before the real selector is scored through this metric, so the 90% backstop
and the 5pp gap are both finely resolvable. (Adding cases would change the
headline number and require a re-bless; a doc qualification is sufficient here.)

**Read the gap, not the absolute numbers, as the signal — but only for the real
selector.** The gap is the cleaner signal because it is robust to a
uniformly-hard catalogue: a lexical baseline is weak on near-duplicates in *both*
arms, so its within-office and cross-office numbers are both low. The metric's job
is to surface whether the cross-office arm degrades *relative to* the within-office
control. Whether that degradation means "split the architecture" is a question
about the **production** selector, not this baseline (see the honest boundary).

## Author ≠ blesser (independent-bless eval governance)

- **author:** the set authors derived the confuser differentiae from the
  BD-05/06/07/08/10 SD specs.
- **blesser:** an **independent reviewer** (a different actor, fresh context),
  blessed 2026-05-31. Per the independent-bless discipline the authors did **not**
  self-bless. The independent review read this set blind,
  independently re-derived its fidelity to the SD specs, confirmed the cross-office
  confusers genuinely span the front↔middle boundary (SD-08.6 names IPV's target as
  "the front-office or model marks" verbatim; not a toy set), and certified it; a
  follow-up re-review re-confirmed after the within-office control was made
  difficulty-fair (reusing the genuinely-hard BD-09 cases). Author ≠ blesser is
  genuinely satisfied — distinct actors, fresh context, structural separation. The
  runner still prints a `GOVERNANCE WARNING` when `author == blesser`; the
  `single_actor_authored_and_blessed()` guard remains live for future sets.

## The honest boundary — load-bearing

The thing **proven** here is the **gap metric**: that it computes within-office
accuracy, cross-office accuracy, the gap, and the two-part trigger (gap > 5pp
primary OR cross-office < 90% backstop), and **fires correctly**. That is the
deliverable.

The **baseline selector's within / cross / gap numbers are a harness-validation
datapoint — NOT a verdict on whether to split the architecture.** In particular:

- the interpretation **"within-office < 95% ⇒ the catalogue / tool-RAG is
  broken"** applies to **the real selector**, not to a lexical baseline. A
  lexical baseline scoring below 95% within-office is **expected** (the BD-09
  baseline's was 81.25%) and says **nothing** about the catalogue.
- the interpretation **"gap > 5pp ⇒ split the architecture"** applies to the
  **real selector**, not the baseline. A baseline `SPLIT-INDICATED` does **not**
  mean "the single-orchestrator bet is lost" / "cross-office risk confirmed."

Reading the baseline's gap as a split verdict is the **equivalence-substitution**
failure (a system's own success claims are not verification; evaluation must run
against an independent oracle): proving an adjacent
construct (a lexical baseline's gap) and narrating it as the production construct
(the real selector's architecture verdict). The real split / no-split decision
exists **only** when the LLM planner's `.plan()` tool-RAG selector runs through this
same metric. That `.plan()` selector is async / network-bound / durably journaled,
so it integrates via a **record-then-score adapter** (record its
per-query selections as a fixed transcript, score that through this same metric) —
**not** a synchronous `Selector` proxy. The `--gap` CLI path therefore does **not**
exit non-zero on a baseline `SPLIT-INDICATED`; it guards only the harness's own
integrity (that the gap metric computed cleanly over both arms).

If the trigger ever does fire for the real selector, the upgrade is **~5 specialist
*selectors* behind a router** (the model's office tags), never "agents" — the
later escalation, built then, not here.
