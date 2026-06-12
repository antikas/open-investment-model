"""Static-site renderer — emits the full `dist/` tree."""
from __future__ import annotations

import html
import json
import re
import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..parser.service_domains import ServiceDomainModel, BusinessDomain, ServiceDomain
from ..parser.entities import EntityModel, Entity
from ..parser.ownership import OwnershipMap
from ..graph.build import GraphBundle
from . import dot_gen, layout


class RenderError(RuntimeError):
    pass


# svg-pan-zoom 3.6.2 — MIT — vendored into the repo at
# tools/diagrams/render/static/svg-pan-zoom.min.js. Vendoring (rather than
# fetching at build time) closes the OIM-54 cycle-1 P-3 finding: silent
# CDN fetch + SSL bypass + placeholder fallback is a supply-chain smell
# the 2026-05-21 D2 review forbade. Source and SHA-256 are recorded in
# tools/diagrams/README.md §Dependencies.
_VENDORED_PANZOOM = Path(__file__).parent / "static" / "svg-pan-zoom.min.js"


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(Path(__file__).parent / "templates")),
        autoescape=select_autoescape(enabled_extensions=()),
        keep_trailing_newline=True,
    )


def _href(template: Environment, body_html: str, *,
          title: str, counts: str, include_pan_zoom: bool = True) -> str:
    tpl = template.get_template("base.html.j2")
    return tpl.render(
        title=title, body=body_html, counts=counts,
        include_pan_zoom=include_pan_zoom,
    )


def _svg_wrap(svg: str) -> str:
    """Strip the XML declaration and DOCTYPE so the SVG embeds inline cleanly."""
    svg = re.sub(r"<\?xml[^?]*\?>\s*", "", svg)
    svg = re.sub(r"<!DOCTYPE[^>]*>\s*", "", svg)
    # Force responsive sizing.
    svg = re.sub(
        r'<svg([^>]*?)\swidth="[^"]+"\s+height="[^"]+"',
        r'<svg\1',
        svg,
        count=1,
    )
    return svg


def _copy_pan_zoom(dist: Path) -> None:
    """Copy the vendored svg-pan-zoom into `dist/`.

    The script is bundled at tools/diagrams/render/static/svg-pan-zoom.min.js
    (vendored under MIT licence; SHA-256 recorded in tools/diagrams/README.md).
    No network fetch — the build is reproducible and supply-chain auditable.
    """
    if not _VENDORED_PANZOOM.is_file():
        raise RenderError(
            f"vendored svg-pan-zoom missing at {_VENDORED_PANZOOM} — "
            f"re-fetch from https://cdn.jsdelivr.net/npm/svg-pan-zoom@3.6.2/"
            f"dist/svg-pan-zoom.min.js and commit. SHA-256 in README.md."
        )
    target = dist / "svg-pan-zoom.min.js"
    target.write_bytes(_VENDORED_PANZOOM.read_bytes())


def _bd_office_tag(bd: BusinessDomain) -> str:
    return dot_gen._office_key(bd.office)


def _link_id(id_: str, kind: str) -> str:
    if kind == "sd":
        return f'<a href="./sd-{id_[3:]}.html">{html.escape(id_)}</a>'
    if kind == "bd":
        num = id_[3:]
        return f'<a href="./bd-{num}.html">{html.escape(id_)}</a>'
    if kind == "entity":
        # entity-ref class + data-entity attribute powers the dark-mode
        # tag-highlighting feature in base.html.j2 (hover an entity link,
        # other entities dim, siblings emphasise). Pure CSS, no JS.
        return (
            f'<a href="./entity-{id_}.html" class="entity-ref" '
            f'data-entity="{id_}">{html.escape(id_)}</a>'
        )
    return html.escape(id_)


def _format_purpose(text: str) -> str:
    return html.escape(text)


