"""Build the capability graph and entity graph from the parsed model.

The capability graph carries:

- one node per BusinessDomain (`bd-NN`)
- one node per ServiceDomain (`sd-NN.M`)
- one node per ServiceOperation (`so-NN.M-K`)
- containment edges BD -> SD -> SO
- SD-to-SD edges drawn from each SD's structured `**Consumes:**` /
  `**Produces:**` lines and narrative `Inputs:` / `Outputs:` lines naming
  a specific SD (deduplicated)
- BD-level narrative references (an Inputs/Outputs sentence naming a
  whole BD as aggregate-function-reference shorthand) produce ONE edge
  from the BD landing node, not a fan-out into every member SD. The
  fan-out shape was identified as a bug in OIM-54 cycle-1 P-4 (87% of
  edges were artefacts; readers cannot distinguish artefact from
  declaration). The aggregate-function-reference is preserved as a single
  edge with the distinct `narrative-bd-input` / `narrative-bd-output`
  kind so the renderer can style it (dashed, lighter) and the reader can
  read "this SD takes aggregate input from BD-XX" rather than "this SD
  depends on every SD in BD-XX".

The entity graph carries:

- one node per Entity
- FK edges (entity -> entity)
- group buckets per `pack` for layout / colouring
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from ..parser.service_domains import (
    ServiceDomainModel, BusinessDomain, ServiceDomain, ServiceOperation,
)
from ..parser.entities import EntityModel, Entity


@dataclass(frozen=True)
class CapabilityEdge:
    source: str       # SD id or BD id
    target: str       # SD id or BD id
    kind: str         # "consumes-sd" / "produces-sd" /
                      # "narrative-input" / "narrative-output" /
                      # "narrative-bd-input" / "narrative-bd-output"
                      # (BD-kinds are aggregate-function-references — a
                      # single edge from the BD landing node per OIM-54
                      # cycle-2 B-4 fix, not fan-out per member SD)


@dataclass
class GraphBundle:
    sd_model: ServiceDomainModel
    entity_model: EntityModel
    edges: list[CapabilityEdge] = field(default_factory=list)
    so_index: dict[str, ServiceOperation] = field(default_factory=dict)

    def edges_within_bd(self, bd_num: int) -> list[CapabilityEdge]:
        prefix = f"SD-{bd_num:02d}."
        return [e for e in self.edges if e.source.startswith(prefix) and e.target.startswith(prefix)]

    def cross_bd_edges(self) -> list[CapabilityEdge]:
        out: list[CapabilityEdge] = []
        for e in self.edges:
            src_bd = _bd_of(e.source)
            tgt_bd = _bd_of(e.target)
            if src_bd and tgt_bd and src_bd != tgt_bd:
                out.append(e)
        return out

    def cross_bd_pairs(self) -> set[tuple[str, str]]:
        pairs: set[tuple[str, str]] = set()
        for e in self.cross_bd_edges():
            pairs.add((_bd_of(e.source), _bd_of(e.target)))  # type: ignore[arg-type]
        return pairs


def _bd_of(node_id: str) -> str | None:
    if node_id.startswith("SD-"):
        return f"BD-{node_id[3:5]}"
    if node_id.startswith("BD-"):
        return node_id
    return None


def _so_id(sd_id: str, ix: int) -> str:
    return f"so-{sd_id[3:]}-{ix:02d}"


def build_capability_graph(
    sd_model: ServiceDomainModel,
    entity_model: EntityModel,
) -> GraphBundle:
    bundle = GraphBundle(sd_model=sd_model, entity_model=entity_model)
    # Index SOs.
    for sd in sd_model.all_sds():
        for ix, op in enumerate(sd.operations, start=1):
            bundle.so_index[_so_id(sd.id, ix)] = op

    # Build edges, deduplicated.
    sd_ids = {sd.id for sd in sd_model.all_sds()}
    bd_ids = {bd.id for bd in sd_model.business_domains}
    seen: set[tuple[str, str, str]] = set()

    def add(source: str, target: str, kind: str) -> None:
        key = (source, target, kind)
        if key in seen:
            return
        seen.add(key)
        bundle.edges.append(CapabilityEdge(source=source, target=target, kind=kind))

    bd_to_sds: dict[str, list[str]] = {bd.id: [sd.id for sd in bd.service_domains]
                                       for bd in sd_model.business_domains}

    for sd in sd_model.all_sds():
        # Structured Consumes/Produces.
        for sid in sd.consumes_sds:
            if sid in sd_ids:
                add(sid, sd.id, "consumes-sd")
        for sid in sd.produces_sds:
            if sid in sd_ids:
                add(sd.id, sid, "produces-sd")
        # Narrative inputs.
        for ref in sd.upstream_sds:
            if ref.startswith("SD-") and ref in sd_ids and ref != sd.id:
                add(ref, sd.id, "narrative-input")
            elif ref.startswith("BD-") and ref in bd_ids and ref != sd.bd_id:
                # Aggregate-function-reference: one edge from the BD node,
                # NOT fan-out per member SD. See module docstring + OIM-54
                # cycle-2 B-4 (the fan-out fix). Same-BD self-references
                # (an SD that names its own BD as input) are dropped.
                add(ref, sd.id, "narrative-bd-input")
        for ref in sd.downstream_sds:
            if ref.startswith("SD-") and ref in sd_ids and ref != sd.id:
                add(sd.id, ref, "narrative-output")
            elif ref.startswith("BD-") and ref in bd_ids and ref != sd.bd_id:
                add(sd.id, ref, "narrative-bd-output")

    return bundle


def build_entity_graph(entity_model: EntityModel) -> list[tuple[str, str, str]]:
    """Return entity FK edges as (source, target, kind) triples."""
    edges: list[tuple[str, str, str]] = []
    for e in entity_model.entities:
        for fk in e.fk_targets:
            edges.append((e.id, fk, "fk"))
        if e.specialises:
            edges.append((e.id, e.specialises, "specialises"))
    return edges
