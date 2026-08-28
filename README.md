# OpenIM: Open Investment Model

> A shared map of what an institutional investment firm does and the information it uses.

OpenIM is an open, MIT-licensed reference model for institutional investment management. It connects a capability map of the firm to a canonical entity model. The same source also generates most machine-readable exports.

Business and technology teams can use OpenIM to describe firm scope, compare systems, shape data models and prepare context for software. The model is vendor neutral and does not prescribe an implementation.

## Why OpenIM exists

Different parts of an investment firm often describe the same capability or entity in different ways. Platform maps, internal architecture and specialist standards each cover part of the picture.

OpenIM provides a firm-level reference that teams can inspect and adapt. It gives stable names to business capabilities and the information those capabilities use. Each firm supplies its own data and calculation rules, with firm-specific controls.

The model helps teams frame questions such as:

- *What is this fund's net asset value (NAV) per unit, and what changed since the last strike?*
- *What are our assets under management (AUM) by strategy and asset class?*
- *What is our counterparty exposure and collateral coverage?*
- *Where do two systems disagree on a position or valuation?*
- *Do two records describe the same legal entity?*

OpenIM identifies the capabilities and entities involved in those questions. It also records the relationships between them.

## What the model contains

OpenIM has two connected parts:

- **[Business capabilities](model/service-domains/INDEX.md)** describe what the firm does. The map contains **17 Business Domains and 171 Service Domains**. Each Service Domain defines a bounded capability and lists its Service Operations.
- **[Canonical entities](model/entities/INDEX.md)** describe the information the firm uses. The model contains **86 entities**, with a **generalised core of 38** and five specialisation packs.

The specialisation packs add detail for different forms of holding and operation:

- public markets
- fund operations
- private markets
- derivatives
- real assets

The entity model uses one Legal Entity master with roles such as issuer, counterparty, manager or custodian. Internal keys, aliases and external identifiers support entity resolution across source systems.

OpenIM also includes an [ownership map](model/ownership-map.md), [FIBO alignment](model/fibo-alignment.md), a [glossary](model/glossary.md) and [diagrams](model/diagrams/INDEX.md).

## How to use OpenIM

1. Start with the [Business Domain index](model/service-domains/INDEX.md) to find the area of work you are describing.
2. Open a Service Domain to review its definition, boundary and operations.
3. Follow its entity links into the [canonical entity catalogue](model/entities/INDEX.md).
4. Compare those capabilities and entities with your local systems or data models.
5. Choose a generated format from [`exports/`](exports/) when a tool needs the model in machine-readable form. Treat the two BPMN files as illustrations only.

A reference model is a common starting point for local design. Each implementation decides its organisation, ownership, controls and technology. Record the OpenIM release or commit used in your work so later reviews can trace the same source.

