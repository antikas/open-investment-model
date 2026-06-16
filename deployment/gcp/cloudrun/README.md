# Cloud Run deployment for agentINVEST

This folder documents how to deploy the agentINVEST reference implementation to Google Cloud Run using DuckDB as the canonical data layer.

## Goals

- Deploy each runtime component as a separate Cloud Run service
- Use DuckDB for canonical and append-only storage instead of Cloud SQL
- Use Secret Manager for API keys and runtime secrets
- Use Cloud Run service account authentication for internal connectivity
- Keep the operator UI protected behind Cloud Run IAM or IAP

## Services

Recommended Cloud Run services:

- `agentinvest-restate`
- `agentinvest-ts-endpoint`
- `agentinvest-py-endpoint`
- `agentinvest-mcp` (optional)
- `agentinvest-operator-ui`

## Build and push images

From the repo root:

```sh
cd /home/admin_user/open-investment-model
export PROJECT_ID="$(gcloud config get-value project)"
export IMAGE_TAG="latest"
./deployment/gcp/build-images.sh
```

This script should build and push the following images:

- `gcr.io/$PROJECT_ID/agentinvest-restate:$IMAGE_TAG`
- `gcr.io/$PROJECT_ID/agentinvest-ts-endpoint:$IMAGE_TAG`
- `gcr.io/$PROJECT_ID/agentinvest-py-endpoint:$IMAGE_TAG`
- `gcr.io/$PROJECT_ID/agentinvest-operator-ui:$IMAGE_TAG`
- `gcr.io/$PROJECT_ID/agentinvest-mcp:$IMAGE_TAG`

## Deploy Cloud Run services

Set deployment variables:

```sh
export PROJECT_ID="$(gcloud config get-value project)"
export REGION="us-central1"
export IMAGE_TAG="latest"
export SERVICE_ACCOUNT="agentinvest-cloudrun-sa@$PROJECT_ID.iam.gserviceaccount.com"
```

Deploy the Restate service:

```sh
gcloud run deploy agentinvest-restate \
  --image="gcr.io/$PROJECT_ID/agentinvest-restate:$IMAGE_TAG" \
  --region="$REGION" \
  --no-allow-unauthenticated \
  --service-account="$SERVICE_ACCOUNT" \
  --set-env-vars="RESTATE_PORT=8080"
```

Deploy the TypeScript endpoint:

```sh
gcloud run deploy agentinvest-ts-endpoint \
  --image="gcr.io/$PROJECT_ID/agentinvest-ts-endpoint:$IMAGE_TAG" \
  --region="$REGION" \
  --no-allow-unauthenticated \
  --service-account="$SERVICE_ACCOUNT" \
  --set-env-vars="RESTATE_URL=https://agentinvest-restate-$REGION.a.run.app"
```

Deploy the Python endpoint:

```sh
gcloud run deploy agentinvest-py-endpoint \
  --image="gcr.io/$PROJECT_ID/agentinvest-py-endpoint:$IMAGE_TAG" \
  --region="$REGION" \
  --no-allow-unauthenticated \
  --service-account="$SERVICE_ACCOUNT" \
  --set-env-vars="RESTATE_URL=https://agentinvest-restate-$REGION.a.run.app"
```

Deploy the operator UI:

```sh
gcloud run deploy agentinvest-operator-ui \
  --image="gcr.io/$PROJECT_ID/agentinvest-operator-ui:$IMAGE_TAG" \
  --region="$REGION" \
  --no-allow-unauthenticated \
  --service-account="$SERVICE_ACCOUNT"
```

If you need an MCP sidecar service:

```sh
gcloud run deploy agentinvest-mcp \
  --image="gcr.io/$PROJECT_ID/agentinvest-mcp:$IMAGE_TAG" \
  --region="$REGION" \
  --no-allow-unauthenticated \
  --service-account="$SERVICE_ACCOUNT"
```

## Runtime config

Set runtime environment variables through Cloud Run or Secret Manager:

- `ANTHROPIC_API_KEY` or Vertex AI credentials
- `RESTATE_URL`
- `RESTATE_PORT`
- `RESTATE_ADMIN_URL`
- `RESTATE_INGRESS_URL`
- `AGENTINVEST_DUCKDB_PATH` (e.g. `/tmp/agentinvest/duckdb/canonical.duckdb`)
- `AGENTINVEST_LOG_LEVEL`

## DuckDB storage

- Use a local Cloud Run writable path for DuckDB, such as `/tmp/agentinvest/duckdb/canonical.duckdb`.
- Optionally add startup/shutdown logic to copy the DuckDB file to/from a GCS bucket for persistence and restore.
- Note that Cloud Run containers are ephemeral, so any local DuckDB file is not durable across instance replacement.

## Secret Manager

Use Secret Manager to store keys and runtime secrets, then mount or inject them into Cloud Run:

```sh
gcloud secrets create ANTHROPIC_API_KEY --data-file=-
```

Use `gcloud run services update` to add secret environment variables when needed.

## Permissions

- Grant the Cloud Run service account access to Secret Manager secrets.
- Use Cloud Run IAM to restrict service invocation.
- Use `gcloud run services add-iam-policy-binding` to allow the TS and Python services to call Restate if you secure it with IAM.

## Notes

- This Cloud Run deployment is the current target because GKE is blocked in the environment.
- The project should not rely on Cloud SQL for this deployment.
- Keep internal service communication private and authenticated.
- If you later migrate to Cloud SQL, preserve the existing `reference/dbt/profiles.yml` Postgres placeholder profile as a future option.
