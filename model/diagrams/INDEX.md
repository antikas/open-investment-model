# OpenIM diagrams

These diagrams provide visual routes into the [OpenIM model](../README.md). Start with the Business Domain map for capabilities or the conceptual entity diagram for information concepts.

## Markdown diagrams

The diagrams in this directory render in GitHub without a separate build step.

| # | Diagram | What it shows |
|---|---|---|
| 01 | [Layer stack](01-layer-stack.md) | OpenIM's relationship to adjacent standards and model layers. |
| 02 | [Business Domain map](02-business-domain-map.md) | The 17 Business Domains, grouped by office label with Service Domain counts. |
| 03 | [Conceptual entity diagram](03-conceptual-erd.md) | The 38 core entities and their main relationships. |
| 04 | [Asset class and form of holding](04-asset-class-form-of-holding-matrix.md) | How asset classes cross the specialisation packs used for different holding forms. |

## Generated static views

The Python generator under [`../../tools/diagrams/`](../../tools/diagrams/) reads the model Markdown and writes navigable HTML and SVG views to [`../../exports/diagrams/`](../../exports/diagrams/).

The source remains under `model/service-domains/`, `model/entities/` and `model/ownership-map.md`. See the [diagram generator guide](../../tools/diagrams/README.md) for build commands and output details.

The attribute-level core entity diagram uses [`d2/core-erd.d2`](d2/core-erd.d2). The layer stack uses [`d2/layer-stack.d2`](d2/layer-stack.d2). The build renders both D2 files to SVG.
