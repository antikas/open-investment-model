# GKE Deployment Error Handling and Recovery Guide

Complete operational procedures for handling deployment failures, rollbacks, and disaster recovery.

---

## Quick Reference: Common Failure Scenarios

| Scenario | Symptom | Fix |
|----------|---------|-----|
| **Docker build fails** | `docker build` error | Check Dockerfile syntax, internet connection |
| **Image push fails** | `docker push` times out | Check Docker daemon, network connectivity |
| **GKE cluster unreachable** | `kubectl` commands fail | Run `gcloud container clusters get-credentials ...` |
| **Pod crashes immediately** | CrashLoopBackOff | Check logs: `kubectl logs <pod> --previous` |
| **Pod stuck pending** | No errors, pod not starting | Cluster may be out of resources; check quota |
| **Cloud SQL connection fails** | Python endpoint logs show connection error | Verify Private Service Connection, Cloud SQL private IP |
| **Restate handler registration fails** | Handlers not visible in admin API | Check TS/Python endpoints can reach Restate |
| **Deployment times out** | Takes >10 minutes to complete | Scale down and diagnose: see SCALE_DOWN procedure |

---

## Pre-Flight Checks (Run Before Deployment)

Script: `deployment/gcp/DEPLOYMENT-WITH-ERROR-HANDLING.sh` (included)

**Automated checks**:
```bash
bash deployment/gcp/DEPLOYMENT-WITH-ERROR-HANDLING.sh preflight
```

**Manual checks**:
```sh
# 1. Authentication
gcloud auth list --filter=status:ACTIVE

# 2. Project and APIs
gcloud config get-value project
gcloud services list --enabled | grep -E 'container|sqladmin|run|artifactregistry'

# 3. Required tools
docker --version && kubectl version --client && gcloud --version

# 4. Docker daemon
docker ps

# 5. Disk space for Docker builds
df /var/lib/docker  # Need >10GB

# 6. GKE cluster exists
gcloud container clusters list --region=us-central1

# 7. Cloud SQL instance exists
gcloud sql instances list

# 8. Container Registry/Artifact Registry
gcloud container images list --repository=gcr.io/$PROJECT_ID
```

**Abort deployment if any check fails.**

---

## Deployment with Error Handling

**Use the safe deployment script**:
```bash
bash deployment/gcp/DEPLOYMENT-WITH-ERROR-HANDLING.sh
```

This script includes:
- ✅ Pre-flight checks (prevents wasted effort on known issues)
- ✅ State tracking (knows what succeeded, what failed)
- ✅ Build error handling (logs all docker build output)
- ✅ Push error handling (retries on network failures)
- ✅ Deployment error handling (partial failures detected)
- ✅ Health checks (waits for pods to be ready)
- ✅ Automatic rollback on critical failures
- ✅ Logging to file (full audit trail)

**Output**:
- Log file: `deployment_YYYYMMDD_HHMMSS.log`
- State file: `deployment_state.json` (tracks progress)

---

## Phase 1: Image Build Failures

### Symptom: `docker build` fails

**Check logs**:
```bash
tail deployment_*.log | grep -i "error\|failed"
```

**Common causes and fixes**:

1. **Network error (e.g., downloading Restate binary)**
   ```
   Error: Failed to download v1.6.2/restate-server-x86_64-unknown-linux-musl.tar.xz
   ```
   **Fix**: 
   ```bash
   # Check internet connection
   curl -I https://github.com/restatedev/restate/releases/download/v1.6.2/restate-server-x86_64-unknown-linux-musl.tar.xz
   
   # Retry build
   docker build -t gcr.io/$PROJECT_ID/agentinvest-restate:latest -f deployment/gcp/Dockerfile.restate .
   ```

2. **Missing source file**
   ```
   Error: COPY reference/config/restate-dev.toml: not found
   ```
   **Fix**:
   ```bash
   # Verify file exists
   ls -la reference/config/restate-dev.toml
   
   # Build from correct directory
   cd /home/admin_user/open-investment-model
   docker build -t gcr.io/$PROJECT_ID/agentinvest-restate:latest -f deployment/gcp/Dockerfile.restate .
   ```

