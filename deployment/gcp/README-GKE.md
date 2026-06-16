# GCP Deployment for agentINVEST — GKE + Cloud SQL

**Status**: Updated 2026-06-16 — GKE and Cloud SQL APIs now enabled. 

**Deployment Strategy**: Google Kubernetes Engine (GKE) + Cloud SQL Postgres backend provides enterprise-grade durability, automatic backups, point-in-time recovery, and operational simplicity.

---

## Quick Summary

| Component | Technology |
|-----------|-----------|
| **Orchestration** | GKE (Google Kubernetes Engine) |
| **Restate state store** | Cloud SQL Postgres (durable backend) |
| **Canonical data layer** | Cloud SQL Postgres (replaces local DuckDB) |
| **Secrets** | Cloud Secret Manager |
| **Container images** | Artifact Registry / GCR |
| **Egress** | Cloud NAT gateway |
| **Monitoring** | Cloud Logging + Cloud Monitoring |

---

## Deployment Artifacts

```
deployment/gcp/
├── README.md (this file)
├── ARCHITECTURE-COMPARISON.md          # Cloud Run vs. GKE comparison
├── GKE-DEPLOYMENT-RUNBOOK.md           # Step-by-step GKE deployment
├── CLOUD-SQL-PERSISTENCE-GUIDE.md      # Cloud SQL setup and migration
├── Dockerfile.restate                  # Fixed to download Restate v1.6.2
├── Dockerfile.ts-endpoint
├── Dockerfile.py-endpoint
├── Dockerfile.operator-ui
├── Dockerfile.mcp
├── build-images.sh                     # Build all images
├── kubernetes/                         # Kubernetes manifests
│   ├── generate-manifests.sh          # Generate manifests
│   ├── namespace.yaml
│   ├── service-account.yaml
│   ├── restate-deployment.yaml
│   ├── ts-endpoint-deployment.yaml
│   ├── py-endpoint-deployment.yaml
│   ├── operator-ui-deployment.yaml
│   ├── hpa.yaml                        # Horizontal Pod Autoscaler
│   ├── network-policy.yaml
│   └── smoke-test.sh
├── cloudrun/                           # [LEGACY] Cloud Run path (deprecated)
└── secret-manager/                     # Secret management guidance
```

---

## Deployment Phases

### Phase 1: Prerequisites & API Setup

1. **Verify APIs are enabled**:
   ```sh
   gcloud services list --enabled | grep -E '(container|sqladmin|run)'
   ```
   - ✅ `container.googleapis.com` (GKE)
   - ✅ `sqladmin.googleapis.com` (Cloud SQL)
   - ✅ `run.googleapis.com` (Cloud Run, optional)
   - ✅ `artifactregistry.googleapis.com` or `containerregistry.googleapis.com`

2. **Set environment variables**:
   ```sh
   export PROJECT_ID="$(gcloud config get-value project)"
   export REGION="us-central1"
   export CLUSTER_NAME="agentinvest-gke"
   export CLOUD_SQL_INSTANCE="agentinvest-sql"
   export IMAGE_TAG="latest"
   ```

### Phase 2: Infrastructure Setup

Follow **[GKE-DEPLOYMENT-RUNBOOK.md](GKE-DEPLOYMENT-RUNBOOK.md)** step-by-step:

1. Create GKE cluster (Step 2)
2. Create Cloud SQL instance (Step 3)
3. Configure Private Service Connection (Step 5)
4. Set up Workload Identity (Steps 6–7)
5. Create secrets (Step 9)

### Phase 3: Build & Deploy

1. **Build container images**:
   ```sh
   cd /home/admin_user/open-investment-model
   ./deployment/gcp/build-images.sh
   ```

2. **Deploy to GKE**:
   ```sh
   bash deployment/gcp/kubernetes/generate-manifests.sh
   kubectl apply -f deployment/gcp/kubernetes/*.yaml
   ```

3. **Verify deployment**:
   ```sh
   kubectl wait --for=condition=Ready pod -l app=restate -n agentinvest --timeout=300s
   kubectl get pods -n agentinvest
   ```

### Phase 4: Verify & Test

Run smoke tests:
```sh
bash deployment/gcp/kubernetes/smoke-test.sh
```

---

## Data Persistence

### Restate State Durability

Restate is configured with a **Cloud SQL Postgres backend**. All workflow execution logs, state, and completion journal are persisted in the `restate_state` database.

✅ **Automatic**: No additional setup required beyond Cloud SQL instance creation.  
✅ **Durable**: Data survives pod restarts, cluster upgrades, and node failures.  
✅ **Recoverable**: Automatic daily backups + point-in-time recovery up to 7 days.

### Canonical Data Layer

Local DuckDB files are **replaced** with Cloud SQL Postgres.

**Migration**:
1. Export current DuckDB schema
2. Create equivalent Postgres tables in `canonical_db`
3. Migrate seed data
4. Update dbt `profiles.yml` to use Postgres (PROD profile)
5. Update Python endpoint to read/write Postgres

See **[CLOUD-SQL-PERSISTENCE-GUIDE.md](CLOUD-SQL-PERSISTENCE-GUIDE.md)** for detailed migration steps.

### Backup & Recovery

**Automatic**:
- Cloud SQL daily backups (30-day retention)
- Point-in-time recovery (PITR) up to 7 days

