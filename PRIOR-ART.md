# Related standards and models

OpenIM sits among established standards, public models and implementation platforms. This document records their scope and explains how OpenIM relates to them.

Its purpose is scope alignment. The record includes earlier buy-side models and current adjacent work.

## OpenIM's scope

OpenIM links two views of an institutional investment firm:

- a capability map of Business Domains and Service Domains
- a canonical entity model for the information those capabilities use

Generated exports express the same source in forms used by architecture, data and graph tools.

The table below shows where adjacent artefacts fit.

| Need | Primary artefact | OpenIM relationship |
|---|---|---|
| Firm-level capability map | OpenIM Service Domains | Core OpenIM scope |
| Canonical investment entities | OpenIM entities with FIBO mappings | Core OpenIM scope and semantic alignment |
| Financial concepts and relationships | FIBO | Reuse or map where concepts align |
| Products and transaction lifecycles | FINOS Common Domain Model | Reference at the transaction layer |
| External identifiers | LEI, FIGI, ISIN and other schemes | Store and resolve across identifiers |
| Financial messages | ISO 20022, FIX and FpML | Use at interoperability boundaries |
| Private-capital reporting | ILPA templates | Use as reporting inputs and outputs |
| Investment performance presentation | GIPS standards | Apply as domain rules |
| AI risk and mitigation vocabulary | FINOS AI Governance Framework | Use as an external governance reference |

## Capability and data models

### BIAN

[BIAN's Service Landscape](https://bian.org/deliverables/service-landscape/) is a reference structure that categorises and organises Service Domains for banking. A BIAN Service Domain represents a discrete business capability.

BIAN provides the structural precedent for OpenIM's capability map. OpenIM uses its own Business Domains, Service Domains and definitions for institutional investment management.

### FIBO

The [Financial Industry Business Ontology](https://spec.edmcouncil.org/fibo/) defines financial concepts and the relationships between them. EDM Council hosts FIBO, and the Object Management Group standardises it. FIBO is published in formats that people and software can read.

OpenIM maps canonical entities to FIBO concepts where the meanings align. The [entity-level alignment](model/fibo-alignment.md) records each mapping and its status. OpenIM retains local concepts for firm capabilities and information that fall outside a suitable FIBO term.

### FINOS Common Domain Model

The [FINOS Common Domain Model](https://cdm.finos.org/docs/cdm-overview/) is a machine-readable model for financial products, trades and lifecycle events. Its published scope includes product, event and process models, with supporting reference data.

OpenIM refers to CDM for product and transaction-lifecycle concepts. OpenIM's primary scope is the wider firm capability map and the canonical information used across that map.

### FINOS `glue`

[FINOS `glue`](https://github.com/finos/glue) describes itself as an enterprise data model for the buy side, tailored to wealth and asset managers. It includes concepts such as parties, business relationships, investment strategies, instruments and portfolios.

FINOS archived the repository in May 2023, leaving it read-only. OpenIM treats `glue` as direct prior art for open buy-side data modelling. OpenIM adds a linked service-domain map and maintains model-derived exports from the same source.

### Quadra

[Quadra](https://github.com/quadra-platform) is a current investment data management platform for asset managers and asset owners. Its public description covers ingestion, entity resolution, master data, lineage and an investment book across public and private markets.

The full platform and data model are source available under the Business Source License 1.1. A [public sample](https://github.com/quadra-platform/data-model-sample) exposes part of the model under the MIT licence.

Quadra and OpenIM overlap in investment-data vocabulary. They have different artefact types: Quadra is a platform with an operating data model, while OpenIM is an implementation-neutral reference model. This comparison uses Quadra's public materials only.

## Reporting and performance standards

### ILPA templates

The [Institutional Limited Partners Association reporting templates](https://ilpa.org/industry-guidance/templates-standards-model-documents/ilpa-templates-hub/ilpa-reporting-template/) define reporting formats for private-capital fees, expenses, carried interest and performance.

OpenIM uses ILPA templates as external reporting structures for relevant private-market capabilities. Canonical entity identity remains a separate concern inside OpenIM.

### GIPS standards

The [Global Investment Performance Standards](https://www.gipsstandards.org/standards/) provide requirements for calculating and presenting investment performance. CFA Institute publishes provisions for firms, asset owners and verifiers.

OpenIM treats GIPS concepts as domain rules for performance and reporting capabilities. OpenIM records the entities and capability boundaries that an implementation can use when applying those rules.

## Messaging and identifiers

### ISO 20022, FIX and FpML

[ISO 20022](https://www.iso20022.org/about-iso-20022) provides a common approach for developing financial messages and a central dictionary of business items. [FIX](https://www.fixtrading.org/standards/) and [FpML](https://www.fpml.org/) provide established protocols for trading and derivatives use cases.

OpenIM treats these as interoperability artefacts. Service Domains can reference the messages used at their boundaries while keeping the capability definition independent of a wire format.

### Identifier schemes

Investment firms use several external identifier schemes, including LEI, FIGI and ISIN. Their coverage and purpose differ.

OpenIM entities store external identifiers and aliases alongside a firm-specific internal key. This structure lets implementations reconcile records across providers and schemes. The model does not claim authority over the external identifiers themselves.

## AI governance

### FINOS AI Governance Framework

The [FINOS AI Governance Framework](https://air-governance-framework.finos.org/) publishes a catalogue of generative-AI risks and mitigations for financial services. It also maps its content to external regulations and standards.

Where OpenIM refers to AI governance, this framework supplies an external risk and mitigation vocabulary. OpenIM's model remains usable without an AI runtime.

## Other software and models

Open-source trading platforms, portfolio libraries and analytics tools are implementation artefacts. They may consume OpenIM concepts or overlap with part of its domain.

OpenIM assesses a specific project by artefact type and scope. A runnable platform, a message standard, an ontology and a reference model can describe related subject matter while serving different purposes.

## OpenIM's bounded contribution

The repository supports four specific statements about OpenIM:

1. It links a capability decomposition of an institutional investment firm to a canonical entity model.
2. It publishes the model in plain-text source under the MIT licence.
3. It generates architecture, schema and graph representations from that source.
4. It includes explicit entity-resolution structures and documented mappings to adjacent standards.

The prior-art record places those features in context. FINOS `glue` demonstrates earlier open buy-side data modelling. Quadra demonstrates current adjacent work. BIAN, FIBO and CDM provide important structural or semantic precedents.

Corrections and missing primary sources can be proposed through the [contribution process](CONTRIBUTING.md).