3. **Disk space exhausted**
   ```
   Error: no space left on device
   ```
   **Fix**:
   ```bash
   # Clean up old images
   docker system prune -a --volumes
   
   # Check disk space
   df /var/lib/docker
   
   # If still low, clean up logs
   docker logs $(docker ps -a -q) | wc -l  # Can be large
   ```

4. **Package installation fails (Python/Node.js)**
   ```
   Error: No matching distribution found for package_name
   ```
   **Fix**:
   ```bash
   # Check if package exists
   pip index versions package_name
   npm view package_name versions
   
   # Update lock files
   cd reference/python && pip install -U pip && uv sync
   cd reference/ts && npm install
   ```

**Recovery**:
```bash
# Retry build
docker build -t gcr.io/$PROJECT_ID/agentinvest-<name>:latest -f deployment/gcp/Dockerfile.<name> .

# If still fails, abort and fix Dockerfile before retrying full deployment
```

---

## Phase 2: Image Push Failures

### Symptom: `docker push` fails or times out

**Check logs**:
```bash
docker push gcr.io/$PROJECT_ID/agentinvest-restate:latest 2>&1 | head -30
```

**Common causes and fixes**:

1. **Network connectivity issues**
   ```
   Error: failed to dial unixsocket /var/run/docker.sock
   ```
   **Fix**:
   ```bash
   # Restart Docker
   sudo systemctl restart docker
   
   # Verify daemon
   docker ps
   ```

2. **Push timeout (large image)**
   ```
   Error: context deadline exceeded
   ```
   **Fix**:
   ```bash
   # Retry push
   docker push gcr.io/$PROJECT_ID/agentinvest-<name>:latest
   
   # If persistent, compress image layers
   docker build --compress -t gcr.io/$PROJECT_ID/agentinvest-<name>:latest .
   ```

3. **Not authenticated to registry**
   ```
   Error: denied: Unauthenticated
   ```
   **Fix**:
   ```bash
   # Re-authenticate
   gcloud auth configure-docker
   gcloud auth configure-docker us.gcr.io,eu.gcr.io
   
   # Retry push
   docker push gcr.io/$PROJECT_ID/agentinvest-<name>:latest
   ```

**Recovery**:
```bash
# Retry push (usually succeeds on retry)
docker push gcr.io/$PROJECT_ID/agentinvest-<name>:latest

# Verify image was pushed
gcloud container images list --repository=gcr.io/$PROJECT_ID
```

---

## Phase 3: GKE Deployment Failures

### Symptom: `kubectl apply` fails or times out

**Check logs**:
```bash
tail deployment_*.log | grep -A5 "Deploying\|Failed\|Error"
```

**Common causes and fixes**:

1. **Cannot connect to cluster**
   ```
   Error: Unable to connect to the server
   ```
   **Fix**:
   ```bash
   # Get cluster credentials
   gcloud container clusters get-credentials $CLUSTER_NAME --region=$REGION
   
   # Verify connection
   kubectl cluster-info
   ```

2. **Namespace creation fails**
   ```
   Error: namespaces "agentinvest" already exists
   ```
   **Fix**:
   ```bash
   # Namespace already exists (harmless); continue deployment
   # Or, if cleaning up:
   kubectl delete namespace agentinvest
   ```

3. **RBAC/permissions issues**
   ```
   Error: failed to create Workload Identity binding
   ```
   **Fix**:
   ```bash
   # Verify service account exists
   gcloud iam service-accounts list | grep agentinvest-gke-sa
   
   # Add IAM binding
   gcloud iam service-accounts add-iam-policy-binding \
     agentinvest-gke-sa@${PROJECT_ID}.iam.gserviceaccount.com \
     --role=roles/iam.workloadIdentityUser \
     --member="serviceAccount:${PROJECT_ID}.svc.id.goog[agentinvest/agentinvest-gke]"
   ```

