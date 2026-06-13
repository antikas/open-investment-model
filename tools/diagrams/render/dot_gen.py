"""Build DOT source strings from the parsed model + graph bundle.

One emitter per view:

- `landscape_dot` — 17 BD boxes, cross-BD arrows. Layout: dot, LR.
- `bd_detail_dot(bd_num)` — full SD + SO detail for one BD, with internal
  edges (consumes/produces, narrative) and one out-bound arrow per
  external destination BD (collapsed onto the BD box).
- `entity_erd_dot` — entity nodes grouped by pack with FK edges.

Cross-BD edges branch on `edge.kind`. The two BD-aggregate kinds
(`narrative-bd-input`, `narrative-bd-output` — the single-edge aggregate
references) render distinctly from the structured / SD-narrative edges. BD-aggregate
edges use `style="dashed", color="#808080", penwidth=0.8` plus a
tooltip naming the shape; structured edges retain the default style.
A practitioner reading the rendered SVG can now tell "this BD has
structured / SD-specific dependencies into that one" from "this BD
narratively references that one as aggregate-function-reference
context".
"""
from __future__ import annotations

import html
import re
from typing import Iterable

from ..parser.service_domains import ServiceDomainModel, BusinessDomain
from ..parser.entities import EntityModel
from ..graph.build import GraphBundle, CapabilityEdge


# Office colour palette (subdued, accessible).
_OFFICE_COLOURS = {
    "Front": ("#dfe8f7", "#5b7aa6"),         # blue
    "Middle": ("#e9e2f0", "#7a5b9b"),         # purple
    "Back": ("#e5efe1", "#5b8a48"),           # green
    "Cross-cutting": ("#fbf0d8", "#a07b2c"),  # amber
    "Commercial": ("#f7dfe0", "#a65b5b"),     # rose
}


def _office_key(office: str) -> str:
    o = office.lower()
    if o.startswith("front"):
        return "Front"
    if o.startswith("middle"):
        return "Middle"
    if o.startswith("back"):
        return "Back"
    if o.startswith("cross"):
        return "Cross-cutting"
    if o.startswith("commercial"):
        return "Commercial"
    return "Cross-cutting"


