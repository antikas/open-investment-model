"""In-memory graph structures built from parsed markdown."""

from .build import build_capability_graph, build_entity_graph, GraphBundle

__all__ = ["build_capability_graph", "build_entity_graph", "GraphBundle"]