4. **Secret creation fails**
   ```
   Error: secret "cloudsql-credentials" already exists
   ```
   **Fix**:
   ```bash
   # Delete old secret
   kubectl delete secret cloudsql-credentials -n agentinvest
   
   # Recreate
   kubectl create secret generic cloudsql-credentials \
     --from-literal=username=agentinvest \
     --from-literal=password="$PASSWORD" \
     -n agentinvest
   ```

**Recovery**:
```bash
# Reapply manifests
kubectl apply -f deployment/gcp/kubernetes/*.yaml -n agentinvest

# Or use rollback script
bash deployment/gcp/ROLLBACK-AND-RECOVERY.sh reapply
```

---

## Phase 4: Pod Startup Failures

### Symptom: Pods stuck in `CrashLoopBackOff` or `Pending`

**Check status**:
```bash
kubectl get pods -n agentinvest -o wide
kubectl describe pod <pod-name> -n agentinvest
```

**Common causes and fixes**:

1. **Image pull errors**
   ```
   Status: ImagePullBackOff
   Error: Failed to pull image "gcr.io/PROJECT_ID/agentinvest-restate:latest": rpc error: code = Unknown desc = Error response from daemon: unknown
   ```
   **Fix**:
   ```bash
   # Verify image exists
   gcloud container images list-tags gcr.io/$PROJECT_ID/agentinvest-restate
   
   # If missing, rebuild and push
   docker build -t gcr.io/$PROJECT_ID/agentinvest-restate:latest -f deployment/gcp/Dockerfile.restate .
   docker push gcr.io/$PROJECT_ID/agentinvest-restate:latest
   
   # Restart pod
   kubectl delete pod <pod-name> -n agentinvest
   ```

2. **Container crashes on startup**
   ```
   Status: CrashLoopBackOff
   ```
   **Check logs**:
   ```bash
   kubectl logs <pod-name> -n agentinvest
   kubectl logs <pod-name> -n agentinvest --previous  # Previous crash
   ```
   **Common startup errors**:
   - Missing environment variable: `echo "RESTATE_PORT not set"` → Add to deployment manifest
   - Cloud SQL connection failed → Check Private Service Connection, firewall rules
   - Anthropic API key invalid → Verify secret in Secret Manager
   - Restate registration failed → Check TS/Python endpoints can reach Restate

3. **Pod stuck in Pending**
   ```
   Status: Pending
   ```
   **Diagnose**:
   ```bash
   kubectl describe pod <pod-name> -n agentinvest
   # Look for: "Insufficient cpu/memory", "node selector mismatch"
   ```
   **Fix options**:
   ```bash
   # Option 1: Scale down other pods to free resources
   kubectl scale deployment ts-endpoint -n agentinvest --replicas=0
   
   # Option 2: Add more nodes to cluster
   gcloud container node-pools create additional-pool \
     --cluster=$CLUSTER_NAME \
     --region=$REGION \
     --machine-type=e2-standard-2 \
     --num-nodes=2
   
   # Option 3: Reduce pod resource requests
   kubectl set resources deployment restate \
     -n agentinvest \
     --requests=cpu=1,memory=1Gi
   ```

**Recovery**:
```bash
# Delete failed pod (Kubernetes will recreate it)
kubectl delete pod <pod-name> -n agentinvest

# Or, restart entire deployment
kubectl rollout restart deployment/restate -n agentinvest

# Or, use rollback script
bash deployment/gcp/ROLLBACK-AND-RECOVERY.sh restart restate
```

---

## Phase 5: Runtime Failures (Pods running but service fails)

### Symptom: Pods are running but application errors occur

**Check pod logs**:
```bash
# Real-time logs
kubectl logs -n agentinvest -f -l app=restate

# Logs from specific pod
kubectl logs <pod-name> -n agentinvest --tail=100

# Previous crash logs
kubectl logs <pod-name> -n agentinvest --previous
```

**Common causes and fixes**:

