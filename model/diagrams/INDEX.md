# OpenIM Diagrams

The visual companion to the [OpenIM model](../README.md).

## GitHub-native diagrams

These render in any GitHub markdown view — the readable form, no build step.

| # | Diagram | What it shows |
|---|---|---|
| 01 | [Layer stack](01-layer-stack.md) | OpenIM's position in the standards landscape — agent channel above, FIBO / ISDA CDM / identifiers / wire formats / reporting / governance around it. |
| 02 | [Business Domain map](02-business-domain-map.md) | The 17 Business Domains grouped by office tag (Front / Middle / Back / Cross-cutting / Commercial), with Service-Domain counts. Graphical companion to the summary table in [`../service-domains/INDEX.md`](../service-domains/INDEX.md). |
| 03 | [Conceptual ERD — core entities](03-conceptual-erd.md) | The 38-entity core entity model — organised into six groups (primary spine, reference and identity, risk, computed-result and metadata, operational, strategy) — and the key relationships among them. |
| 04 | [Asset class × form of holding](04-asset-class-form-of-holding-matrix.md) | The orthogonality matrix — the nine asset classes (E-09) against the four form-of-holding specialisation packs, every crossing walked to its entity-and-Service-Domain home. The demonstration that the asset-class axis and the form-of-holding axis are independent. |

## Static site

The full model — every Business Domain drilled to Service-Operation depth, every entity page, the landscape and the entity ERD — is rendered as a navigable static HTML + SVG site by the Python generator at [`../../tools/diagrams/`](../../tools/diagrams/), committed at [`../../exports/diagrams/`](../../exports/diagrams/). The markdown under `model/service-domains/`, `model/entities/` and `model/ownership-map.md` is the only authoritative source; the generator parses it directly. See [`../../tools/diagrams/README.md`](../../tools/diagrams/README.md) for the build invocation and the per-view details.

The attribute-level core ERD is the D2 source at [`d2/core-erd.d2`](d2/core-erd.d2); the layer-stack rendering is [`d2/layer-stack.d2`](d2/layer-stack.d2). Both render to SVG via the D2 binary as their own build step alongside the static site.
