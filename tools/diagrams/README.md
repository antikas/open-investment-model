# Hybrid D — OpenIM static-site diagram generator

A small Python generator that parses the OpenIM model markdown directly, lays out the BD → SD → Service Operation capability graph and the entity ERD via Graphviz, and emits a static HTML+SVG site to `dist/`. The markdown is the only authoritative source; no derived DSL artefact (no `.c4`, no intermediate JSON) sits between the writer's hand and the rendered page.

The Mermaid interval diagrams (`model/diagrams/01..04.md`) stay in place — they are the source-code-readable form and render natively on GitHub. The D2 attribute-level core ERD (`model/diagrams/d2/core-erd.d2`) and the D2 layer-stack (`model/diagrams/d2/layer-stack.d2`) continue to be rendered by the D2 binary in CI; the Hybrid D generator links to those outputs from its ERD page.

## What it produces

| Page | What it shows |
|---|---|
| `index.html` | Landing page — links to every other view. |
| `landscape.html` | The 17 Business Domains, grouped by office tag, with cross-Business-Domain arrows derived from the per-SD Inputs / Outputs and the structured `**Consumes:**` / `**Produces:**` declarations. Boxes click through to per-BD pages. |
| `bd-NN.html` | One per Business Domain. Renders every Service Domain in the BD as a cluster, every Service Operation as a node inside the cluster, internal edges between SDs, and one collapsed arrow per external BD touched. |
| `sd-NN.M.html` | One per Service Domain. Full Service Operation list, declared owned / consumed entities, upstream / downstream Service Domains. |
| `entity-X-NN.html` | One per entity (core + four specialisation packs — `E-`, `PM-`, `PB-`, `DR-`, `RA-`). Names the owning + consuming Service Domains, the foreign-key targets, and the specialisation parent (where present). |
| `erd.html` | The pack-grouped entity overview ERD — nodes per entity with FK + Specialises edges. The attribute-level core ERD is rendered separately by D2 (`entities/core/core-erd.svg`); the layer stack is at `layer-stack.svg`. |

