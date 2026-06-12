"""OpenIM Hybrid D static-site diagram generator.

Parses the OpenIM model markdown (service-domains, entities, ownership map,
d2 ERD source), builds the capability and entity graphs in memory, lays them
out via Graphviz (sfdp for capability views, dot for ERD), and emits a
static HTML+SVG site to `dist/`.

Markdown is the only authoritative source: no intermediate DSL, no `.c4`
middleman. Per ADR-0045 (Hybrid D static-site generator).
"""
