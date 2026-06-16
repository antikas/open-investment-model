# GCP Deployment Plan for agentINVEST

## 1. Summary

agentINVEST is a reference implementation built around:
- A durable Restate substrate
- A TypeScript orchestrator/control plane
- A Python planner, tool services, and canonical data layer
- A dbt canonical data pipeline
- OpenAPI and MCP ingress surfaces
- An operator UI

This plan targets enterprise deployment on Google Cloud Platform using native managed services where feasible.

## 2. Current state

- No Docker, Kubernetes, Terraform, or GCP manifests exist in the repo.
- Local dev infrastructure is built around a self-hosted Restate binary and a polyglot workspace.
- `reference/ts/` hosts the orchestrator endpoint and CLI.
- `reference/python/` hosts the planner, typed tool services, MCP server, and dbt integration.
- `reference/operator-ui/` hosts the Next.js operator console.
- The planner currently uses Anthropic Sonnet 4.6 via `ANTHROPIC_API_KEY`.
- The canonical data layer is currently DuckDB-based in dev and has a `dbt-postgres` placeholder profile for prod.

## 3. Proposed GCP architecture

### Deployment target evaluation

- This repo is not a native ADK agent project. It is a polyglot reference implementation built around a self-hosted Restate substrate, a local TypeScript handler endpoint, a Python tool endpoint, and a durable runtime.
- Because GKE is blocked in the current environment, choose **Cloud Run** as the primary deployment target.
- Cloud Run supports separately deployed services and service-to-service authentication, but it introduces tradeoffs for stateful workloads and callback reachability.
- Use Cloud Run internal connectivity, signed identity tokens, and service-to-service auth to connect Restate and endpoint services.
- Avoid Cloud SQL entirely for this deployment and keep the canonical data layer in **DuckDB**.

### Core runtime

- Deploy the runtime to Cloud Run services.
  - `agentinvest-restate`
  - `agentinvest-ts-endpoint`
  - `agentinvest-py-endpoint`
  - `agentinvest-mcp` (optional)
  - `agentinvest-operator-ui`

### Data persistence

- Use **DuckDB** for canonical data and append-only stores.
- Store the DuckDB file under an ephemeral Cloud Run path such as `/tmp/agentinvest/duckdb/canonical.duckdb`.
- For durability across container restarts, optionally backup the DuckDB file to a GCS bucket from startup/shutdown logic.
- Use **Secret Manager** for AI keys, runtime config, and any optional backup credentials.
- Use Cloud Run service account authentication for secure service-to-service communication.

### AI model integration

- Abstract the current Anthropic call in `reference/python/src/agentinvest_orchestrator/planner.py`.
- Implement a provider switch for `ANTHROPIC` and `VERTEX_AI`.
- If Anthropic remains, control egress and store the key in Secret Manager.

### Networking and security

- Keep Restate admin and ingress internal to the private GKE cluster.
- Expose only the operator UI or a dedicated API gateway as needed.
- Protect external access with IAP, Cloud Armor, or private ingress.
- Use a private VPC with VPC-native Cloud SQL private IP where possible.
- Enforce least-privilege IAM for service accounts and Secret Manager access.

### Observability

- Send application logs to **Cloud Logging**.
- Export metrics to **Cloud Monitoring**.
- Persist audit journal exports to a locked GCS bucket with retention and immutability.

## 4. Deployment surfaces

- `restate-server` container
- `agentinvest-ts-endpoint` container
- `agentinvest-py-endpoint` container
- `mcp-server` sidecar container
- `operator-ui` container
- Optional `openapi` docs container for Swagger UI

## 5. Migration tasks

1. Containerize the runtime packages:
   - Restate substrate
   - TS endpoint
   - Python endpoint
   - MCP stdio sidecar
   - Operator UI
2. Replace DuckDB with Cloud SQL Postgres for the canonical data layer.
3. Migrate append-only stores to Cloud SQL or a managed store.
4. Add provider abstraction for the planner model call.
5. Add Secret Manager integration and GKE Workload Identity.
6. Secure the UI and admin surfaces with GCP-native controls.
7. Add audit export automation to GCS.
8. Enable required GCP APIs for the target project and validate service account roles.

## 6. Verification criteria

- The runtime can register and invoke the agentINVEST handlers over Restate.
- The placeholder bootstrap proof works after switching to private GCP service endpoints.
- `dbt` builds successfully against Cloud SQL Postgres.
- The planner LLM call and `PlanSchema` validation succeed.
- The operator UI and OpenAPI surface are protected behind secure access.

## 7. Phased rollout

1. Proof-of-concept deployment on GKE with local config and internal service endpoints.
2. Build and push containers to Artifact Registry / Container Registry.
3. Cloud SQL integration for canonical/dbt data and `reference/dbt/profiles.yml` production profile validation.
4. Secure the UI and OpenAPI with IAP, Cloud Armor, or private ingress.
5. Harden the AI provider integration and support Vertex AI as an option.
6. Add audit export automation and enterprise monitoring.

## 8. Relevant files

- `reference/README.md`
- `reference/ts/README.md`
- `reference/python/README.md`
- `reference/docs/architecture/agentinvest-solution-architecture.md`
- `reference/python/src/agentinvest_orchestrator/planner.py`
- `reference/python/src/agentinvest_tools/mcp_server.py`
- `reference/python/src/agentinvest_tools/endpoint.py`
- `reference/operator-ui/README.md`
- `reference/dbt/profiles.yml`
- `reference/config/restate-dev.toml`

