#!/usr/bin/env bash
# GKE Deployment Error Handling and Rollback Guide
#
# This guide covers:
# 1. Pre-flight checks to prevent failures
# 2. Error handling during deployment
# 3. Rollback and cleanup procedures
# 4. Recovery steps for common failures

set -euo pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging
LOG_FILE="${LOG_FILE:-deployment_$(date +%Y%m%d_%H%M%S).log}"

log_info() {
  echo -e "${GREEN}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') $1" | tee -a "$LOG_FILE"
}

log_warn() {
  echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m-%d %H:%M:%S') $1" | tee -a "$LOG_FILE"
}

log_error() {
  echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') $1" | tee -a "$LOG_FILE"
}

log_section() {
  echo "" | tee -a "$LOG_FILE"
  echo -e "${BLUE}======================================${NC}" | tee -a "$LOG_FILE"
  echo -e "${BLUE}$1${NC}" | tee -a "$LOG_FILE"
  echo -e "${BLUE}======================================${NC}" | tee -a "$LOG_FILE"
}

# Trap errors and run cleanup
trap 'on_error' ERR
trap 'on_exit' EXIT

# State tracking
DEPLOYMENT_STATE_FILE="deployment_state.json"
ROLLED_BACK=false

on_error() {
  local line_no=$1
  log_error "Error on line $line_no"
  log_error "Deployment failed. Run: source deployment/gcp/ROLLBACK-AND-RECOVERY.sh"
  exit 1
}

on_exit() {
  if [ $? -eq 0 ]; then
    log_info "Deployment completed successfully"
  fi
}

# ============================================================================
# SECTION 1: PRE-FLIGHT CHECKS
# ============================================================================

preflight_checks() {
  log_section "Running Pre-Flight Checks"

  local checks_passed=0
  local checks_failed=0

  # 1. Check gcloud auth
  if gcloud auth list --filter=status:ACTIVE --format='value(account)' &>/dev/null; then
    log_info "✓ gcloud authenticated"
    ((checks_passed++))
  else
    log_error "✗ gcloud not authenticated. Run: gcloud auth login"
    ((checks_failed++))
  fi

  # 2. Check project is set
  if [ -n "${PROJECT_ID:-}" ]; then
    log_info "✓ PROJECT_ID set: $PROJECT_ID"
    ((checks_passed++))
  else
    log_error "✗ PROJECT_ID not set. Export: export PROJECT_ID=your-project"
    ((checks_failed++))
  fi

  # 3. Check APIs enabled
  for api in container sqladmin run artifactregistry; do
    if gcloud services list --enabled --filter="NAME:${api}.googleapis.com" --format='value(NAME)' 2>/dev/null | grep -q "${api}"; then
      log_info "✓ ${api}.googleapis.com enabled"
      ((checks_passed++))
    else
      log_error "✗ ${api}.googleapis.com NOT enabled"
      ((checks_failed++))
    fi
  done

  # 4. Check required tools
  for tool in docker kubectl gcloud; do
    if command -v $tool &>/dev/null; then
      log_info "✓ $tool installed"
      ((checks_passed++))
    else
      log_error "✗ $tool NOT installed"
      ((checks_failed++))
    fi
  done

  # 5. Check Docker daemon
  if docker ps &>/dev/null; then
    log_info "✓ Docker daemon running"
    ((checks_passed++))
  else
    log_error "✗ Docker daemon not running. Start Docker and retry"
    ((checks_failed++))
  fi

  # 6. Check disk space for Docker
  local available_space=$(df /var/lib/docker 2>/dev/null | awk 'NR==2 {print $4}')
  if [ "$available_space" -gt 10485760 ]; then  # 10GB
    log_info "✓ Sufficient disk space: $(numfmt --to=iec $available_space 2>/dev/null || echo "${available_space} KB")"
    ((checks_passed++))
  else
    log_warn "⚠ Low disk space. Docker builds may fail"
    ((checks_failed++))
  fi

  # 7. Check GKE cluster exists (if continuing from previous deployment)
  if [ -n "${CLUSTER_NAME:-}" ]; then
    if gcloud container clusters describe "$CLUSTER_NAME" --region="${REGION}" &>/dev/null; then
      log_info "✓ GKE cluster exists: $CLUSTER_NAME"
      ((checks_passed++))
    else
      log_warn "ℹ GKE cluster will be created: $CLUSTER_NAME"
    fi
  fi

  log_info "Pre-flight checks: $checks_passed passed, $checks_failed failed"
  
  if [ $checks_failed -gt 0 ]; then
    log_error "Pre-flight checks failed. Fix issues above and retry"
    return 1
  fi
}

