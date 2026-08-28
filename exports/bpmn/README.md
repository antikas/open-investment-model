# Illustrative BPMN processes

> These Business Process Model and Notation (BPMN) files are hand-authored, non-normative illustrations. They are outside the canonical OpenIM model.

## Why these files are separate

OpenIM defines business capabilities and canonical entities. Its Service Operations are an unordered vocabulary. The model does not define process sequence, swimlanes, gateways or triggers because firms make those design choices locally.

The ArchiMate, JSON Schema, OWL, SHACL and property-graph exports are generated from the model source. BPMN cannot be generated from the current model because the required sequence information is absent.

The two files in this directory show how selected OpenIM capabilities and entities could be used in a process. They may lag the model and do not pass the determinism or coverage gates applied to generated exports. Each file carries the same qualification in its `bpmn:documentation` element.

## Capital-call lifecycle

[`capital-call-lifecycle.bpmn`](capital-call-lifecycle.bpmn) illustrates a private-markets capital call across three lanes:

- The fund or general partner issues a call and later issues distributions.
- The limited partner funds the call by its due date.
- The fund administrator records the contribution and updates the commitment position.

The flow includes decisions for a late payment and a recallable distribution. Its task names use the OpenIM vocabulary for commitments, calls, distributions and commitment balances.

## NAV-strike workflow

[`nav-strike.bpmn`](nav-strike.bpmn) illustrates a governed net asset value (NAV) strike across two lanes:

- A deterministic calculation produces the NAV and waits before publication.
- An operator reviews the result and approves or rejects publication.

The workflow records an approved publication once. A rejection ends the process without publication.

## Validate the files

Both files use BPMN 2.0 XML and include a `BPMNDiagram` interchange layer. The Object Management Group schemas are vendored under [`schema/`](schema/) for offline validation:

```python
from lxml import etree

schema = etree.XMLSchema(etree.parse("schema/BPMN20.xsd"))
for file_name in ("capital-call-lifecycle.bpmn", "nav-strike.bpmn"):
    schema.assertValid(etree.parse(file_name))
```

The vendored set contains `BPMN20.xsd` and its required imports and includes.
