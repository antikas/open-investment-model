"""agentINVEST Python tool + data layer.

The Python side of the polyglot split: typed Restate tool *services*
(model-free dispatch boundaries, never "agents") invoked over the shared Restate
substrate by the TypeScript orchestrator. The workspace and the cross-language RPC
seam, the dbt canonical data layer, and the typed per-Service-Operation tool surface
build on it.
"""

__all__ = ["__version__"]

__version__ = "0.0.0"
