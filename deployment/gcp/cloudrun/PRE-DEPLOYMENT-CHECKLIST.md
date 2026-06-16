# Pre-Deployment Checklist for agentINVEST Cloud Run

Use this checklist to verify all prerequisites and configurations before deploying to Cloud Run.

## GCP Project Setup

- [ ] GCP project is created and active
  - Verify: `gcloud config get-value project`
- [ ] Required APIs are enabled:
  - [ ] Cloud Run (`run.googleapis.com`)
  - [ ] Artifact Registry or Container Registry
  - [ ] Secret Manager (`secretmanager.googleapis.com`)
  - [ ] Cloud Logging (`logging.googleapis.com`)
  - Verify: `gcloud services list --enabled`
- [ ] Project quota allows for:
  - [ ] Cloud Run services (default: 250 services per project)
  - [ ] Container image storage (default: 500 GB)
  - [ ] Secrets storage (unlimited in Secret Manager)

## Service Account Setup

- [ ] Service account `agentinvest-cloudrun-sa` is created
  - Verify: `gcloud iam service-accounts list | grep agentinvest-cloudrun-sa`
- [ ] Service account has required IAM roles:
  - [ ] `roles/run.invoker` (can invoke Cloud Run services)
  - [ ] `roles/secretmanager.secretAccessor` (can read secrets)
  - [ ] `roles/logging.logWriter` (can write logs)
  - Verify: `gcloud projects get-iam-policy $PROJECT_ID --flatten="bindings[].members" | grep agentinvest-cloudrun-sa`

## Container Images

- [ ] All Dockerfiles are valid and ready:
  - [ ] `deployment/gcp/Dockerfile.restate` includes binary download
  - [ ] `deployment/gcp/Dockerfile.ts-endpoint`
  - [ ] `deployment/gcp/Dockerfile.py-endpoint`
  - [ ] `deployment/gcp/Dockerfile.operator-ui`
  - Verify: Docker files have been updated and verified locally
- [ ] Images can be built locally without errors:
  - [ ] Run `docker build -f deployment/gcp/Dockerfile.restate .` locally
  - [ ] Run `docker build -f deployment/gcp/Dockerfile.ts-endpoint .` locally
  - [ ] Run `docker build -f deployment/gcp/Dockerfile.py-endpoint .` locally
  - [ ] Run `docker build -f deployment/gcp/Dockerfile.operator-ui .` locally
- [ ] Build script is ready:
  - [ ] `deployment/gcp/build-images.sh` exists
  - [ ] Script has execution permissions: `chmod +x deployment/gcp/build-images.sh`
  - Verify: `./deployment/gcp/build-images.sh --help` or inspect file

## Secrets Management

- [ ] All required secrets are created in Secret Manager:
  - [ ] `ANTHROPIC_API_KEY` (or credentials for LLM provider)
  - [ ] Additional secrets as needed for your environment
  - Verify: `gcloud secrets list`
- [ ] Service account has access to all secrets:
  - [ ] Run: `gcloud secrets add-iam-policy-binding ANTHROPIC_API_KEY --member=serviceAccount:agentinvest-cloudrun-sa@$PROJECT_ID.iam.gserviceaccount.com --role=roles/secretmanager.secretAccessor`
  - Verify: `gcloud secrets get-iam-policy ANTHROPIC_API_KEY`

## Configuration and Environment

- [ ] Environment variables are documented:
  - [ ] `RESTATE_VERSION` = 1.6.2
  - [ ] `RESTATE_PORT` = 8080 (or configured port)
  - [ ] `REGION` = us-central1 (or your chosen region)
  - [ ] All required endpoint URLs and credentials
- [ ] DuckDB path is configured:
  - [ ] Python endpoint will use `/tmp/agentinvest/duckdb/canonical.duckdb`
  - [ ] Consider GCS backup strategy for persistence
- [ ] Restate configuration file exists:
  - [ ] `reference/config/restate-dev.toml` is ready
  - Verify: `cat reference/config/restate-dev.toml`

## Security and Access Control

- [ ] Service account permissions follow least-privilege principle:
  - [ ] No Project Editor or Owner roles granted
  - [ ] Only specific roles granted for required services
- [ ] Cloud Run services are not publicly accessible by default:
  - [ ] Use `--no-allow-unauthenticated` flag during deployment
  - [ ] Operator UI may be an exception (explicit IAM bindings)
- [ ] Service-to-service authentication is planned:
  - [ ] Endpoints can call Restate admin API
  - [ ] Identity tokens will be used for authentication

## Monitoring and Logging

- [ ] Cloud Logging is configured:
  - [ ] Service account has `roles/logging.logWriter` role
  - [ ] Log sink (if needed) is set up for centralized logging
- [ ] Error tracking is planned:
  - [ ] Cloud Error Reporting is considered
  - [ ] Alert policies are planned (optional)

## Network and Connectivity

- [ ] Cloud Run region is selected:
  - [ ] Verify region is available: `gcloud run regions list`
  - [ ] Region is close to your data/users
- [ ] VPC and private networking (optional):
  - [ ] If using VPC connectors, verify they exist
  - [ ] Firewall rules are configured

## Documentation and Runbooks

- [ ] Deployment documentation is complete:
  - [ ] `CLOUD-RUN-DEPLOYMENT-RUNBOOK.md` is reviewed
  - [ ] All commands and scripts are ready
- [ ] Rollback procedures are documented:
  - [ ] Know how to revert to previous revision
  - [ ] Cleanup commands are documented
- [ ] Troubleshooting guide is available:
  - [ ] Common issues and solutions are documented

## Pre-Deployment Testing

- [ ] Docker images build successfully:
  ```sh
  ./deployment/gcp/build-images.sh
  ```
- [ ] Build script output is reviewed:
  - [ ] No build errors
  - [ ] Images are tagged correctly
  - [ ] Images are pushed to Container Registry / Artifact Registry
- [ ] Environment variables are set:
  ```sh
  export PROJECT_ID="$(gcloud config get-value project)"
  export REGION="us-central1"
  export IMAGE_TAG="latest"
  export SERVICE_ACCOUNT="agentinvest-cloudrun-sa"
  ```
- [ ] Service account email is correct:
  ```sh
  echo "${SERVICE_ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com"
  ```

## Final Verification Before Deploy

- [ ] All checklist items are completed
- [ ] `gcloud auth list` shows correct authentication
- [ ] `gcloud config get-value project` shows correct project
- [ ] Dry-run commands reviewed (if applicable)
- [ ] Team is ready to monitor deployment
- [ ] Rollback plan is known and tested

## Deployment

Once all items are checked:

1. Run: `bash deployment/gcp/CLOUD-RUN-DEPLOYMENT-RUNBOOK.md` step-by-step
2. Monitor deployment progress in Cloud Console
3. Run smoke tests after deployment:
   ```sh
   bash deployment/gcp/cloudrun/smoke-test.sh
   ```
4. Access operator UI and verify functionality

## Post-Deployment

- [ ] All services show as "OK" in Cloud Run console
- [ ] Logs show no critical errors
- [ ] Health endpoints respond
- [ ] Operator UI is accessible
- [ ] Restate endpoints are registered
- [ ] End-to-end test succeeds

---

**Sign-off**: __________________ (Name) __________________ (Date)
