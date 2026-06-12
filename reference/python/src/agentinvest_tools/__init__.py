"""agentINVEST Python tool + data layer.

The Python side of the ADR-0054 polyglot split: typed Restate tool *services*
(model-free dispatch boundaries, never "agents") invoked over the shared Restate
substrate by the TypeScript orchestrator. OIM-101 stands up the workspace and the
cross-language RPC seam; the dbt canonical data layer (OIM-102) and the typed
per-Service-Operation tool surface (OIM-103+) build on it.
"""

__all__ = ["__version__"]

__version__ = "0.0.0"
