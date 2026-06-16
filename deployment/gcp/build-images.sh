#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID=${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}
IMAGE_TAG=${IMAGE_TAG:-latest}

if [ -z "$PROJECT_ID" ]; then
  echo 'PROJECT_ID is required. Set it via export PROJECT_ID=...' >&2
  exit 1
fi

REGION=${REGION:-us-central1}
REPOSITORY=${REPOSITORY:-agentinvest}

build_and_push() {
  local image_name=$1
  local dockerfile=$2

  echo "Building $image_name from $dockerfile"
  docker build -t "gcr.io/${PROJECT_ID}/${image_name}:${IMAGE_TAG}" -f "$dockerfile" .
  docker push "gcr.io/${PROJECT_ID}/${image_name}:${IMAGE_TAG}"
}

build_and_push "restate-server" "deployment/gcp/Dockerfile.restate"
build_and_push "agentinvest-ts-endpoint" "deployment/gcp/Dockerfile.ts-endpoint"
build_and_push "agentinvest-py-endpoint" "deployment/gcp/Dockerfile.py-endpoint"
build_and_push "operator-ui" "deployment/gcp/Dockerfile.operator-ui"
build_and_push "agentinvest-mcp" "deployment/gcp/Dockerfile.mcp"