**Manual**:
```sh
# Export to GCS
gcloud sql export sql agentinvest-sql \
  gs://agentinvest-backups/canonical_db_$(date +%Y%m%d).sql \
  --database=canonical_db

# Restore from backup
gcloud sql import sql agentinvest-sql \
  gs://agentinvest-backups/canonical_db_20260616.sql \
  --database=canonical_db
```

---

## Networking & Security

### Private VPC

- GKE cluster: VPC-native networking (Alias IP)
- Cloud SQL: Private IP via Private Service Connection (no public IP)
- Pods communicate with Cloud SQL over private network

### Service-to-Service Communication

- **Internal**: Kubernetes DNS (e.g., `restate-service:8080`)
- **Restate Admin**: Internal ClusterIP (not exposed externally)
- **Operator UI**: Exposed via Kubernetes Ingress with Cloud IAP + Cloud Armor

### Secrets Management

All sensitive data in Cloud Secret Manager:

```sh
# Anthropic API key
kubectl create secret generic anthropic-credentials \
  --from-literal=api-key="$ANTHROPIC_API_KEY" \
  -n agentinvest

# Cloud SQL credentials
kubectl create secret generic cloudsql-credentials \
  --from-literal=username="agentinvest" \
  --from-literal=password="$CLOUD_SQL_PASSWORD" \
  -n agentinvest
```

---

## Observability

### Logging

All pod logs automatically collected by **Cloud Logging**:

```sh
# View logs
gcloud logging read "resource.type=k8s_container AND resource.labels.namespace_name=agentinvest" \
  --limit=50

# Stream logs
kubectl logs -n agentinvest -f -l "app in (restate,ts-endpoint,py-endpoint)"
```

### Monitoring

**Cloud Monitoring** captures metrics:
- Pod CPU, memory, network
- Cloud SQL connections, queries, replication lag
- Application custom metrics

### Alerting

Example: Alert on high Cloud SQL CPU:

```bash
gcloud alpha monitoring policies create \
  --display-name="Cloud SQL High CPU" \
  --condition-threshold-value=0.8 \
  --condition-threshold-filter='resource.type="cloudsql_database"'
```

---

## Troubleshooting

### Pod not starting

```sh
kubectl describe pod <pod-name> -n agentinvest
kubectl logs <pod-name> -n agentinvest --previous
```

### Cloud SQL connection issues

Test connectivity:
```sh
kubectl run -it --rm debug \
  --image=gcr.io/cloud-builders/kubectl:latest \
  --serviceaccount=agentinvest-gke \
  -n agentinvest -- \
  psql "postgresql://agentinvest:PASSWORD@PRIVATE_IP:5432/canonical_db"
```

### Restate handler registration fails

Check Restate logs:
```sh
kubectl logs -n agentinvest -l app=restate | grep -i "register\|error"
```

Port-forward to admin API:
```sh
kubectl port-forward -n agentinvest svc/restate-service 9070:9070
curl http://localhost:9070/health
```

---

## Cost Estimate

| Component | Monthly Cost |
|-----------|--------------|
| GKE (3x e2-standard-2) | ~$150 |
| Cloud SQL (db-custom-2-8, standard) | ~$100 |
| Cloud SQL HA (add standby replica) | +$100 |
| Artifact Registry / GCR | ~$10 |
| Cloud NAT (egress) | ~$30 |
| Total (standard) | ~$290 |
| Total (HA) | ~$390 |

---

## Next Steps

1. ✅ **Choose deployment target**: GKE + Cloud SQL (recommended)
2. ⏳ **Follow [GKE-DEPLOYMENT-RUNBOOK.md](GKE-DEPLOYMENT-RUNBOOK.md)** for step-by-step setup
3. ⏳ **Follow [CLOUD-SQL-PERSISTENCE-GUIDE.md](CLOUD-SQL-PERSISTENCE-GUIDE.md)** for data migration
4. ⏳ **Review Kubernetes manifests** in `kubernetes/` directory
5. ⏳ **Configure monitoring and alerting** in Cloud Monitoring
6. ⏳ **Test disaster recovery** (backup restore, PITR)
7. ⏳ **Document operational runbooks** for team

---

## References

- [GCP Deployment Plan](../GCP-DEPLOYMENT-PLAN-GKE-CLOUDSQL.md) — Architecture overview
- [GKE Deployment Runbook](./GKE-DEPLOYMENT-RUNBOOK.md) — Step-by-step commands
- [Cloud SQL Persistence Guide](./CLOUD-SQL-PERSISTENCE-GUIDE.md) — Data layer setup
- [Architecture Comparison](./ARCHITECTURE-COMPARISON.md) — GKE vs. Cloud Run
- [GKE Docs](https://cloud.google.com/kubernetes-engine/docs)
- [Cloud SQL Docs](https://cloud.google.com/sql/docs)
- [Restate Postgres State Store](https://docs.restate.dev/deploy/self-hosted#postgres-state-store)

---

## Legacy / Alternative Paths

- **Cloud Run deployment** (for testing/dev): See `cloudrun/` directory (maintained but not recommended for production)
- **Kubernetes manifests** (legacy): See `k8s/` directory (may be outdated)

**Recommendation**: Use **GKE + Cloud SQL** for all non-development deployments.