In-page navigation: every SVG node carries an `<a href="...">`, so clicking a Business Domain box on the landscape opens its `bd-NN.html`, clicking a Service Domain cluster opens its `sd-NN.M.html`, clicking an entity opens its `entity-X-NN.html`. A small JS helper ([svg-pan-zoom](https://github.com/bumbu/svg-pan-zoom) 3.6.2, MIT, ~30 KB) adds pan / zoom inside each diagram.

## How to build it

From the OpenIM repo root:

```bash
python -m pip install -r tools/diagrams/requirements.txt
python tools/diagrams/build.py --out dist/
```

The generator parses the markdown, builds the graphs in memory, hands DOT source to Graphviz (`dot` for the landscape + ERD, `dot` with `compound=true` for per-BD views), and writes the rendered SVG into the HTML template. Exit codes:

- `0` — every declared BD / SD / Service Operation / entity is rendered.
- `1` — a parser raised on an unhandled markdown shape, or Graphviz failed to lay a graph out, or the coverage assertion found a declared item missing from `dist/`.

Local preview:

```bash
python -m http.server 8000 -d dist/
# open http://localhost:8000/
```

## What it parses

| Source | What is extracted |
|---|---|
| `model/service-domains/INDEX.md` | Top-level structure (validated by the cross-reference check). |
| `model/service-domains/BD-NN-*/README.md` | BD id, name, office tag. |
| `model/service-domains/BD-NN-*/SD-NN.M-*.md` | SD id, name, `**Applies:**` tag, `## Purpose`, `## Service Operations` bullets, `## Inputs and outputs` narrative SDs, `## Entities` structured `**Consumes:**` / `**Owns:**` / `**Produces:**` lines. |
| `model/entities/core/E-NN-*.md` and `model/entities/specialisations/<pack>/X-NN-*.md` | Entity id, name, `**Specialises:**` declaration (specialisation packs), FK targets from the attribute table, `## Owned and consumed by` `**Owned by:**` / `**Consumed by:**` lines. |
| `model/ownership-map.md` | Per-entity authoritative ownership pattern (single owner / key-partitioned / faceted / co-owned) and the owning Service Domain(s). |
| `model/diagrams/d2/core-erd.d2` | Not parsed by the generator — the D2 binary renders this source directly to SVG in the CI workflow (`dist/entities/core/core-erd.svg`); the generator's ERD page links to that output. |

The parser is strict by construction. Any of the following raise `ParseError` and exit non-zero:

- An unknown H2 heading in an SD file (the whitelist: `## Purpose`, `## Service Operations`, `## Inputs and outputs`, `## Entities`, `## Standards`, `## Open extensions` — see `parser/service_domains.py:SD_KNOWN_H2`). Entity files and BD READMEs carry richer per-file H2 sets and are not whitelisted at this layer.
- A missing required field (`**Applies:**` on an SD, `## Service Operations` section, `## Owned and consumed by` section, `**Owned by:**` line on an entity).
- A Service Domain or entity reference that does not resolve to a declared id (after the full model is parsed).
- A malformed ownership-map row (no entity id in column 1, or no Service Domain id in column 2).
- A specialisation entity's filename prefix that does not match its declared pack directory.

Silent skipping is not permitted: the parser exits loudly so the build pipeline cannot quietly render a partial model. The unknown-H2 strict mode on SD files exists for the same reason — an unrecognised heading is a parse failure, not something to skip past.

## How it lays graphs out

Two Graphviz engines are used:

- **`dot`** for the landscape, per-BD views, and the entity ERD overview — clustered, directed, hierarchical layouts with rank separation tuned for the BD / SD / SO nesting depth.
- **`dot` with `compound=true`** for per-BD pages so edges connect SD clusters as a whole rather than terminate on one SO node inside the cluster.

Render-quality tuning lives in [`render/dot_gen.py`](render/dot_gen.py): node spacing, rank separation, palette, cluster fill colours per office tag, splines, and per-edge style for narrative vs structured derivation. The palette is the office-tagged five-colour scheme the model uses across the landing page and the v0.1 Mermaid diagrams (Front blue / Middle purple / Back green / Cross-cutting amber / Commercial rose).

**Edge kinds and their visual styles.** The capability graph carries six edge kinds with two render shapes:

| Edge kind | Source | Render shape |
|---|---|---|
| `consumes-sd` | Structured `**Consumes:**` line | Solid, default colour |
| `produces-sd` | Structured `**Produces:**` line | Solid, default colour |
| `narrative-input` | SD-specific narrative `Inputs:` reference | Solid, default colour |
| `narrative-output` | SD-specific narrative `Outputs:` reference | Solid, default colour |
| `narrative-bd-input` | BD-level aggregate `Inputs:` reference | Dashed, gray60, penwidth 0.8 |
| `narrative-bd-output` | BD-level aggregate `Outputs:` reference | Dashed, gray60, penwidth 0.8 |

The visual distinction lets a practitioner reading the rendered SVG separate "this BD has structured / SD-specific dependencies into that one" (the strong-signal solid edges) from "this BD narratively references that one as aggregate function context" (the weaker-signal dashed BD-aggregate edges). At a per-pair level, a "mixed" pair (both shapes present for the same source/destination BD) renders solid: the stronger structured signal wins for the landscape overview.

If Graphviz fails to lay a large graph out cleanly even after tuning, the engineered fallback is per-BD baking only — the landscape becomes a link hub of BD boxes without cross-BD edges. That fallback is not active in this build (every page is rendered with full cross-BD edges); enabling it is a deliberate decision, not an automatic degradation.

## Dependency tree

The generator imports two third-party Python libraries beyond the standard library:

- **[Jinja2](https://github.com/pallets/jinja) 3.x** — MIT — the HTML template engine. Used purely for the page chrome; no template inheritance, no filters beyond `safe`. A 200-line hand-rolled template renderer could replace it; Jinja2 is preferred because every Python developer already knows it.
- **[graphviz](https://github.com/xflr6/graphviz) 0.21** — MIT — a thin Python binding around the Graphviz CLI. Used only as a convenience; the generator invokes the `dot` binary directly via `subprocess` in [`render/layout.py`](render/layout.py). Replaceable in ~30 lines if the dependency footprint matters.

Both ship pure-Python; neither carries native code. The Graphviz binary itself (`dot`, `sfdp`) must be installed on the system (apt-get on Linux / Homebrew on macOS / the binary releases on Windows). The CI workflow at `.github/workflows/diagrams.yml` installs it as a build step.

The rendered site embeds one vendored client-side JS file:

- **[svg-pan-zoom](https://github.com/bumbu/svg-pan-zoom) 3.6.2** — MIT — vendored at [`render/static/svg-pan-zoom.min.js`](render/static/svg-pan-zoom.min.js). Size 29,784 bytes. SHA-256 `9c8fc41b3359e699990766dd7a943595d234a80c880a90dfc14b920a273b99d8`. Source: `https://cdn.jsdelivr.net/npm/svg-pan-zoom@3.6.2/dist/svg-pan-zoom.min.js`. Vendored rather than fetched at build time as a supply-chain discipline (no `curl|sh`-style network fetches in the build pipeline). To bump the version: download the new release, replace the file, recompute the SHA-256 with `Get-FileHash svg-pan-zoom.min.js -Algorithm SHA256` (PowerShell) or `shasum -a 256 svg-pan-zoom.min.js` (POSIX), update this README, and commit.

Hand-rolled static HTML + SVG was preferred over any JS framework. The output is static HTML + SVG + the one ~30 KB vendored JS file; no SPA toolkit, no bundler, no build-step transpilation, no client-side router.

## Tests

Golden-output tests for each of the seven source-file shapes the generator parses live under [`tests/`](tests/). Run them with either:

```bash
python -m pytest tools/diagrams/tests/
python -m unittest discover tools/diagrams/tests/
```

The fixtures (under `tests/fixtures/`) mirror the real repo's structure on a minimal 1-BD / 2-SD / 4-entity scale, so tests run in well under a second and exercise the parsers end-to-end. Negative tests confirm the strict-parser contract (missing `**Applies:**` raises, a non-bullet line under `## Service Operations` raises).

## Layout (the directory)

```
tools/diagrams/
  build.py                  — main entry point (the script CI invokes)
  requirements.txt          — Jinja2 + graphviz pins
  README.md                 — this file
  parser/                   — markdown → in-memory model
    service_domains.py      — BD + SD parser (carries the SD H2 whitelist)
    entities.py             — core + specialisation entity parser
    ownership.py            — ownership-map row parser
    errors.py               — ParseError type
  graph/                    — in-memory graph build
    build.py                — capability + entity graph + edge dedup
                              (BD-narrative refs → single aggregate edge,
                               not fan-out)
  render/                   — Graphviz layout + HTML emission
    dot_gen.py              — DOT source builders for each view
    layout.py               — subprocess wrapper around dot / sfdp
    site.py                 — page renderer; embeds SVG; writes dist/
    templates/
      base.html.j2          — shared page chrome (header, nav, footer,
                              dark mode CSS, tag-highlighting CSS)
    static/
      svg-pan-zoom.min.js   — vendored MIT lib (see Dependencies above)
  tests/                    — parser + substantive-coverage tests
    test_parsers.py
    fixtures/               — minimal markdown fixtures
```

## What it does not do

- It does not edit the model. The generator renders what exists; new SDs / entities / BDs land through the standard ADR process and the next build picks them up.
- It does not draw Service-Operation-to-Service-Operation edges. The SO names live in the markdown; the SO-to-SO edges did not — they were authored into the predecessor renderer's source by hand and do not exist as data in any markdown file. Restoring them would be either (a) authoring a structured SO-edge declaration into the SD markdown, or (b) a future machine-readable (RDF/OWL) representation of the model.
- It does not re-render the D2 attribute-level ERD. The D2 binary step in CI continues to produce `entities/core/core-erd.svg`; the generator's ERD page links to that file.
- It does not deploy. The generator writes to `dist/`; the CI workflow at `.github/workflows/diagrams.yml` packages and uploads.
- It does not ship live filtering, dynamic view composition, an MCP server, or rich hover overlays. The static-bundle floor is the optimisation; richer client-side features would require a JS framework. Dark mode + tag highlighting are pure CSS (no JS); see `render/templates/base.html.j2`.

## When something goes wrong

| Symptom | Likely cause |
|---|---|
| `ParseError: ... missing '**Applies:**' tag line` | An SD file was added without the standard header. |
| `ParseError: ... references unknown SD-NN.M` | A Consumes / Produces line names an SD that does not exist; check the spelling. |
| `LayoutError: Graphviz dot not found on PATH` | Install Graphviz (apt-get / Homebrew / the binary releases). |
| `LayoutError: Graphviz timed out` | A view exceeds the layout-engine budget; consider per-BD baking only. |
| `coverage assertion failed — N expected pages missing` | The generator ran to completion but a declared BD / SD / entity has no corresponding page; almost always a parser bug to investigate, not a model defect. |

## Install — local build prerequisites

The generator needs Python ≥ 3.10 and Graphviz ≥ 11. The Python deps come from `pip install -r tools/diagrams/requirements.txt`. Install Graphviz:

```bash
# Linux (apt-get) — what the CI workflow runs.
sudo apt-get install -y graphviz

# macOS (Homebrew).
brew install graphviz

# Windows — download the installer from
# https://gitlab.com/api/v4/projects/4207231/packages/generic/graphviz-releases
# and add the bin/ directory to PATH.
```

The D2 binary (still used in CI for the attribute-level ERD and layer stack) is installed by the workflow itself; see the CI section below.

## CI / deploy

`.github/workflows/diagrams.yml` runs on push to the pilot branch and on `workflow_dispatch`. It:

1. Sets up Python 3.12 and installs the generator's requirements.
2. Installs the system Graphviz binary.
3. Installs D2 (still used for the attribute-level core ERD and the layer-stack SVG).
4. Runs `python tools/diagrams/build.py --out dist/` to emit the full Hybrid D site.
5. Runs D2 to render `dist/entities/core/core-erd.svg` and `dist/layer-stack.svg` alongside.
6. Uploads `dist/` as a workflow artefact and (if Pages is enabled) deploys to GitHub Pages.

GitHub Pages must be enabled at the repository level for the deploy step to succeed — *Settings → Pages → Build and deployment → Source: GitHub Actions*. This is a one-time repo-admin action.