The public website at [openinvestmentmodel.org](https://openinvestmentmodel.org/) provides a browsable view of the released model.

## The model at a glance

The office labels below group domains for navigation. Firms can organise the same capabilities in different ways.

| # | Business Domain | Office | Service domains |
|---|---|---|---|
| BD-01 | Investment Strategy & Allocation | Front | 14 |
| BD-02 | Securities Research & Selection | Front | 8 |
| BD-03 | Manager & Fund Investment | Front | 9 |
| BD-04 | Direct & Co-Investment | Front | 12 |
| BD-05 | Portfolio Management | Front | 13 |
| BD-06 | Trading & Execution | Front | 6 |
| BD-07 | Investment Risk | Middle | 8 |
| BD-08 | Valuation & Pricing | Middle | 6 |
| BD-09 | Performance & Analytics | Middle | 9 |
| BD-10 | Investment Compliance & Guideline Monitoring | Middle | 9 |
| BD-11 | Treasury, Cash & Collateral | Middle | 8 |
| BD-12 | Investment Operations & Servicing | Back | 17 |
| BD-13 | Investment Data & Reporting | Cross-cutting (data) | 12 |
| BD-14 | Enterprise Risk, Control & Assurance | Cross-cutting (corporate) | 9 |
| BD-15 | Distribution, Product & Client Management | Commercial | 16 |
| BD-16 | Enterprise Governance & Accountability | Cross-cutting (corporate) | 5 |
| BD-17 | Corporate Services & Resources | Cross-cutting (corporate) | 10 |

## Relationship to existing standards and models

OpenIM is a firm-level reference model. It links to specialist standards where their concepts match:

- **BIAN** provides the structural precedent of a Service Landscape for banking. OpenIM uses a comparable capability-modelling approach for institutional investment.
- **FIBO** defines financial concepts and their relationships. OpenIM maps its entities to FIBO terms where the semantics align.
- **FINOS Common Domain Model** describes financial products and transaction lifecycle events. OpenIM places that transaction detail within a wider view of the firm.
- **FINOS `glue`** is prior art for open buy-side data modelling. Its repository was archived in 2023.
- **Quadra** is current adjacent work in investment data management. Its public sample exposes part of a wider platform data model.

See [PRIOR-ART.md](PRIOR-ART.md) for the detailed comparison and source links.

## Exports

[`exports/`](exports/) contains formats for architecture and data tooling, including graph use cases. ArchiMate, JSON Schema, OWL, SHACL and property-graph exports are generated from the model source for each release.

The two BPMN files are hand-authored, non-normative illustrations. They are not generated from the model and may lag it. Each export README explains its scope and loading instructions.

## Local validation

The model is plain Markdown and can be read on GitHub without installing anything. Python 3.9 or later is required to run the structural validator:

```sh
git clone https://github.com/antikas/open-investment-model.git
cd open-investment-model
python tools/openim-validate/validate.py
```

The validator checks identifiers, links, required sections and cross-file counts. Exit code `0` means those structural checks passed. See the [validator guide](tools/openim-validate/README.md) for details.

## Use from an AI or coding tool

The read-only [OpenIM MCP server](mcp/README.md) lets compatible tools search and retrieve the released model with source links and version provenance:

```sh
npx -y @openinvestmentmodel/openim-mcp
```

The server exposes model retrieval. Investment advice and transaction execution sit outside its scope.

## Project boundary

- The public repository contains the reference model, generated exports and two illustrative BPMN files.
- Firms may use all or part of the model and add local detail.
- Implementations retain responsibility for their data, controls and decisions.
- The MIT licence permits commercial and non-commercial use, subject to its terms.

The canonical machine-readable project identity is [`metadata/openim.json`](metadata/openim.json).

## Repository layout

```text
open-investment-model/
|-- README.md                    Project introduction and reader route
|-- PRIOR-ART.md                 Relationship to adjacent standards and models
|-- CONTRIBUTING.md              Contribution process
|-- CODE_OF_CONDUCT.md           Community standards
|-- GOVERNANCE.md                Decision and release governance
|-- CITATION.cff                 Citation metadata
|-- LICENSE                      MIT licence
|-- metadata/                    Canonical project identity
|-- model/                       Reference-model source
|   |-- service-domains/         Business and Service Domain map
|   |-- entities/                Core entities and specialisation packs
|   |-- diagrams/                Model-derived visual views
|   |-- glossary.md              Domain vocabulary
|   |-- ownership-map.md         Entity ownership by Service Domain
|   `-- fibo-alignment.md        Entity-level FIBO alignment
|-- exports/                     Generated formats and illustrative BPMN
`-- tools/
    |-- openim-validate/         Structural validator
    `-- diagrams/                Diagram generation
```

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) before proposing a model change. [GOVERNANCE.md](GOVERNANCE.md) explains how decisions and releases are handled. Prior-art corrections are especially useful when they include a primary source.

## Licence and maintainer

OpenIM is available under the [MIT licence](LICENSE). It is maintained by [Georgios Antikatzidis](https://github.com/antikas), an enterprise architect with more than 25 years in financial services.
