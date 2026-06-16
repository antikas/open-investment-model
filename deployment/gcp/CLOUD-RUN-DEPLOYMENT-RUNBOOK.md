# Cloud Run Deployment Runbook for agentINVEST

This runbook is the complete operational guide for deploying agentINVEST to Google Cloud Run.

## Prerequisites

- `gcloud` CLI installed and authenticated
- Active GCP project with required APIs enabled:
  - `run.googleapis.com` (Cloud Run)
  - `artifactregistry.googleapis.com` or `containerregistry.googleapis.com`
  - `secretmanager.googleapis.com` (Secret Manager)
  - `cloudlog.googleapis.com` (Cloud Logging)
- Docker installed (for building images locally)
- Sufficient IAM permissions (Compute Admin, Secret Manager Admin, Service Accounts Admin)

## Step 1: Set up environment variables

```sh
export PROJECT_ID="$(gcloud config get-value project)"
export REGION="us-central1"  # or your preferred region
export IMAGE_TAG="latest"
export SERVICE_ACCOUNT="agentinvest-cloudrun-sa"
export SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com"
export RESTATE_SERVICE_URL="https://agentinvest-restate-${REGION}.a.run.app"
```

## Step 2: Create service account and grant IAM roles

```sh
# Create the service account
gcloud iam service-accounts create "${SERVICE_ACCOUNT}" \
  --display-name="agentINVEST Cloud Run service account"

# Grant Cloud Run roles
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/run.invoker"

# Grant Secret Manager access
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/secretmanager.secretAccessor"

# Grant Cloud Logging access
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/logging.logWriter"
```

## Step 3: Create and store secrets in Secret Manager

```sh
# Create secret for Anthropic API key (or use Vertex AI credentials instead)
echo -n "your-anthropic-api-key" | gcloud secrets create ANTHROPIC_API_KEY --data-file=-

# Verify secret was created
gcloud secrets list

# Grant the service account access to the secret
gcloud secrets add-iam-policy-binding ANTHROPIC_API_KEY \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/secretmanager.secretAccessor"
```

## Step 4: Build and push container images

```sh
cd /path/to/open-investment-model

# Build images
export PROJECT_ID="$(gcloud config get-value project)"
export IMAGE_TAG="latest"
./deployment/gcp/build-images.sh

# Verify images were pushed
gcloud container images list --repository="gcr.io/${PROJECT_ID}"
```

## Step 5: Deploy Restate service

```sh
gcloud run deploy agentinvest-restate \
  --image="gcr.io/${PROJECT_ID}/agentinvest-restate:${IMAGE_TAG}" \
  --region="${REGION}" \
  --no-allow-unauthenticated \
  --service-account="${SERVICE_ACCOUNT_EMAIL}" \
  --memory=2Gi \
  --cpu=2 \
  --timeout=900 \
  --set-env-vars="RESTATE_BASE_DIR=/tmp/restate,RESTATE_PORT=8080"
```

## Step 6: Deploy TypeScript endpoint

```sh
gcloud run deploy agentinvest-ts-endpoint \
  --image="gcr.io/${PROJECT_ID}/agentinvest-ts-endpoint:${IMAGE_TAG}" \
  --region="${REGION}" \
  --no-allow-unauthenticated \
  --service-account="${SERVICE_ACCOUNT_EMAIL}" \
  --memory=1Gi \
  --cpu=1 \
  --set-env-vars="RESTATE_URL=${RESTATE_SERVICE_URL},RESTATE_ADMIN_URL=http://localhost:9070,AGENTINVEST_ENDPOINT_PORT=9090"
```

## Step 7: Deploy Python endpoint

```sh
gcloud run deploy agentinvest-py-endpoint \
  --image="gcr.io/${PROJECT_ID}/agentinvest-py-endpoint:${IMAGE_TAG}" \
  --region="${REGION}" \
  --no-allow-unauthenticated \
  --service-account="${SERVICE_ACCOUNT_EMAIL}" \
  --memory=2Gi \
  --cpu=2 \
  --set-env-vars="RESTATE_URL=${RESTATE_SERVICE_URL},RESTATE_ADMIN_URL=http://localhost:9070,AGENTINVEST_PY_ENDPOINT_PORT=9091,AGENTINVEST_DUCKDB_PATH=/tmp/agentinvest/duckdb/canonical.duckdb" \
  --set-secrets="ANTHROPIC_API_KEY=ANTHROPIC_API_KEY:latest"
```