1. **Cloud SQL connection error**
   ```
   Error: psycopg2.OperationalError: could not translate host name "PRIVATE_IP" to address
   ```
   **Fix**:
   ```bash
   # Verify Private Service Connection
   gcloud sql instances describe $CLOUD_SQL_INSTANCE --format='value(ipAddresses[0].ipAddress)'
   
   # Test connectivity from pod
   kubectl run -it --rm debug \
     --image=google/cloud-sql-proxy:latest \
     --serviceaccount=agentinvest-gke \
     -n agentinvest -- \
     psql "postgresql://agentinvest:PASSWORD@PRIVATE_IP:5432/canonical_db"
   
   # If fails, check firewall rules
   gcloud compute firewall-rules list --filter="name~agentinvest"
   ```

2. **Restate endpoint registration fails**
   ```
   Error: [REGISTER_SERVICE] Failed to reach Restate at http://restate-service:8080
   ```
   **Fix**:
   ```bash
   # Verify Restate is running
   kubectl get pod -n agentinvest -l app=restate
   
   # Test DNS from TS endpoint pod
   kubectl exec -it <ts-endpoint-pod> -n agentinvest -- nslookup restate-service
   
   # Check NetworkPolicy allows traffic
   kubectl get networkpolicy -n agentinvest
   
   # If blocked, fix NetworkPolicy
   kubectl apply -f deployment/gcp/kubernetes/network-policy.yaml
   ```

3. **Out of memory**
   ```
   Error: OOMKilled
   Reason: OutOfMemory
   ```
   **Fix**:
   ```bash
   # Increase memory limit
   kubectl set resources deployment py-endpoint \
     -n agentinvest \
     --limits=memory=3Gi
   
   # Restart pod
   kubectl delete pod <pod-name> -n agentinvest
   ```

**Recovery**:
```bash
# Restart affected pod
kubectl delete pod <pod-name> -n agentinvest

# Or, restart entire deployment
kubectl rollout restart deployment/<name> -n agentinvest

# Or, check logs for more details
kubectl logs <pod-name> -n agentinvest | grep -i error
```

---

## Rollback Procedures

### Option 1: Automatic Rollback (if deployment used safe script)

The `DEPLOYMENT-WITH-ERROR-HANDLING.sh` script automatically rolls back on critical failures:
```bash
# Done automatically on failure, but can be manual:
bash deployment/gcp/ROLLBACK-AND-RECOVERY.sh rollback
```

### Option 2: Rollback to Previous Revision

```bash
# Rollback all deployments
bash deployment/gcp/ROLLBACK-AND-RECOVERY.sh rollback

# Or specific deployment
bash deployment/gcp/ROLLBACK-AND-RECOVERY.sh restart restate
```

### Option 3: Rollback to Specific Revision

```bash
# List revisions
kubectl rollout history deployment/restate -n agentinvest

# Rollback to revision N
bash deployment/gcp/ROLLBACK-AND-RECOVERY.sh
# Choose option 2, enter deployment name and revision
```

### Option 4: Full Cleanup and Redeploy

```bash
# DELETE EVERYTHING and start fresh
bash deployment/gcp/ROLLBACK-AND-RECOVERY.sh
# Choose option 10 (nuclear option)

# Or manually
kubectl delete namespace agentinvest
bash deployment/gcp/DEPLOYMENT-WITH-ERROR-HANDLING.sh
```

---

## Cloud SQL Recovery

### Restore from Backup

```bash
# List backups
gcloud sql backups list --instance=$CLOUD_SQL_INSTANCE

# Restore specific backup
gcloud sql backups restore BACKUP_ID \
  --backup-instance=$CLOUD_SQL_INSTANCE

# Point-in-time recovery
gcloud sql backups restore LATEST_BACKUP \
  --backup-instance=$CLOUD_SQL_INSTANCE \
  --point-in-time="2026-06-16T10:30:00Z"
```

### Restore from GCS Export

```bash
# List exports
gsutil ls gs://agentinvest-backups/

# Import into new database
gcloud sql import sql $CLOUD_SQL_INSTANCE \
  gs://agentinvest-backups/canonical_db_20260616.sql \
  --database=canonical_db
```

