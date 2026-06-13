---
eval_id: bd09-sd0901-intra-domain-return-selection
measures: within-office tool-selection accuracy over BD-09 SD-09.1's near-duplicate return tools
metric: within-office selection accuracy (correct selections / total cases)
bar: 0.95
oracle: model/service-domains/BD-09-performance-and-analytics/SD-09.1-performance-measurement.md (the Service Operation descriptions — the tool differentiae are derived from the SD spec, not asserted)
author: set authors
blesser: independent review (blessed 2026-05-31; author != blesser satisfied — see reference/evals/README.md)
set_ref: intra-domain-bd09-returns.json
focus_tool_ids: [SO-09-01-twr, SO-09-01-mwr, SO-09-01-period-linking, SO-09-01-gross-net]
notes: The selector measured here is a declared deterministic baseline (token-overlap) — a harness-validation datapoint, NOT agentINVEST's tool-selection accuracy and NOT a verdict on the single-orchestrator bet.
---

# Eval card — BD-09 SD-09.1 intra-domain return-tool selection

## What this eval measures

**Within-office (intra-domain) tool-selection accuracy** over the near-duplicate
return tools of BD-09 SD-09.1 Performance Measurement. A selector is shown a
realistic analyst query and must pick the single correct return tool from the
SD-09.1 catalogue; the eval reports the fraction it gets right.

This is the **baseline** within-office arm. The bar is
**≥ 95%** within-office selection accuracy: if a real selector fails the
within-office bar, the catalogue / tool-RAG design is broken — *not* a topology
problem. The **cross-office** torture arm and the cross-office-minus-within-office
gap metric are a **separate eval set**, not this eval.

## The oracle (where the labels come from)

`model/service-domains/BD-09-performance-and-analytics/SD-09.1-performance-measurement.md`.
The four focus tools and their differentiae are **derived from the SD-09.1
Service Operation descriptions**, not asserted:

- **SO-09-01-twr — time-weighted return:** removes the effect of external
  cash-flow timing; the basis for benchmark and peer comparison.
- **SO-09-01-mwr — money-weighted return:** the IRR on the dated cash-flow series;
  the investor's actual experienced return; the private-markets standard basis.
- **SO-09-01-period-linking — strike period returns:** daily / monthly /
  quarterly / YTD / since-inception returns, by linking sub-period returns.
- **SO-09-01-gross-net — gross and net returns:** return before and after
  management fees, performance fees and expenses.

Why they are genuinely confusable (so the set is not a toy): all four are
return calculations sharing the vocabulary "return", "period", "fees", "cash
flow". TWR and MWR are the sharpest pair — both are returns over a cash-flow
series, and TWR is *defined by removing* exactly the flow-timing sensitivity that
MWR is *defined by keeping*. Period-linking shares TWR's sub-period-linking
mechanism. Gross/net is a transform that can apply to any of the others.

**The difficulty is uneven, and the discriminating power is concentrated on the
TWR/MWR axis — read the score by axis, not as a uniform number.** The gross-net
(C04/C08/C12/C16) and period-linking (C03/C07/C11/C15) cases are lexically easier:
the query echoes distinctive vocabulary ("before/after management fees",
"year-to-date / since-inception / quarterly"), so they separate by wide token-
overlap margins. The genuinely hard axis is the **TWR vs MWR** near-duplicate pair
(C01/C02/C05/C06/C09/C10/C13/C14), where the misses and the thinnest margins all
live. A selector could score ~75% by nailing only the lexical-echo cases **without
discriminating the TWR/MWR pair at all** — so a high *aggregate* score does not by
itself imply genuine near-duplicate discrimination. The precise claim: a selector
that scores high **on the TWR/MWR cases** has discriminated the sharpest
near-duplicate pair. (The honest boundary already prevents the headline number
being read as a verdict; this qualification keeps the *card's* adversariality
claim honest about which cases carry the discriminating power.)

## Author ≠ blesser (independent-bless eval governance)

- **author:** the set authors authored this set and card.
- **blesser:** an **independent reviewer** (fresh context), blessed
  2026-05-31. The independent review read this set blind,
  independently re-derived its fidelity to SD-09.1, confirmed the confusers are
  genuine near-duplicates (the baseline's three misses land on the true TWR/MWR
  semantic-inversion axis — not a toy set), and certified it; a follow-up
  re-review re-confirmed. Author ≠ blesser is
  genuinely satisfied — distinct actors, fresh context, structural separation. The
  `single_actor_authored_and_blessed()` guard remains live for future sets, and the
  runner still prints a GOVERNANCE WARNING when `author == blesser`.

## The honest boundary

The number this eval emits is the **baseline selector's** accuracy — a
**harness-validation datapoint**. It is **NOT** agentINVEST's tool-selection
accuracy and **NOT** a verdict on the single-orchestrator bet. The *harness* is
what is proven. The real measurement exists only when **the LLM planner's** real
`.plan()` tool-RAG selector's selections are scored through this same harness against this
same set. That `.plan()` selector is async / network-bound / durably journaled,
so it integrates via a **record-then-score adapter** (record its
per-query selections as a fixed transcript, score that) — *not* by wrapping it in
a synchronous `Selector` proxy, which would score a stand-in rather than the real
selector. A green here would mean the baseline is decent on this set; a red here
means the baseline is weak — neither says anything about the production selector.
