#!/usr/bin/env bash
# GKE Deployment Rollback and Recovery Script
#
# Use this script to:
# 1. Rollback failed deployments to previous revision
# 2. Clean up partial deployments
# 3. Recover from common failure scenarios
# 4. Restore from backups

set -euo pipefail

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
NAMESPACE="${NAMESPACE:-agentinvest}"
CLUSTER_NAME="${CLUSTER_NAME:-agentinvest-gke}"
REGION="${REGION:-us-central1}"
PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project)}"
LOG_FILE="rollback_$(date +%Y%m%d_%H%M%S).log"

log_info() {
  echo -e "${GREEN}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

log_warn() {
  echo -e "${YELLOW}[WARN]${NC} $1" | tee -a "$LOG_FILE"
}

log_error() {
  echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

log_section() {
  echo "" | tee -a "$LOG_FILE"
  echo -e "${BLUE}======================================${NC}" | tee -a "$LOG_FILE"
  echo -e "${BLUE}$1${NC}" | tee -a "$LOG_FILE"
  echo -e "${BLUE}======================================${NC}" | tee -a "$LOG_FILE"
}

# ============================================================================
# RECOVERY OPTION 1: ROLLBACK TO PREVIOUS REVISION
# ============================================================================

rollback_to_previous() {
  log_section "Rolling Back to Previous Revision"

  # Get credentials
  gcloud container clusters get-credentials "$CLUSTER_NAME" --region="$REGION" >> "$LOG_FILE" 2>&1

  local deployments=("restate" "ts-endpoint" "py-endpoint" "operator-ui")

  for deployment in "${deployments[@]}"; do
    log_info "Rolling back $deployment..."

    # Check if deployment exists
    if ! kubectl get deployment "$deployment" -n "$NAMESPACE" &>/dev/null; then
      log_warn "Deployment $deployment not found"
      continue
    fi

    # Get rollout history
    local revision_count=$(kubectl rollout history deployment/"$deployment" -n "$NAMESPACE" 2>/dev/null | wc -l || echo "1")
    
    if [ "$revision_count" -le 2 ]; then
      log_warn "Only one revision exists for $deployment. Cannot rollback"
      continue
    fi

    # Perform rollback
    if kubectl rollout undo deployment/"$deployment" -n "$NAMESPACE" >> "$LOG_FILE" 2>&1; then
      log_info "✓ Rolled back $deployment"
      
      # Wait for rollback to complete
      if kubectl rollout status deployment/"$deployment" -n "$NAMESPACE" --timeout=300s >> "$LOG_FILE" 2>&1; then
        log_info "✓ $deployment rollback complete and ready"
      else
        log_warn "⚠ $deployment rollback may not be complete. Check status"
      fi
    else
      log_error "✗ Failed to rollback $deployment"
    fi
  done

  log_info "Rollback complete"
}

# ============================================================================
# RECOVERY OPTION 2: ROLLBACK TO SPECIFIC REVISION
# ============================================================================

rollback_to_revision() {
  local deployment=$1
  local revision=$2

  log_section "Rolling Back $deployment to Revision $revision"

  gcloud container clusters get-credentials "$CLUSTER_NAME" --region="$REGION" >> "$LOG_FILE" 2>&1

  if kubectl rollout undo deployment/"$deployment" -n "$NAMESPACE" --to-revision="$revision" >> "$LOG_FILE" 2>&1; then
    log_info "✓ Rolled back $deployment to revision $revision"
    
    if kubectl rollout status deployment/"$deployment" -n "$NAMESPACE" --timeout=300s >> "$LOG_FILE" 2>&1; then
      log_info "✓ Rollback complete and ready"
    fi
  else
    log_error "✗ Failed to rollback to revision $revision"
    return 1
  fi
}

# ============================================================================
# RECOVERY OPTION 3: CLEAN UP FAILED DEPLOYMENT
# ============================================================================

cleanup_failed_deployment() {
  log_section "Cleaning Up Failed Deployment"

  gcloud container clusters get-credentials "$CLUSTER_NAME" --region="$REGION" >> "$LOG_FILE" 2>&1

  # Delete namespace (will cascade delete all resources)
  if kubectl get namespace "$NAMESPACE" &>/dev/null; then
    log_warn "Deleting namespace: $NAMESPACE"
    log_warn "This will delete all resources in the namespace"
    
    read -p "Are you sure? (yes/no): " confirm
    if [ "$confirm" = "yes" ]; then
      kubectl delete namespace "$NAMESPACE" >> "$LOG_FILE" 2>&1
      
      # Wait for deletion
      local timeout=120
      local start=$(date +%s)
      while kubectl get namespace "$NAMESPACE" &>/dev/null; do
        local elapsed=$(($(date +%s) - start))
        if [ $elapsed -gt $timeout ]; then
          log_error "Timeout waiting for namespace deletion"
          return 1
        fi
        sleep 5
      done
      
      log_info "✓ Namespace deleted"
    else
      log_warn "Cleanup cancelled"
    fi
  else
    log_warn "Namespace $NAMESPACE not found"
  fi
}

# ============================================================================
# RECOVERY OPTION 4: DELETE FAILED PODS
# ============================================================================

delete_failed_pods() {
  log_section "Deleting Failed Pods"

  gcloud container clusters get-credentials "$CLUSTER_NAME" --region="$REGION" >> "$LOG_FILE" 2>&1

  # Find pods in failed states
  local failed_pods=$(kubectl get pods -n "$NAMESPACE" \
    --field-selector=status.phase!=Running,status.phase!=Succeeded \
    -o jsonpath='{.items[*].metadata.name}' 2>/dev/null || echo "")

  if [ -z "$failed_pods" ]; then
    log_info "No failed pods found"
    return 0
  fi

  log_warn "Found failed pods: $failed_pods"
  for pod in $failed_pods; do
    log_info "Deleting pod: $pod"
    kubectl delete pod "$pod" -n "$NAMESPACE" --grace-period=30 >> "$LOG_FILE" 2>&1
  done

  log_info "Failed pods deleted. Kubernetes will recreate them"
}

# ============================================================================
# RECOVERY OPTION 5: RESTART DEPLOYMENT
# ============================================================================

restart_deployment() {
  local deployment=$1

  log_section "Restarting Deployment: $deployment"

  gcloud container clusters get-credentials "$CLUSTER_NAME" --region="$REGION" >> "$LOG_FILE" 2>&1

  if ! kubectl get deployment "$deployment" -n "$NAMESPACE" &>/dev/null; then
    log_error "Deployment $deployment not found"
    return 1
  fi

  log_info "Rolling restart of $deployment..."
  kubectl rollout restart deployment/"$deployment" -n "$NAMESPACE" >> "$LOG_FILE" 2>&1

  if kubectl rollout status deployment/"$deployment" -n "$NAMESPACE" --timeout=300s >> "$LOG_FILE" 2>&1; then
    log_info "✓ $deployment restarted successfully"
  else
    log_error "✗ Restart did not complete in time"
    return 1
  fi
}

# ============================================================================
# RECOVERY OPTION 6: RESTORE CLOUD SQL FROM BACKUP
# ============================================================================

restore_cloud_sql_from_backup() {
  log_section "Restoring Cloud SQL from Backup"

  local instance="${CLOUD_SQL_INSTANCE:-agentinvest-sql}"
  local database=${1:-canonical_db}
  
  log_info "Available backups for instance: $instance"
  gcloud sql backups list --instance="$instance" --limit=10

  read -p "Enter backup ID to restore from (or PITR timestamp): " backup_id

  if [[ "$backup_id" == *"T"* ]]; then
    # PITR restore
    log_warn "Restoring to point-in-time: $backup_id"
    log_warn "Note: This requires manual Cloud SQL operations"
    log_info "See: https://cloud.google.com/sql/docs/postgres/point-in-time-recovery"
  else
    # Backup restore
    log_info "Restoring backup: $backup_id"
    
    if gcloud sql backups restore "$backup_id" \
      --backup-instance="$instance" \
      --backup-configuration="backup-config" \
      >> "$LOG_FILE" 2>&1; then
      log_info "✓ Backup restore initiated"
      log_info "Monitor progress: gcloud sql operations list --instance=$instance"
    else
      log_error "✗ Backup restore failed"
      return 1
    fi
  fi
}

# ============================================================================
# RECOVERY OPTION 7: EXAMINE LOGS AND DIAGNOSTICS
# ============================================================================

examine_logs() {
  log_section "Examining Logs and Diagnostics"

  gcloud container clusters get-credentials "$CLUSTER_NAME" --region="$REGION" >> "$LOG_FILE" 2>&1

  # Pod status
  log_info "Pod Status:"
  kubectl get pods -n "$NAMESPACE" -o wide >> "$LOG_FILE" 2>&1

  # Deployment status
  log_info "Deployment Status:"
  kubectl get deployments -n "$NAMESPACE" -o wide >> "$LOG_FILE" 2>&1

  # Events
  log_info "Recent Events:"
  kubectl get events -n "$NAMESPACE" --sort-by='.lastTimestamp' | tail -20 >> "$LOG_FILE" 2>&1

  # Pod logs (last 50 lines from each failed pod)
  local failed_pods=$(kubectl get pods -n "$NAMESPACE" \
    --field-selector=status.phase!=Running,status.phase!=Succeeded \
    -o jsonpath='{.items[*].metadata.name}' 2>/dev/null || echo "")

  if [ -n "$failed_pods" ]; then
    log_info "Logs from Failed Pods:"
    for pod in $failed_pods; do
      log_info "=== Logs from $pod ==="
      kubectl logs "$pod" -n "$NAMESPACE" --tail=50 >> "$LOG_FILE" 2>&1 || true
    done
  fi

  # Node status
  log_info "Node Status:"
  kubectl get nodes -o wide >> "$LOG_FILE" 2>&1

  # Cloud SQL status
  if [ -n "${CLOUD_SQL_INSTANCE:-}" ]; then
    log_info "Cloud SQL Instance Status:"
    gcloud sql instances describe "${CLOUD_SQL_INSTANCE}" --format=json >> "$LOG_FILE" 2>&1
  fi

  log_info "Diagnostic info written to: $LOG_FILE"
}

# ============================================================================
# RECOVERY OPTION 8: SCALE DOWN TO DIAGNOSE
# ============================================================================

scale_down_for_diagnosis() {
  log_section "Scaling Down Deployments for Diagnosis"

  gcloud container clusters get-credentials "$CLUSTER_NAME" --region="$REGION" >> "$LOG_FILE" 2>&1

  for deployment in restate ts-endpoint py-endpoint operator-ui; do
    log_info "Scaling $deployment to 0 replicas..."
    kubectl scale deployment "$deployment" -n "$NAMESPACE" --replicas=0 >> "$LOG_FILE" 2>&1
  done

  log_info "✓ All deployments scaled to 0"
  log_info "Now investigate the root cause, then scale back up:"
  log_info "  kubectl scale deployment <name> -n $NAMESPACE --replicas=<count>"
}

# ============================================================================
# RECOVERY OPTION 9: REAPPLY MANIFESTS
# ============================================================================

reapply_manifests() {
  log_section "Reapplying Kubernetes Manifests"

  gcloud container clusters get-credentials "$CLUSTER_NAME" --region="$REGION" >> "$LOG_FILE" 2>&1

  # Create namespace if missing
  kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f - >> "$LOG_FILE" 2>&1

  # Apply all manifests
  local manifests=("namespace" "service-account" "restate-deployment" "ts-endpoint-deployment" "py-endpoint-deployment" "operator-ui-deployment" "hpa" "network-policy")

  for manifest in "${manifests[@]}"; do
    local manifest_file="deployment/gcp/kubernetes/${manifest}.yaml"
    
    if [ -f "$manifest_file" ]; then
      log_info "Applying $manifest..."
      if kubectl apply -f "$manifest_file" -n "$NAMESPACE" >> "$LOG_FILE" 2>&1; then
        log_info "✓ Applied $manifest"
      else
        log_warn "⚠ Failed to apply $manifest (may have conflicts)"
      fi
    else
      log_warn "Manifest not found: $manifest_file"
    fi
  done

  log_info "Manifests reapplied. Check pod status: kubectl get pods -n $NAMESPACE"
}

# ============================================================================
# RECOVERY OPTION 10: FULL NUCLEAR OPTION (DELETE AND REDEPLOY)
# ============================================================================

full_redeploy() {
  log_section "FULL REDEPLOYMENT (Nuclear Option)"

  log_error "This will DELETE the entire namespace and redeploy from scratch"
  
  read -p "ARE YOU SURE? This cannot be undone. Type 'yes, delete everything': " confirm
  if [ "$confirm" != "yes, delete everything" ]; then
    log_info "Cancelled"
    return 0
  fi

  # Backup data from Cloud SQL first
  log_warn "Backing up Cloud SQL before deletion..."
  if [ -n "${CLOUD_SQL_INSTANCE:-}" ]; then
    gcloud sql export sql "${CLOUD_SQL_INSTANCE}" \
      "gs://agentinvest-backups/pre-redeploy-backup-$(date +%Y%m%d_%H%M%S).sql" \
      --database=canonical_db \
      >> "$LOG_FILE" 2>&1 || log_warn "Cloud SQL backup failed"
  fi

  # Delete namespace
  gcloud container clusters get-credentials "$CLUSTER_NAME" --region="$REGION" >> "$LOG_FILE" 2>&1
  
  log_warn "Deleting namespace..."
  kubectl delete namespace "$NAMESPACE" --ignore-not-found >> "$LOG_FILE" 2>&1

  # Wait for deletion
  sleep 30

  # Redeploy
  log_info "Redeploying from scratch..."
  reapply_manifests

  log_info "Redeployment complete. Verify with: kubectl get pods -n $NAMESPACE"
}

# ============================================================================
# MAIN MENU
# ============================================================================

show_menu() {
  cat << EOF

${BLUE}GKE Deployment Rollback & Recovery Menu${NC}

1) Rollback to previous revision
2) Rollback to specific revision
3) Delete failed pods
4) Restart deployment
5) Examine logs and diagnostics
6) Scale down for diagnosis
7) Reapply Kubernetes manifests
8) Restore Cloud SQL from backup
9) Clean up entire namespace
10) FULL REDEPLOYMENT (nuclear option)
0) Exit