# ============================================================================
# SECTION 2: DEPLOYMENT STATE TRACKING
# ============================================================================

save_deployment_state() {
  local key=$1
  local value=$2
  
  if [ -f "$DEPLOYMENT_STATE_FILE" ]; then
    # Update existing JSON
    jq ".\"$key\"=\"$value\"" "$DEPLOYMENT_STATE_FILE" > "${DEPLOYMENT_STATE_FILE}.tmp"
    mv "${DEPLOYMENT_STATE_FILE}.tmp" "$DEPLOYMENT_STATE_FILE"
  else
    # Create new JSON
    echo "{\"$key\":\"$value\"}" > "$DEPLOYMENT_STATE_FILE"
  fi
  
  log_info "State saved: $key = $value"
}

get_deployment_state() {
  local key=$1
  if [ -f "$DEPLOYMENT_STATE_FILE" ]; then
    jq -r ".\"$key\"" "$DEPLOYMENT_STATE_FILE" 2>/dev/null || echo ""
  fi
}

# ============================================================================
# SECTION 3: BUILD IMAGES WITH ERROR HANDLING
# ============================================================================

build_images_safe() {
  log_section "Building Container Images"

  local failed_images=()

  for image in "restate" "ts-endpoint" "py-endpoint" "operator-ui" "mcp"; do
    log_info "Building agentinvest-$image..."
    
    local dockerfile="deployment/gcp/Dockerfile.$image"
    if [ ! -f "$dockerfile" ]; then
      log_error "Dockerfile not found: $dockerfile"
      failed_images+=("$image")
      continue
    fi

    # Build with error handling
    if docker build \
      -t "gcr.io/${PROJECT_ID}/agentinvest-${image}:${IMAGE_TAG}" \
      -f "$dockerfile" \
      . \
      >> "$LOG_FILE" 2>&1; then
      log_info "✓ Built agentinvest-$image"
      save_deployment_state "image_${image}_built" "true"
    else
      log_error "✗ Failed to build agentinvest-$image"
      failed_images+=("$image")
    fi
  done

  if [ ${#failed_images[@]} -gt 0 ]; then
    log_error "Failed to build: ${failed_images[*]}"
    log_error "To retry: docker build -f deployment/gcp/Dockerfile.<name> ."
    return 1
  fi

  log_info "All images built successfully"
}

push_images_safe() {
  log_section "Pushing Container Images"

  local failed_pushes=()

  for image in "restate" "ts-endpoint" "py-endpoint" "operator-ui" "mcp"; do
    # Only push if build succeeded
    if [ "$(get_deployment_state "image_${image}_built")" != "true" ]; then
      log_warn "Skipping push for $image (build failed)"
      continue
    fi

    log_info "Pushing agentinvest-$image..."
    
    if docker push \
      "gcr.io/${PROJECT_ID}/agentinvest-${image}:${IMAGE_TAG}" \
      >> "$LOG_FILE" 2>&1; then
      log_info "✓ Pushed agentinvest-$image"
      save_deployment_state "image_${image}_pushed" "true"
    else
      log_error "✗ Failed to push agentinvest-$image"
      failed_pushes+=("$image")
      # Note: Don't fail immediately; try to push remaining images
    fi
  done

  if [ ${#failed_pushes[@]} -gt 0 ]; then
    log_error "Failed to push: ${failed_pushes[*]}"
    log_warn "Network issues likely. Retry: docker push gcr.io/$PROJECT_ID/agentinvest-<name>:$IMAGE_TAG"
    return 1
  fi

  log_info "All images pushed successfully"
}

# ============================================================================
# SECTION 4: GKE DEPLOYMENT WITH ROLLBACK
# ============================================================================

deploy_to_gke_safe() {
  log_section "Deploying to GKE"

  local cluster_name="${CLUSTER_NAME}"
  local namespace="${NAMESPACE:-agentinvest}"

  # Check cluster exists
  if ! gcloud container clusters describe "$cluster_name" --region="${REGION}" &>/dev/null; then
    log_error "GKE cluster not found: $cluster_name"
    return 1
  fi

  # Get credentials
  log_info "Getting cluster credentials..."
  gcloud container clusters get-credentials "$cluster_name" --region="${REGION}" >> "$LOG_FILE" 2>&1

  # Create namespace
  log_info "Creating namespace: $namespace"
  if kubectl create namespace "$namespace" --dry-run=client -o yaml | kubectl apply -f - >> "$LOG_FILE" 2>&1; then
    save_deployment_state "namespace_created" "true"
    log_info "✓ Namespace ready"
  else
    log_error "✗ Failed to create namespace"
    return 1
  fi

  # Apply manifests with checksums for rollback
  log_info "Deploying Kubernetes manifests..."
  
  local manifests=("namespace" "service-account" "restate-deployment" "ts-endpoint-deployment" "py-endpoint-deployment" "operator-ui-deployment" "hpa" "network-policy")
  
  for manifest in "${manifests[@]}"; do
    local manifest_file="deployment/gcp/kubernetes/${manifest}.yaml"
    
    if [ ! -f "$manifest_file" ]; then
      log_warn "Manifest not found: $manifest_file"
      continue
    fi

    log_info "Applying $manifest..."
    
    if kubectl apply -f "$manifest_file" --namespace="$namespace" >> "$LOG_FILE" 2>&1; then
      # Save checksum for rollback
      local checksum=$(md5sum "$manifest_file" | awk '{print $1}')
      save_deployment_state "manifest_${manifest}_checksum" "$checksum"
      log_info "✓ Applied $manifest"
    else
      log_error "✗ Failed to apply $manifest"
      log_warn "Partial deployment detected. Run rollback: bash deployment/gcp/ROLLBACK-AND-RECOVERY.sh"
      return 1
    fi
  done

  log_info "All manifests deployed"
}

# ============================================================================
# SECTION 5: HEALTH CHECKS WITH RETRIES
# ============================================================================

wait_for_pods_ready() {
  log_section "Waiting for Pods to be Ready"

  local namespace="${NAMESPACE:-agentinvest}"
  local timeout=300
  local start_time=$(date +%s)

  while true; do
    local current_time=$(date +%s)
    local elapsed=$((current_time - start_time))

    if [ $elapsed -gt $timeout ]; then
      log_error "Timeout waiting for pods to be ready (${timeout}s elapsed)"
      log_info "Run: kubectl describe pods -n $namespace"
      log_info "Run: kubectl logs -n $namespace -l app=restate"
      return 1
    fi

    local ready=$(kubectl get pods -n "$namespace" -o jsonpath='{.items[*].status.conditions[?(@.type=="Ready")].status}' 2>/dev/null | grep -c "True" || echo "0")
    local total=$(kubectl get pods -n "$namespace" --no-headers 2>/dev/null | wc -l)

    if [ "$total" -gt 0 ] && [ "$ready" -eq "$total" ]; then
      log_info "✓ All $total pods ready"
      return 0
    fi

    log_info "Pods ready: $ready/$total (waiting...)"
    sleep 10
  done
}

health_check() {
  log_section "Running Health Checks"

  local namespace="${NAMESPACE:-agentinvest}"

  # Check Restate health
  log_info "Checking Restate health..."
  if kubectl exec -n "$namespace" -it deployment/restate -- curl -s http://localhost:9070/health &>/dev/null; then
    log_info "✓ Restate admin API healthy"
  else
    log_warn "⚠ Restate health check inconclusive (may be internal-only)"
  fi

  # Check pod logs for errors
  log_info "Checking pod logs for errors..."
  for app in restate ts-endpoint py-endpoint operator-ui; do
    local error_count=$(kubectl logs -n "$namespace" -l "app=$app" --tail=50 2>/dev/null | grep -i "error\|fail" | wc -l || echo "0")
    if [ "$error_count" -gt 0 ]; then
      log_warn "⚠ Found $error_count error lines in $app logs"
    else
      log_info "✓ No errors in $app logs"
    fi
  done
}

# ============================================================================
# SECTION 6: ROLLBACK PROCEDURES
# ============================================================================

rollback_deployment() {
  log_section "Rolling Back Deployment"

  local namespace="${NAMESPACE:-agentinvest}"
  
  log_warn "Rolling back to previous revision..."

  # Rollback each deployment
  for deployment in restate ts-endpoint py-endpoint operator-ui; do
    if kubectl rollout history deployment/"$deployment" -n "$namespace" &>/dev/null; then
      log_info "Rolling back $deployment..."
      kubectl rollout undo deployment/"$deployment" -n "$namespace" >> "$LOG_FILE" 2>&1
      log_info "✓ Rolled back $deployment"
    fi
  done

  ROLLED_BACK=true
  log_info "Rollback complete"
}

cleanup_failed_deployment() {
  log_section "Cleaning Up Failed Deployment"

  local namespace="${NAMESPACE:-agentinvest}"

  log_warn "Removing failed deployment artifacts..."

  if kubectl get namespace "$namespace" &>/dev/null; then
    log_info "Deleting namespace: $namespace"
    kubectl delete namespace "$namespace" --ignore-not-found >> "$LOG_FILE" 2>&1
    log_info "✓ Namespace deleted"
  fi

  log_info "Cleanup complete"
}

# ============================================================================
# SECTION 7: RECOVERY PROCEDURES
# ============================================================================

check_and_fix_permissions() {
  log_section "Checking and Fixing Permissions"

  local namespace="${NAMESPACE:-agentinvest}"

  log_info "Verifying IAM bindings..."

  # Check service account
  if kubectl get serviceaccount agentinvest-gke -n "$namespace" &>/dev/null; then
    log_info "✓ Service account exists"
  else
    log_error "✗ Service account missing. Create with: kubectl create serviceaccount agentinvest-gke -n $namespace"
    return 1
  fi

  # Check Workload Identity binding
  local gcp_sa="agentinvest-gke-sa@${PROJECT_ID}.iam.gserviceaccount.com"
  if gcloud iam service-accounts get-iam-policy "$gcp_sa" --format='value(bindings[].members)' 2>/dev/null | grep -q "serviceAccount:${PROJECT_ID}.svc.id.goog\[${namespace}/agentinvest-gke\]"; then
    log_info "✓ Workload Identity binding exists"
  else
    log_warn "⚠ Workload Identity binding missing. Create with: gcloud iam service-accounts add-iam-policy-binding $gcp_sa ..."
  fi
}

troubleshoot_common_issues() {
  log_section "Troubleshooting Common Issues"

  local namespace="${NAMESPACE:-agentinvest}"

  # 1. Pod crash loop
  log_info "Checking for crash loops..."
  local crash_count=$(kubectl get pods -n "$namespace" -o jsonpath='{.items[*].status.containerStatuses[*].state.waiting.reason}' | grep -c "CrashLoopBackOff" || echo "0")
  if [ "$crash_count" -gt 0 ]; then
    log_error "✗ Found $crash_count pods in CrashLoopBackOff"
    log_info "Run: kubectl logs -n $namespace <pod-name> --previous"
    return 1
  fi

  # 2. Image pull errors
  log_info "Checking for image pull errors..."
  local pull_errors=$(kubectl get pods -n "$namespace" -o jsonpath='{.items[*].status.containerStatuses[*].state.waiting.reason}' | grep -c "ImagePullBackOff" || echo "0")
  if [ "$pull_errors" -gt 0 ]; then
    log_error "✗ Found $pull_errors pods with image pull errors"
    log_info "Verify images exist: gcloud container images list --repository=gcr.io/$PROJECT_ID"
    return 1
  fi

  # 3. Pending pods (usually resource issues)
  log_info "Checking for pending pods..."
  local pending=$(kubectl get pods -n "$namespace" --field-selector=status.phase=Pending -o name | wc -l)
  if [ "$pending" -gt 0 ]; then
    log_warn "⚠ Found $pending pending pods (cluster may be out of resources)"
    log_info "Run: kubectl describe pods -n $namespace --field-selector=status.phase=Pending"
  fi

  log_info "Troubleshooting check complete"
}

# ============================================================================
# MAIN ORCHESTRATION
# ============================================================================

main() {
  log_section "GKE Deployment with Error Handling"

  log_info "Log file: $LOG_FILE"
  log_info "Deployment state: $DEPLOYMENT_STATE_FILE"

  # Run phases
  if ! preflight_checks; then
    log_error "Pre-flight checks failed. Cannot proceed"
    return 1
  fi

  if ! build_images_safe; then
    log_error "Image build failed. Cleanup: docker rmi gcr.io/$PROJECT_ID/agentinvest-*"
    return 1
  fi

  if ! push_images_safe; then
    log_error "Image push failed. Check network connectivity"
    return 1
  fi

  if ! deploy_to_gke_safe; then
    log_error "Deployment failed. Rolling back..."
    rollback_deployment
    return 1
  fi

  if ! wait_for_pods_ready; then
    log_error "Pods failed to become ready"
    check_and_fix_permissions
    troubleshoot_common_issues
    return 1
  fi

  if ! health_check; then
    log_warn "Health checks failed. Investigate with: kubectl logs -n $NAMESPACE -f"
    return 1
  fi

  log_section "Deployment Successful ✓"
  log_info "All services deployed and healthy"
  log_info "Next: Access operator UI at: kubectl port-forward -n $NAMESPACE svc/operator-ui-service 4180:4180"
}

# Run main
main "$@"
