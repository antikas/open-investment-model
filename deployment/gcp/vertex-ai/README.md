# Vertex AI Provider Integration for agentINVEST

This folder documents how to integrate a GCP-native model provider with the agentINVEST planner.

## Design

- Add a provider abstraction in `reference/python/src/agentinvest_orchestrator/planner.py`.
- Use environment variables to choose the runtime provider.
- Support: `ANTHROPIC`, `VERTEX_AI`, or another external provider.

## Recommended env vars

- `AGENTINVEST_PLANNER_MODEL`
- `VERTEX_AI_MODEL`
- `VERTEX_AI_PROJECT`
- `VERTEX_AI_LOCATION`

## Security

- Use restricted egress for external providers.
- Use Workload Identity for Vertex AI access.