## Step 8: Deploy operator UI

```sh
gcloud run deploy agentinvest-operator-ui \
  --image="gcr.io/${PROJECT_ID}/agentinvest-operator-ui:${IMAGE_TAG}" \
  --region="${REGION}" \
  --allow-unauthenticated \
  --service-account="${SERVICE_ACCOUNT_EMAIL}" \
  --memory=512Mi \
  --cpu=1
```

## Step 9: Configure service-to-service authentication

Allow the endpoints to call Restate:

```sh
# Grant TS endpoint permission to call Restate
gcloud run services add-iam-policy-binding agentinvest-restate \
  --region="${REGION}" \
  --member="serviceAccount:$(gcloud run services describe agentinvest-ts-endpoint --region=${REGION} --format='value(status.template.spec.serviceAccountName)')@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/run.invoker"

# Grant Python endpoint permission to call Restate
gcloud run services add-iam-policy-binding agentinvest-restate \
  --region="${REGION}" \
  --member="serviceAccount:$(gcloud run services describe agentinvest-py-endpoint --region=${REGION} --format='value(status.template.spec.serviceAccountName)')@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/run.invoker"
```

## Step 10: Verify deployments

### Check service status

```sh
gcloud run services list --region="${REGION}"

# Get service URLs
gcloud run services describe agentinvest-restate --region="${REGION}" --format='value(status.address.url)'
gcloud run services describe agentinvest-ts-endpoint --region="${REGION}" --format='value(status.address.url)'
gcloud run services describe agentinvest-py-endpoint --region="${REGION}" --format='value(status.address.url)'
gcloud run services describe agentinvest-operator-ui --region="${REGION}" --format='value(status.address.url)'
```

### Check service logs

```sh
gcloud run services describe agentinvest-restate --region="${REGION}" --format='value(status.logUrl)' | xargs echo "Restate logs:"
gcloud run services describe agentinvest-py-endpoint --region="${REGION}" --format='value(status.logUrl)' | xargs echo "Python endpoint logs:"
```

## Step 11: Run smoke tests

Execute the smoke test script:

```sh
bash deployment/gcp/cloudrun/smoke-test.sh
```

See `deployment/gcp/cloudrun/smoke-test.sh` for full smoke test coverage.

## Step 12: Access the operator UI

The operator UI is publicly accessible at its Cloud Run URL (see Step 10).

For production, restrict access:

```sh
gcloud run services add-iam-policy-binding agentinvest-operator-ui \
  --region="${REGION}" \
  --member="user:your-email@example.com" \
  --role="roles/run.invoker"
```

## Troubleshooting

### Service fails to start

Check logs:

```sh
gcloud run services describe agentinvest-restate --region="${REGION}" --format='value(status.logUrl)'
```

### Endpoint cannot reach Restate

Verify service-to-service auth is set up (Step 9).

Verify environment variables are set correctly.

Check Cloud Run logs for network errors.

### DuckDB persistence lost after restart

DuckDB files in `/tmp` are ephemeral. For durability:

1. Add GCS backup/restore logic to Python endpoint startup/shutdown
2. Or migrate to Cloud SQL

## Rollback

To rollback a deployment:

```sh
# List revision history
gcloud run revisions list --service=agentinvest-restate --region="${REGION}"

# Route traffic back to a previous revision
gcloud run services update-traffic agentinvest-restate \
  --region="${REGION}" \
  --to-revisions=REVISION_ID=100
```

## Clean up

To delete all resources:

```sh
gcloud run services delete agentinvest-restate --region="${REGION}" --quiet
gcloud run services delete agentinvest-ts-endpoint --region="${REGION}" --quiet
gcloud run services delete agentinvest-py-endpoint --region="${REGION}" --quiet
gcloud run services delete agentinvest-operator-ui --region="${REGION}" --quiet

gcloud iam service-accounts delete "${SERVICE_ACCOUNT_EMAIL}" --quiet
gcloud secrets delete ANTHROPIC_API_KEY --quiet
```

## Next steps

- Set up Cloud Logging and alerting
- Configure Cloud Run with VPC for private networking
- Add backup/restore for DuckDB state
- Implement CI/CD pipeline for automated deployments
- Plan migration to Cloud SQL for production dbt builds
