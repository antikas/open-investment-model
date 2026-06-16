# GCP Deployment for agentINVEST

This folder contains the deployment scaffold for running the agentINVEST reference implementation on Google Cloud Platform.

## What is included

- Dockerfiles for each runtime component:
  - `Dockerfile.restate` — the Restate substrate container
  - `Dockerfile.ts-endpoint` — the TypeScript agentINVEST handler endpoint
  - `Dockerfile.py-endpoint` — the Python agentINVEST tool endpoint
  - `Dockerfile.operator-ui` — the operator UI container
  - `Dockerfile.mcp` — the MCP stdio sidecar container
- Cloud Run deployment guidance under `cloudrun/`
- Existing Kubernetes manifests under `k8s/` as a legacy/alternative path
- Deployment helper scripts for image build and manifest application
- GCP Secret Manager and Vertex AI guidance in adjacent folders

## Deployment overview

1. Build and push container images to Artifact Registry / Container Registry.
2. Deploy the runtime to Cloud Run services.
3. Use DuckDB for canonical data on Cloud Run with an ephemeral local file path and optional GCS backup.
4. Create secrets for AI provider keys and runtime configuration.
5. Configure Cloud Run service-to-service authentication and internal access.

## Build images

From the repo root:

```sh
cd /home/admin_user/open-investment-model
export PROJECT_ID="$(gcloud config get-value project)"
export IMAGE_TAG="latest"
./deployment/gcp/build-images.sh
```

## Deploy on Cloud Run

Use `gcloud run deploy` to publish each service.
Example:

```sh
export PROJECT_ID="$(gcloud config get-value project)"
export REGION="us-central1"
export IMAGE_TAG="latest"

# Restate substrate
gcloud run deploy agentinvest-restate \
  --image="gcr.io/$PROJECT_ID/agentinvest-restate:$IMAGE_TAG" \
  --region="$REGION" \
  --no-allow-unauthenticated \
  --set-env-vars="RESTATE_PORT=8080"

# TypeScript endpoint
gcloud run deploy agentinvest-ts-endpoint \
  --image="gcr.io/$PROJECT_ID/agentinvest-ts-endpoint:$IMAGE_TAG" \
  --region="$REGION" \
  --no-allow-unauthenticated

# Python endpoint
gcloud run deploy agentinvest-py-endpoint \
  --image="gcr.io/$PROJECT_ID/agentinvest-py-endpoint:$IMAGE_TAG" \
  --region="$REGION" \
  --no-allow-unauthenticated

# Operator UI
gcloud run deploy agentinvest-operator-ui \
  --image="gcr.io/$PROJECT_ID/agentinvest-operator-ui:$IMAGE_TAG" \
  --region="$REGION" \
  --no-allow-unauthenticated
```

## Notes

- The Restate server is run as a Cloud Run service, and the TS/Python endpoints register with it over service URLs.
- Each service must bind to `0.0.0.0` and expose the port configured in its container.
- `reference/dbt/profiles.yml` remains DuckDB-first for this deployment; the Postgres placeholder profile is not used.
- The DuckDB canonical store can be placed in `/tmp/agentinvest/duckdb/canonical.duckdb` inside Cloud Run and optionally backed up to a GCS bucket.
- The `reference/tools/restate-server` binary must be present for `Dockerfile.restate` to build.

## GCP integration scope

- Use DuckDB for canonical data and append-only stores in this Cloud Run deployment.
- Use Secret Manager for AI keys, runtime config, and any optional backup credentials.
- Use Cloud Run service account authentication for service-to-service communication.
- Keep the Restate admin/ingress plane internal-only where possible.
- Protect the operator UI with authenticated access (IAP or Cloud Run IAM) if exposed publicly.
