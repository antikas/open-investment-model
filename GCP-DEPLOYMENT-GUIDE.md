# GCP Deployment Guide for agentINVEST

This repository now contains a complete deployment documentation package for running agentINVEST on Google Cloud Platform.

## What is included

- `deployment/gcp/README.md` — the main GCP deployment entrypoint.
- `deployment/gcp/cloudrun/README.md` — Cloud Run-specific deployment instructions.
- `deployment/gcp/secret-manager/README.md` — secret management guidance.
- `deployment/gcp/vertex-ai/README.md` — AI provider integration guidance.
- `deployment/gcp/cloudsql/README.md` — optional Cloud SQL migration notes.
- `GCP-DEPLOYMENT-PLAN.md` — architecture and deployment strategy.
- `GCP-DEPLOYMENT-MANIFEST.md` — artifact manifest and scaffolding checklist.

## Recommended deployment path

1. Use Cloud Run as the primary target.
2. Keep the canonical data layer on DuckDB for this deployment.
3. Use Secret Manager for keys and runtime secrets.
4. Use Cloud Run service account IAM for service-to-service authentication.
5. Keep the operator UI protected behind Cloud Run IAM or IAP.

## Prerequisites

- `gcloud` installed and authenticated.
- Active GCP project set with `gcloud config set project <PROJECT_ID>`.
- `run.googleapis.com` enabled in the project.
- `artifactregistry.googleapis.com` or `containerregistry.googleapis.com` enabled.
- `secretmanager.googleapis.com` enabled.
- A Cloud Run service account with least-privilege access.

## Quick start

1. Review `deployment/gcp/README.md`.
2. Build and push images with `./deployment/gcp/build-images.sh`.
3. Deploy the Cloud Run services using the commands in `deployment/gcp/cloudrun/README.md`.
4. Configure secret injection and runtime environment variables.
5. Confirm the services are reachable and the Restate endpoint is registered.

## Do we need a code fork?

No, a fork is not required to deploy this repository in your GCP environment.

- Use the existing branch `gcp-deployment-plan` if you want to keep changes isolated within this repo.
- Fork only if you need a separate repository copy for a different upstream or long-term divergence.

## Notes

- The current Cloud Run deployment is the intended path for the present environment because GKE is blocked.
- Cloud SQL is intentionally excluded from the current deployment, and DuckDB is used instead.
- The `deployment/gcp/k8s/` manifests are preserved as an alternative or future migration path.