---

## Diagnostics and Troubleshooting

### Comprehensive Diagnostics

```bash
# Run all diagnostics
bash deployment/gcp/ROLLBACK-AND-RECOVERY.sh logs

# Or manually
kubectl get pods -n agentinvest -o wide
kubectl get events -n agentinvest --sort-by='.lastTimestamp'
kubectl describe node  # Check node resources
gcloud sql instances describe $CLOUD_SQL_INSTANCE
```

### Scale Down for Diagnosis

If a pod keeps crashing and you need to investigate:

```bash
# Scale down all pods
bash deployment/gcp/ROLLBACK-AND-RECOVERY.sh
# Choose option 6

# SSH into a pod to debug
kubectl exec -it <pod-name> -n agentinvest -- /bin/bash

# Once fixed, scale back up
kubectl scale deployment restate -n agentinvest --replicas=1
```

---

## Prevention: Best Practices

1. **Always run pre-flight checks before deployment**
   ```bash
   bash deployment/gcp/DEPLOYMENT-WITH-ERROR-HANDLING.sh
   ```

2. **Use safe deployment script instead of manual commands**
   ```bash
   # ✅ Good
   bash deployment/gcp/DEPLOYMENT-WITH-ERROR-HANDLING.sh
   
   # ❌ Risky
   kubectl apply -f deployment/gcp/kubernetes/*.yaml
   ```

3. **Test locally first**
   ```bash
   # Test Docker builds locally before pushing
   docker build -t agentinvest-restate -f deployment/gcp/Dockerfile.restate .
   ```

4. **Use state files to track progress**
   ```bash
   # Check what succeeded/failed
   cat deployment_state.json
   ```

5. **Monitor after deployment**
   ```bash
   # Watch pod status
   kubectl get pods -n agentinvest -w
   
   # Stream logs
   kubectl logs -n agentinvest -f -l "app in (restate,ts-endpoint,py-endpoint)"
   ```

6. **Keep backups and test restore**
   ```bash
   # Regular backups
   gcloud sql export sql $CLOUD_SQL_INSTANCE \
     gs://agentinvest-backups/backup_$(date +%Y%m%d).sql \
     --database=canonical_db
   
   # Test restore (monthly)
   gcloud sql import sql $CLOUD_SQL_INSTANCE \
     gs://agentinvest-backups/backup_20260615.sql \
     --database=test_canonical_db
   ```

---

## Support and Escalation

If the above procedures don't resolve the issue:

1. **Collect all diagnostics**
   ```bash
   bash deployment/gcp/ROLLBACK-AND-RECOVERY.sh logs
   # This generates comprehensive diagnostic output
   ```

2. **Check GCP support documentation**
   - [GKE troubleshooting](https://cloud.google.com/kubernetes-engine/docs/troubleshooting)
   - [Cloud SQL troubleshooting](https://cloud.google.com/sql/docs/postgres/troubleshoot)

3. **Contact GCP support** with:
   - Deployment log file (`deployment_*.log`)
   - Diagnostic output (`rollback_*.log`)
   - Pod describe output (`kubectl describe pod <name> -n agentinvest`)
   - Cluster/instance info (`gcloud container clusters describe ...`)

---

## Reference: Script Usage

| Script | Purpose | Usage |
|--------|---------|-------|
| `DEPLOYMENT-WITH-ERROR-HANDLING.sh` | Safe deployment with checks | `bash deployment/gcp/DEPLOYMENT-WITH-ERROR-HANDLING.sh` |
| `ROLLBACK-AND-RECOVERY.sh` | Rollback and recovery | `bash deployment/gcp/ROLLBACK-AND-RECOVERY.sh` (interactive) |
| `GKE-DEPLOYMENT-RUNBOOK.md` | Manual step-by-step | Reference for manual operations |

---

## Change Log

- **2026-06-16**: Created error handling framework with safe deployment script and recovery procedures