def render_site(
    dist: Path,
    sd_model: ServiceDomainModel,
    entity_model: EntityModel,
    ownership: OwnershipMap,
    bundle: GraphBundle,
    *,
    embed_d2_svg: bool = True,
) -> dict[str, list[str]]:
    """Render the entire site to `dist/`. Returns a manifest of emitted IDs."""
    dist.mkdir(parents=True, exist_ok=True)
    env = _env()
    layout.check_graphviz()
    _copy_pan_zoom(dist)

    counts_line = (
        f"{len(sd_model.business_domains)} Business Domains · "
        f"{len(sd_model.all_sds())} Service Domains · "
        f"{len(sd_model.all_sos())} Service Operations · "
        f"{len(entity_model.entities)} Entities"
    )

    rendered = {
        "index": [], "landscape": [], "bd": [], "sd": [], "entity": [], "erd": [],
    }

    # ---- Index ----
    rows = []
    for bd in sd_model.business_domains:
        rows.append(
            f"<tr><td>{html.escape(bd.id)}</td>"
            f"<td><a href='./bd-{bd.num:02d}.html'>{html.escape(bd.name)}</a></td>"
            f"<td>{html.escape(bd.office)}</td>"
            f"<td>{len(bd.service_domains)}</td></tr>"
        )
    index_body = f"""
<h2>OpenIM Diagram Index</h2>
<p class='meta'>OpenIM is the reference model for institutional investment management — the buy-side: asset managers, sovereign wealth funds, LP allocators, institutional investors. This site renders the service-domain decomposition and the canonical entity model.</p>

<h3>Top-level views</h3>
<ul class='tight'>
  <li><a href='./landscape.html'>Landscape</a> — the 17 Business Domains and the relationships between them.</li>
  <li><a href='./erd.html'>Entity ERD</a> — the {len(entity_model.entities)}-entity canonical data model.</li>
</ul>

<h3>Business Domains</h3>
<table>
  <thead><tr><th>ID</th><th>Business Domain</th><th>Office</th><th>SDs</th></tr></thead>
  <tbody>{''.join(rows)}</tbody>
</table>
"""
    (dist / "index.html").write_text(
        _href(env, index_body, title="Index", counts=counts_line, include_pan_zoom=False),
        encoding="utf-8",
    )
    rendered["index"].append("index.html")

    # ---- Landscape ----
    landscape_dot_src = dot_gen.landscape_dot(sd_model, bundle)
    landscape_svg = _svg_wrap(layout.render_svg(landscape_dot_src, engine="dot"))
    landscape_body = f"""
<h2>Landscape — the 17 Business Domains</h2>
<p class='meta'>Boxes are Business Domains, grouped by office tag. Dashed cluster outlines mark office groupings. Solid arrows show cross-Business-Domain dependencies derived from the per-SD Inputs and Outputs declarations and the structured Consumes / Produces lines. Click a Business Domain to drill into its Service Domains and Service Operations.</p>
<div class='diagram'>{landscape_svg}</div>
"""
    (dist / "landscape.html").write_text(
        _href(env, landscape_body, title="Landscape", counts=counts_line, include_pan_zoom=True),
        encoding="utf-8",
    )
    rendered["landscape"].append("landscape.html")

    # ---- Per-BD ----
    for bd in sd_model.business_domains:
        dot_src = dot_gen.bd_detail_dot(bd, sd_model, bundle)
        svg = _svg_wrap(layout.render_svg(dot_src, engine="dot"))
        sd_rows = []
        for sd in bd.service_domains:
            ops = ", ".join(o.name for o in sd.operations[:3]) + (
                "…" if len(sd.operations) > 3 else ""
            )
            sd_rows.append(
                f"<tr><td>{html.escape(sd.id)}</td>"
                f"<td><a href='./sd-{sd.id[3:]}.html'>{html.escape(sd.name)}</a> "
                f"<span class='tag tag-{html.escape(sd.applies)}'>{html.escape(sd.applies)}</span></td>"
                f"<td>{html.escape(ops)}</td></tr>"
            )
        body = f"""
<h2>{html.escape(bd.id)} — {html.escape(bd.name)} <span class='tag'>{html.escape(bd.office)}</span></h2>
<div class='diagram'>{svg}</div>
<h3>Service Domains ({len(bd.service_domains)})</h3>
<table>
  <thead><tr><th>ID</th><th>Service Domain</th><th>Example operations</th></tr></thead>
  <tbody>{''.join(sd_rows)}</tbody>
</table>
"""
        out = dist / f"bd-{bd.num:02d}.html"
        out.write_text(
            _href(env, body, title=bd.id, counts=counts_line, include_pan_zoom=True),
            encoding="utf-8",
        )
        rendered["bd"].append(out.name)

    # ---- Per-SD ----
    bd_by_id = sd_model.bd_by_id()
    for sd in sd_model.all_sds():
        bd = bd_by_id[sd.bd_id]
        ops_html = "".join(f"<li>{html.escape(o.name)}</li>" for o in sd.operations)
        own_html = ", ".join(
            _link_id(e, "entity") for e in sd.owns_entities
        ) or "<em>none declared</em>"
        cons_ent_html = ", ".join(
            _link_id(e, "entity") for e in sd.consumes_entities
        ) or "<em>none declared</em>"
        up_html = ", ".join(
            _link_id(s, "sd" if s.startswith("SD-") else "bd")
            for s in sorted(sd.upstream_sds)
        ) or "<em>none declared</em>"
        down_html = ", ".join(
            _link_id(s, "sd" if s.startswith("SD-") else "bd")
            for s in sorted(sd.downstream_sds)
        ) or "<em>none declared</em>"
        body = f"""
<h2>{html.escape(sd.id)} — {html.escape(sd.name)} <span class='tag tag-{html.escape(sd.applies)}'>{html.escape(sd.applies)}</span></h2>
<p class='meta'>Business Domain: <a href='./bd-{bd.num:02d}.html'>{html.escape(bd.id)} — {html.escape(bd.name)}</a> · Office: {html.escape(bd.office)}</p>
<h3>Purpose</h3>
<p>{_format_purpose(sd.purpose) if sd.purpose else '<em>not extracted</em>'}</p>
<h3>Service Operations ({len(sd.operations)})</h3>
<ul class='tight'>{ops_html}</ul>
<h3>Owns</h3>
<p>{own_html}</p>
<h3>Consumes entities</h3>
<p>{cons_ent_html}</p>
<h3>Upstream Service Domains</h3>
<p>{up_html}</p>
<h3>Downstream Service Domains</h3>
<p>{down_html}</p>
"""
        out = dist / f"sd-{sd.id[3:]}.html"
        out.write_text(
            _href(env, body, title=sd.id, counts=counts_line, include_pan_zoom=False),
            encoding="utf-8",
        )
        rendered["sd"].append(out.name)

    # ---- Per-entity ----
    sd_by_id = sd_model.sd_by_id()
    for e in entity_model.entities:
        own_rec = ownership.get(e.id)
        pattern = html.escape(own_rec.pattern) if own_rec else ""
        owners_html = ", ".join(
            f"{_link_id(s, 'sd')} ({html.escape(sd_by_id[s].name)})"
            for s in e.owned_by if s in sd_by_id
        )
        consumers_html = ", ".join(
            f"{_link_id(s, 'sd')} ({html.escape(sd_by_id[s].name)})"
            for s in e.consumed_by if s in sd_by_id
        ) or "<em>none declared</em>"
        fk_html = ", ".join(
            _link_id(fk, "entity") for fk in e.fk_targets
        ) or "<em>none</em>"
        specialises_html = (
            _link_id(e.specialises, "entity") if e.specialises else "<em>core entity</em>"
        )
        body = f"""
<h2>{html.escape(e.id)} — {html.escape(e.name)}</h2>
<p class='meta'>Pack: <code>{html.escape(e.pack)}</code> · Specialises: {specialises_html}</p>
{('<p>' + html.escape(e.summary) + '</p>') if e.summary else ''}
<h3>Owned by</h3>
<p>{owners_html} {('<span class="meta">' + pattern + '</span>') if pattern else ''}</p>
<h3>Consumed by</h3>
<p>{consumers_html}</p>
<h3>Foreign keys</h3>
<p>{fk_html}</p>
"""
        out = dist / f"entity-{e.id}.html"
        out.write_text(
            _href(env, body, title=e.id, counts=counts_line, include_pan_zoom=False),
            encoding="utf-8",
        )
        rendered["entity"].append(out.name)

    # ---- ERD ----
    erd_dot_src = dot_gen.entity_erd_dot(entity_model)
    erd_svg = _svg_wrap(layout.render_svg(erd_dot_src, engine="dot"))
    erd_body = f"""
<h2>Entity ERD — pack-grouped overview</h2>
<p class='meta'>The {len(entity_model.entities)}-entity canonical model — core plus the four specialisation packs (private-markets, public-markets, derivatives, real-assets). Solid arrows are foreign keys; dashed arrows are <code>Specialises</code> declarations. Each entity links to its full attribute schema. The attribute-level ERD of the core is rendered separately by D2 — see <a href='./entities/core/core-erd.svg'>core-erd.svg</a> when the D2 build step has populated it.</p>
<div class='diagram'>{erd_svg}</div>
"""
    (dist / "erd.html").write_text(
        _href(env, erd_body, title="Entity ERD", counts=counts_line, include_pan_zoom=True),
        encoding="utf-8",
    )
    rendered["erd"].append("erd.html")

    return rendered
