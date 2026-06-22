# Illustrative BPMN processes

> **NON-NORMATIVE. ILLUSTRATIVE. HAND-AUTHORED.**
> These two BPMN process models are **not generated from OpenIM** and are **not a maintained parallel model**. They are hand-authored illustrations, nothing more. Do not read them as normative process guidance.

## What these are

OpenIM is a **reference model** for institutional investment management — an operating-model decomposition (Business Domains and Service Domains) plus a canonical entity model. It is the capability-and-data layer. **It is not a process library.** OpenIM does not prescribe how a firm sequences its work; firm-specific process flows — the order of steps, who hands off to whom, where the gateways sit — are deliberately out of scope, because they are firm-specific design choices, not reference-model facts.

Every other published export (the ArchiMate model, the JSON Schema bundle, the FIBO-aligned ontology) is **generated** from the model's markdown source: re-run the generator on an unchanged model and you get a byte-identical artefact. That generate-from-the-source discipline is what keeps the exports honest — they cannot drift from the model, because they *are* the model, projected.

These two BPMN files are the **single, deliberate exception** to that discipline. The model carries **no process-sequence data** at all — Service Operations are an *unordered* vocabulary, with no ordering, no swimlanes, no gateways, and no triggers anywhere in the source. BPMN therefore **cannot be generated** from OpenIM. Rather than omit the artefact entirely, two processes are hand-authored **once**, as illustrations of how OpenIM capabilities and entities *could* compose into a process. They show the shape of a flow built on OpenIM; they are not a claim about how any firm must run.

Because they are hand-authored and not generated:

- they are **not subject to the determinism or coverage gates** the generated exports pass;
- they are **not regenerated** when the model changes, and may lag it — they are illustrations, not a derived surface;
- each file carries the same non-normative statement inline, in a `bpmn:documentation` element on the process, so the exception travels with the file even when this README does not.

## The two processes

### `capital-call-lifecycle.bpmn` — the private-markets capital-call lifecycle

The cash-event lifecycle of a private-markets fund commitment, illustrated across three lanes:

- **Fund / GP-Manager** — establishes the commitment, issues the capital-call notice (the drawdown against the commitment), deploys the called capital to the investment, and later issues distributions.
- **Investor / LP** — funds the drawdown by the due date.
- **Fund Administrator** — records the contribution, tracks any recallable distribution back into callable capacity, and updates the commitment's cumulative-called and cumulative-distributed position.

Two exclusive gateways: *LP funded on time?* (record the contribution, or invoke the default remedy) and *distribution recallable?* (restore the recallable amount to callable capacity, or proceed straight to the position update).

The task names are drawn from the OpenIM capital-call and distribution vocabulary — the LP commitment, the capital call as a drawdown against it, the distribution typed as return of capital / income / gain, the recallable flag, and the commitment-position update — so the flow is recognisably built on OpenIM, while staying an illustration.

### `nav-strike.bpmn` — the NAV-strike governed workflow

The governed-NAV pattern, illustrated across two lanes:

- **NAV Engine (deterministic calculation)** — on a period-close trigger, strikes the NAV (gross market value plus accrued income, less fees, plus hedge P&L), and — only on approval — publishes it exactly once, journaled.
- **Operator (human approver)** — reviews the struck NAV at the high-stakes approval gate.

One exclusive gateway: *approve the publish?* — approve routes to the exactly-once journaled publish and a *NAV published* end state; reject routes to a *strike aborted, no publish* end state. The deterministic engine computes; the human approves the high-stakes publish. The task names are drawn from the OpenIM fund-accounting and NAV vocabulary (the NAV strike, the review-and-sign-off gate) and the valuation record that the strike produces.

## Positioning

OpenIM is a **reference model**, not a standard, and these BPMN do not change that. They make **no** "standard" claim and prescribe **no** firm process. OpenIM builds on FIBO for instrument and legal-entity semantics and is complementary to the transaction- and reporting-layer standards; these illustrations sit alongside that positioning, not above it.

## Validating these files

Both `.bpmn` files are valid **BPMN 2.0** (the OMG interchange XML) and carry a `BPMNDiagram` interchange layer, so they open and render in any BPMN 2.0 tool (bpmn.io, Camunda Modeler, Signavio). The OMG BPMN 2.0 XSD set is vendored under [`schema/`](schema/) for offline validation:

```python
from lxml import etree
schema = etree.XMLSchema(etree.parse("schema/BPMN20.xsd"))
for f in ("capital-call-lifecycle.bpmn", "nav-strike.bpmn"):
    schema.assertValid(etree.parse(f))   # raises if invalid
```

The vendored schema files are the unmodified OMG BPMN 2.0 schemas (`BPMN20.xsd` and its includes/imports: `Semantic.xsd`, `BPMNDI.xsd`, `DI.xsd`, `DC.xsd`).