def _esc(s: str) -> str:
    """Escape for use inside a DOT label (double-quoted form)."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _bd_node_id(bd: BusinessDomain) -> str:
    return f"bd_{bd.num:02d}"


def _sd_node_id(sd_id: str) -> str:
    # SD-NN.M -> sd_NN_M
    return "sd_" + sd_id[3:].replace(".", "_")


def _so_node_id(sd_id: str, ix: int) -> str:
    return f"so_{sd_id[3:].replace('.', '_')}_{ix:02d}"


def landscape_dot(sd_model: ServiceDomainModel, bundle: GraphBundle) -> str:
    """The 17-BD landscape with cross-BD arrows. dot LR engine."""
    lines: list[str] = [
        "digraph openim_landscape {",
        '  rankdir=LR;',
        '  graph [bgcolor="white", pad="0.4", nodesep="0.4", ranksep="1.0", '
        'splines="polyline", overlap=false];',
        '  node [fontname="Helvetica,Arial,sans-serif", fontsize=14, shape=box, '
        'style="filled,rounded", penwidth=2];',
        '  edge [fontname="Helvetica,Arial,sans-serif", fontsize=10, '
        'color="#5b7aa6", arrowsize=0.7, penwidth=1.2];',
    ]
    # Cluster by office tag so the landscape reads top-to-bottom.
    by_office: dict[str, list[BusinessDomain]] = {}
    for bd in sd_model.business_domains:
        by_office.setdefault(_office_key(bd.office), []).append(bd)

    for office in ("Front", "Middle", "Back", "Cross-cutting", "Commercial"):
        bds = by_office.get(office, [])
        if not bds:
            continue
        fill, stroke = _OFFICE_COLOURS[office]
        cluster_name = office.lower().replace("-", "_")
        lines.append(f'  subgraph cluster_{cluster_name} {{')
        lines.append(f'    label="{office} office";')
        lines.append(f'    style="rounded,dashed"; color="{stroke}"; fontcolor="{stroke}"; fontsize=12;')
        for bd in bds:
            label = f"{bd.id}\\n{bd.name}\\n({len(bd.service_domains)} SDs)"
            href = f"./bd-{bd.num:02d}.html"
            lines.append(
                f'    {_bd_node_id(bd)} [label="{_esc(label)}", '
                f'href="{href}", fillcolor="{fill}", color="{stroke}", '
                f'fontcolor="#1f3a5f"];'
            )
        lines.append("  }")

    # Cross-BD arrows — one per unique (src_bd, tgt_bd) pair.
    #
    # Branch on edge.kind so BD-narrative aggregate-function-references
    # render distinctly from structured / SD-narrative edges. A pair
    # carries one of three shapes:
    #
    # - "structured" — at least one consumes-sd / produces-sd / narrative-input
    #   / narrative-output edge connects an SD in src_bd to an SD in tgt_bd.
    #   The reader interprets this as "this BD has structured / SD-specific
    #   relationships into that one". Renders solid, default colour.
    # - "narrative-bd" — only narrative-bd-input / narrative-bd-output edges
    #   connect src_bd and tgt_bd (the aggregate-function-reference
    #   form). The reader interprets this as "this BD's narrative references
    #   that one as aggregate function context, no SD-specific dependency".
    #   Renders dashed, lighter (gray60), thinner (penwidth=0.8).
    # - "mixed" — both shapes present for the same pair. Renders solid as
    #   structured (the stronger signal wins for the landscape overview).
    #
    # Per-edge kind cannot be inferred from cross_bd_pairs() alone (that
    # returns a set of pairs without kind), so build the per-pair kind index
    # here from the full edge list.
    _BD_NARRATIVE_KINDS = frozenset({"narrative-bd-input", "narrative-bd-output"})
    pair_kinds: dict[tuple[str, str], set[str]] = {}
    for edge in bundle.edges:
        s_bd = _bd_of_id(edge.source)
        t_bd = _bd_of_id(edge.target)
        if not s_bd or not t_bd or s_bd == t_bd:
            continue
        pair_kinds.setdefault((s_bd, t_bd), set()).add(edge.kind)

    for src, tgt in sorted(bundle.cross_bd_pairs()):
        if src == tgt:
            continue
        src_bd = sd_model.bd_by_id().get(src)
        tgt_bd = sd_model.bd_by_id().get(tgt)
        if not src_bd or not tgt_bd:
            continue
        kinds = pair_kinds.get((src, tgt), set())
        if kinds and kinds.issubset(_BD_NARRATIVE_KINDS):
            # Pure BD-narrative aggregate reference — dashed, lighter, thinner.
            lines.append(
                f'  {_bd_node_id(src_bd)} -> {_bd_node_id(tgt_bd)} '
                f'[style="dashed", color="#808080", penwidth=0.8, '
                f'tooltip="aggregate BD reference (narrative)"];'
            )
        else:
            # Structured (or mixed structured + narrative) — solid, default.
            lines.append(f'  {_bd_node_id(src_bd)} -> {_bd_node_id(tgt_bd)};')

    lines.append("}")
    return "\n".join(lines)


def _bd_of_id(node_id: str) -> str | None:
    """Resolve a graph node id (`SD-NN.M` or `BD-NN`) to its BD id."""
    if node_id.startswith("SD-") and len(node_id) >= 5:
        return f"BD-{node_id[3:5]}"
    if node_id.startswith("BD-"):
        return node_id
    return None


def bd_detail_dot(
    bd: BusinessDomain,
    sd_model: ServiceDomainModel,
    bundle: GraphBundle,
) -> str:
    """Per-BD view — SDs with SO sub-nodes; internal arrows; collapsed cross-BD arrows."""
    fill, stroke = _OFFICE_COLOURS[_office_key(bd.office)]
    lines: list[str] = [
        "digraph openim_bd {",
        '  graph [bgcolor="white", pad="0.4", nodesep="0.3", ranksep="0.7", '
        'overlap=false, splines="polyline"];',
        '  node [fontname="Helvetica,Arial,sans-serif", fontsize=12, shape=box, '
        'style="filled,rounded", penwidth=1.5];',
        '  edge [fontname="Helvetica,Arial,sans-serif", fontsize=9, '
        'color="#5b7aa6", arrowsize=0.6];',
        f'  label="{_esc(bd.id + " — " + bd.name)}"; labelloc=t; fontsize=14; fontcolor="#1f3a5f";',
    ]

    # SD clusters with SO leaves.
    for sd in bd.service_domains:
        sd_node = _sd_node_id(sd.id)
        sd_label = f"{sd.id}\\n{sd.name}\\n[{sd.applies}]"
        sd_href = f"./sd-{sd.id[3:]}.html"
        cluster_id = "cluster_" + sd_node
        lines.append(f'  subgraph {cluster_id} {{')
        lines.append(f'    label="{_esc(sd_label)}"; labelloc=t;')
        lines.append(f'    style="rounded,filled"; fillcolor="{fill}"; color="{stroke}"; fontcolor="#1f3a5f"; fontsize=11;')
        lines.append(f'    href="{sd_href}";')
        # Add a dummy invisible node so the cluster has a stable connector for edges.
        anchor = sd_node + "_anchor"
        lines.append(
            f'    {anchor} [shape=point, style=invis, width=0.01, height=0.01];'
        )
        # SO leaves.
        for ix, op in enumerate(sd.operations, start=1):
            sn = _so_node_id(sd.id, ix)
            lines.append(
                f'    {sn} [label="{_esc(op.name)}", '
                f'fillcolor="white", color="{stroke}", fontsize=10, '
                f'fontcolor="#3a3a3a"];'
            )
        lines.append("  }")

    # Internal edges (within BD).
    sd_in_bd = {sd.id for sd in bd.service_domains}
    for edge in bundle.edges:
        if edge.source in sd_in_bd and edge.target in sd_in_bd:
            src = _sd_node_id(edge.source) + "_anchor"
            tgt = _sd_node_id(edge.target) + "_anchor"
            ltail = "cluster_" + _sd_node_id(edge.source)
            lhead = "cluster_" + _sd_node_id(edge.target)
            lines.append(f'  {src} -> {tgt} [ltail="{ltail}", lhead="{lhead}"];')

    # Cross-BD edges — collapsed to one node per destination BD. Edges may
    # name a BD directly (the aggregate-function-reference
    # form: narrative-bd-input / narrative-bd-output) or an SD in another BD
    # (the structured / SD-narrative forms). Both routes land on the same
    # collapsed BD external node.
    def _bd_of(node_id: str) -> str | None:
        if node_id.startswith("SD-") and len(node_id) >= 5:
            return f"BD-{node_id[3:5]}"
        if node_id.startswith("BD-"):
            return node_id
        return None

    # Track per-(ext-BD, source-SD) edge kinds so the collapsed cross-BD
    # arrow can render the BD-narrative aggregate-function-reference shape
    # distinctly from the structured / SD-narrative shape. _BD_NARRATIVE_KINDS
    # edges render dashed + gray60 + penwidth 0.8; structured / SD-narrative
    # edges render solid + default (the visual surface for "internal cross-BD"
    # is preserved).
    _BD_NARRATIVE_KINDS = frozenset({"narrative-bd-input", "narrative-bd-output"})

    other_bd_targets: dict[str, list[tuple[str, str]]] = {}
    other_bd_sources: dict[str, list[tuple[str, str]]] = {}
    for edge in bundle.edges:
        if edge.source in sd_in_bd and edge.target not in sd_in_bd:
            tgt_bd = _bd_of(edge.target)
            if tgt_bd and tgt_bd != bd.id:
                other_bd_targets.setdefault(tgt_bd, []).append((edge.source, edge.kind))
        elif edge.target in sd_in_bd and edge.source not in sd_in_bd:
            src_bd = _bd_of(edge.source)
            if src_bd and src_bd != bd.id:
                other_bd_sources.setdefault(src_bd, []).append((edge.target, edge.kind))

    bd_by_id = sd_model.bd_by_id()
    for other_bd_id, contribs in sorted(other_bd_targets.items()):
        other_bd = bd_by_id.get(other_bd_id)
        if not other_bd:
            continue
        node = f"ext_out_{other_bd.num:02d}"
        ofill, ostroke = _OFFICE_COLOURS[_office_key(other_bd.office)]
        ext_label = f"-> {other_bd.id}\\n{other_bd.name}"
        href = f"./bd-{other_bd.num:02d}.html"
        lines.append(
            f'  {node} [label="{_esc(ext_label)}", fillcolor="{ofill}", '
            f'color="{ostroke}", shape=box, style="filled,rounded,dashed", '
            f'href="{href}", fontsize=10];'
        )
        # One representative arrow per source SD; per-pair edge style branches
        # on whether the source's contribution is pure BD-narrative or carries
        # structured / SD-narrative (the stronger signal wins).
        kinds_by_src: dict[str, set[str]] = {}
        for src_sd_id, kind in contribs:
            kinds_by_src.setdefault(src_sd_id, set()).add(kind)
        src_sd_id = sorted(kinds_by_src)[0]
        kinds = kinds_by_src[src_sd_id]
        if kinds.issubset(_BD_NARRATIVE_KINDS):
            edge_attrs = (
                'ltail="cluster_' + _sd_node_id(src_sd_id) + '", '
                'style=dashed, color="#808080", penwidth=0.8, '
                'tooltip="aggregate BD reference (narrative)"'
            )
        else:
            edge_attrs = (
                'ltail="cluster_' + _sd_node_id(src_sd_id) + '", style=dashed'
            )
        lines.append(
            f'  {_sd_node_id(src_sd_id)}_anchor -> {node} [{edge_attrs}];'
        )

    for other_bd_id, contribs in sorted(other_bd_sources.items()):
        other_bd = bd_by_id.get(other_bd_id)
        if not other_bd:
            continue
        node = f"ext_in_{other_bd.num:02d}"
        ofill, ostroke = _OFFICE_COLOURS[_office_key(other_bd.office)]
        ext_label = f"<- {other_bd.id}\\n{other_bd.name}"
        href = f"./bd-{other_bd.num:02d}.html"
        lines.append(
            f'  {node} [label="{_esc(ext_label)}", fillcolor="{ofill}", '
            f'color="{ostroke}", shape=box, style="filled,rounded,dashed", '
            f'href="{href}", fontsize=10];'
        )
        kinds_by_tgt: dict[str, set[str]] = {}
        for tgt_sd_id, kind in contribs:
            kinds_by_tgt.setdefault(tgt_sd_id, set()).add(kind)
        tgt_sd_id = sorted(kinds_by_tgt)[0]
        kinds = kinds_by_tgt[tgt_sd_id]
        if kinds.issubset(_BD_NARRATIVE_KINDS):
            edge_attrs = (
                'lhead="cluster_' + _sd_node_id(tgt_sd_id) + '", '
                'style=dashed, color="#808080", penwidth=0.8, '
                'tooltip="aggregate BD reference (narrative)"'
            )
        else:
            edge_attrs = (
                'lhead="cluster_' + _sd_node_id(tgt_sd_id) + '", style=dashed'
            )
        lines.append(
            f'  {node} -> {_sd_node_id(tgt_sd_id)}_anchor [{edge_attrs}];'
        )

    lines.append('  compound=true;')
    lines.append("}")
    return "\n".join(lines)


def entity_erd_dot(entity_model: EntityModel) -> str:
    """Pack-grouped entity ERD with FK + Specialises edges. dot LR engine."""
    lines: list[str] = [
        "digraph openim_entities {",
        '  rankdir=LR;',
        '  graph [bgcolor="white", pad="0.4", nodesep="0.3", ranksep="0.9", '
        'overlap=false, splines="polyline"];',
        '  node [fontname="Helvetica,Arial,sans-serif", fontsize=11, shape=box, '
        'style="filled,rounded", penwidth=1.5];',
        '  edge [fontname="Helvetica,Arial,sans-serif", fontsize=9, '
        'color="#5b7aa6", arrowsize=0.6];',
    ]
    pack_colours = {
        "core": ("#dfe8f7", "#5b7aa6"),
        "private-markets": ("#e9e2f0", "#7a5b9b"),
        "public-markets": ("#e5efe1", "#5b8a48"),
        "derivatives": ("#fbf0d8", "#a07b2c"),
        "real-assets": ("#f7dfe0", "#a65b5b"),
    }
    by_pack = entity_model.by_pack()
    for pack, ents in by_pack.items():
        fill, stroke = pack_colours.get(pack, ("#eeeeee", "#888888"))
        cluster = "cluster_" + pack.replace("-", "_")
        lines.append(f'  subgraph {cluster} {{')
        lines.append(f'    label="{pack}"; style="rounded,dashed"; color="{stroke}"; fontcolor="{stroke}"; fontsize=12;')
        for e in ents:
            node = "ent_" + e.id.replace("-", "_")
            label = f"{e.id}\\n{e.name}"
            href = f"./entity-{e.id}.html"
            lines.append(
                f'    {node} [label="{_esc(label)}", fillcolor="{fill}", '
                f'color="{stroke}", href="{href}", fontcolor="#1f3a5f"];'
            )
        lines.append("  }")
    # FK and Specialises edges.
    known = {e.id for e in entity_model.entities}
    for e in entity_model.entities:
        src = "ent_" + e.id.replace("-", "_")
        for fk in e.fk_targets:
            if fk in known:
                tgt = "ent_" + fk.replace("-", "_")
                lines.append(f'  {src} -> {tgt};')
        if e.specialises and e.specialises in known:
            tgt = "ent_" + e.specialises.replace("-", "_")
            lines.append(f'  {src} -> {tgt} [style=dashed, color="#a07b2c"];')
    lines.append("}")
    return "\n".join(lines)
