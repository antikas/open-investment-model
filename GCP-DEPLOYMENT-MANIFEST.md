# GCP Deployment Manifest for agentINVEST

## Recommended repository artifacts

Create the following files and directories as the next implementation scaffolding:

- `deployment/gcp/Dockerfile.restate`
- `deployment/gcp/Dockerfile.ts-endpoint`
- `deployment/gcp/Dockerfile.py-endpoint`
- `deployment/gcp/Dockerfile.operator-ui`
- `deployment/gcp/Dockerfile.mcp`
- `deployment/gcp/build-images.sh`
- `deployment/gcp/README.md`
- `deployment/gcp/cloudrun/README.md`
- `deployment/gcp/k8s/namespace.yaml`
- `deployment/gcp/k8s/configmap.yaml`
- `deployment/gcp/k8s/rbac.yaml`
- `deployment/gcp/k8s/secret-template.yaml`
- `deployment/gcp/k8s/restate-deployment.yaml`
- `deployment/gcp/k8s/ts-endpoint-deployment.yaml`
- `deployment/gcp/k8s/py-endpoint-deployment.yaml`
- `deployment/gcp/k8s/operator-ui-deployment.yaml`
- `deployment/gcp/k8s/mcp-sidecar.yaml`
- `deployment/gcp/k8s/services.yaml`
- `deployment/gcp/k8s/ingress.yaml`
- `deployment/gcp/cloudsql/README.md`
- `deployment/gcp/secret-manager/README.md`
- `deployment/gcp/vertex-ai/README.md`

## What each artifact should cover

### Dockerfiles

- Build the runtime packages and dependencies.
- Set entrypoints for the TS endpoint, Python endpoint, Restate substrate, and UI.
- Use environment variables for configuration.

### Kubernetes manifests

- Deploy each container in a dedicated Deployment.
- Use a `Namespace` for the agentINVEST stack.
- Use a `ConfigMap` for non-sensitive runtime config.
- Use a `Secret` or Secret Manager + CSI driver for database credentials, AI keys, and service credentials.
- Use `ServiceAccount` and Workload Identity to avoid image-embedded secrets.
- Use `Role` / `RoleBinding` with least privilege for runtime access to cluster resources.
- Keep Restate admin and ingress services internal.
- Expose only the Operator UI or a dedicated gateway service externally.

### Cloud SQL and dbt

- Document connecting `dbt` to Cloud SQL Postgres.
- Use `reference/dbt/profiles.yml` prod target as the basis for connection settings.
- Prefer Cloud SQL private IP and VPC-native connectivity.
- Ensure separate schemas for canonical data and Restate state if required.
- Validate `dbt build` against the Postgres prod profile before production rollout.

### Secret Manager

- Map secrets such as:
  - `ANTHROPIC_API_KEY` or Vertex AI credentials
  - `AGENTINVEST_PG_HOST`
  - `AGENTINVEST_PG_PORT`
  - `AGENTINVEST_PG_USER`
  - `AGENTINVEST_PG_PASSWORD`
  - `AGENTINVEST_PG_DBNAME`
  - `AGENTINVEST_PG_SCHEMA`
  - `RESTATE_ADMIN_URL`
  - `RESTATE_INGRESS_URL`
- Grant `secretmanager.secretAccessor` only to the runtime service account.
- Use a Secret Manager CSI driver or `gcloud secrets versions access` pattern where needed.

### Vertex AI

- Describe the model provider adapter.
- Define how the planner can switch provider with environment variables.
- Recommend secure network egress controls.
- Use Workload Identity for Vertex AI access and avoid embedding service keys.

## Deployment topology notes

- The Restate substrate should remain a stateful internal service.
- The TS and Python endpoints are separate service registrations against Restate.
- The MCP sidecar can remain a thin ingress/distributor to the journaled services.
- The operator UI should be isolated behind authenticated access.

## Security posture

- Use a private GKE cluster.
- Use VPC-native Cloud SQL and private IP where possible.
- Protect UI ingress with IAP or Cloud Armor.
- Keep the Restate admin/ingress plane internal-only.
- Use Workload Identity for service account access.

