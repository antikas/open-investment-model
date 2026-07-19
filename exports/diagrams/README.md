# OpenIM diagrams — generated static site

**GENERATED. Do not hand-edit.** This is the Hybrid D static-site generator's output: the
capability-graph pages (Business Domains, Service Domains, entities) laid out via Graphviz, plus
two D2 SVGs for the entity-model core ERD and the layer-stack diagram. Regenerate on an unchanged
model and every file is byte-identical (the same generate-from-source discipline as the other
OpenIM exports).

## Regenerating

```bash
python -m pip install -r tools/diagrams/requirements.txt
python -m unittest discover tools/diagrams/tests/
python tools/diagrams/build.py --out exports/diagrams/
d2 --layout=elk model/diagrams/d2/core-erd.d2 exports/diagrams/entities/core/core-erd.svg
d2 --layout=elk model/diagrams/d2/layer-stack.d2 exports/diagrams/layer-stack.svg
```

Requires Graphviz (`dot`, `sfdp`) and D2 (pinned `v0.6.9`) on `PATH`.

## Viewing

Open `exports/diagrams/index.html` (or any `bd-*.html` / `entity-*.html` page) directly in a
browser — the site is fully static, no server required.
