# agentINVEST — The Reference Implementation

This directory holds **agentINVEST**: an agent-native reference implementation built on the [OpenIM model](../model/README.md).

Where the model (`../model/`) is the reference model itself — a decomposition, written in Markdown and schemas — agentINVEST is the model made executable and agent-consumable. It is the buy-side counterpart to the public AI-native bank reference architectures: it treats AI agents as a first-class channel into the institutional investment manager.

## The surface

- **A typed agent-tool catalogue** — each tool maps to operations of a Service Domain in the model. Typed inputs and outputs, consent- and mandate-scoped.
- **An MCP server** exposing those tools to MCP-compatible clients.
- **An OpenAPI surface** as the single source of truth for the API, with the model as its semantic backbone.
- **A canonical data layer** — the OpenIM entity model realised as schemas and a reference data store, with synthetic but realistic sample data.
- **Observability** — agent trace logs, decision provenance, and a metric layer, so every agent action against the firm is auditable.
- **Audit and governance binding** — human-in-the-loop gates on high-stakes operations, model-decision provenance, alignment to the FINOS AI Governance Framework. Fiduciary discipline applied to an agent channel.
- **Recorded build decisions** — the architecture decisions behind agentINVEST are kept as decision records in the project's governance history.

## Status

The substrate is built: the durable-execution engine, the typed tool catalogue, the canonical dbt data layer, MCP and OpenAPI ingress, the operator UI with all four pages (Approvals, Operations, Deployments, and a canonical-data inspector), and a hash-chained audit journal are all in place. The first business workflow — the NAV strike — is built and audited end to end: a human approval gate, a journaled durable workflow, and crash-replay proven recovery.

Reconciliation is in build. The dual-book canonical layer, the IBOR/ABOR read services, the deterministic dual-pipeline reconciliation engine and the append-only break store are complete and audited; the propose-only AI stage over unexplained breaks is designed but not yet built, and the state-mutating correction workflow is not yet built. The tool surface today carries the BD-09 performance tools and the BD-12 book-of-record and reconciliation tools.

The stack is a typed tool surface and data layer in Python, a control plane and orchestrator in TypeScript, and a dbt-managed canonical data layer, with an MCP server and an OpenAPI spec as SSOT.

The build draws on substantial implementation precedent — working dbt pipeline practice and prior investment-data work (extraction with confidence scoring, mark-to-model valuation governance, entity resolution). That experience seeded agentINVEST's pipeline and tool layer.

## Run it

The end-to-end demo runs the full orchestrator loop — plan → resolve → dispatch → approve → aggregate → close — on the production virtual object, producing a real, audited performance attribution, then proves a full-chain crash-replay.

Prerequisites: Node ≥ 22 + pnpm; on Windows, WSL2 with a registered distro (the Restate server and the Python + dbt layer run inside it) and [`uv`](https://docs.astral.sh/uv/) installed inside WSL2 (see [`python/README.md`](python/README.md)). The planner makes a real Anthropic API call — **no API key ships with this repository**; you bring your own.

```sh
cd reference
pnpm install                       # the pnpm workspace (ts/ + operator-ui/)

# 1. Your Anthropic key (the planner's one LLM call). Create reference/.env:
#      ANTHROPIC_API_KEY=<your key>

# 2. Boot the durable-execution substrate (see ts/README.md):
pnpm dev:restate                   # hold it running; Ctrl-C to stop

# 3. Build the canonical data layer (the demo resolves its inputs from the marts):
pnpm dbt:build

# 4. Run the end-to-end demo:
node scripts/full-chain-demo.mjs   # or: pnpm full-chain-demo
```

The demo spawns its own Python endpoint (via `uv`, inside WSL2 on Windows) if one is not already registered, runs the attribution task end to end, asserts the results reconcile, then crashes the operation mid-flight and proves the journaled replay (the planner is not re-called, the tools are not re-run, the audit record is written once).

See [`../model/README.md`](../model/README.md) for what agentINVEST implements, and [`../PRIOR-ART.md`](../PRIOR-ART.md) for how it relates to the agent-native prior art.