Choose an option:
EOF
}

main() {
  log_section "GKE Rollback & Recovery"
  log_info "Log file: $LOG_FILE"

  # If argument provided, run specific action
  if [ $# -gt 0 ]; then
    case "$1" in
      rollback)
        rollback_to_previous
        ;;
      restart)
        restart_deployment "${2:-restate}"
        ;;
      logs)
        examine_logs
        ;;
      cleanup)
        cleanup_failed_deployment
        ;;
      redeploy)
        full_redeploy
        ;;
      *)
        log_error "Unknown option: $1"
        exit 1
        ;;
    esac
  else
    # Interactive menu
    while true; do
      show_menu
      read -p "" choice
      
      case "$choice" in
        1) rollback_to_previous ;;
        2) 
          read -p "Enter deployment name: " dep
          read -p "Enter revision number: " rev
          rollback_to_revision "$dep" "$rev"
          ;;
        3) delete_failed_pods ;;
        4)
          read -p "Enter deployment name (restate/ts-endpoint/py-endpoint/operator-ui): " dep
          restart_deployment "$dep"
          ;;
        5) examine_logs ;;
        6) scale_down_for_diagnosis ;;
        7) reapply_manifests ;;
        8) restore_cloud_sql_from_backup ;;
        9) cleanup_failed_deployment ;;
        10) full_redeploy ;;
        0) log_info "Exiting"; exit 0 ;;
        *) log_error "Invalid choice" ;;
      esac
      
      echo ""
      read -p "Press enter to continue..."
    done
  fi
}

main "$@"
