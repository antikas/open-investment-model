# Deployment Architecture Comparison

## Status Update: GKE and Cloud SQL Now Enabled

As of 2026-06-16, GKE (`container.googleapis.com`) and Cloud SQL (`sqladmin.googleapis.com`) APIs are enabled in the GCP project. This enables a **significant architecture upgrade** from the initial Cloud Run + DuckDB approach.

---

## Option A: Cloud Run + DuckDB (Original)

| Aspect | Status |
|--------|--------|
| **Advantages** | Serverless, pay-per-request, auto-scaling from 0 |
| **Data persistence** | Ephemeral; requires GCS backup/restore workaround |
| **Restate durability** | Lost on pod restart (backup/restore complexity) |
| **Cost** | ~$310/month baseline |
| **Operational complexity** | Medium (state synchronization overhead) |
| **HA/DR** | Limited (requires custom backup logic) |
| **Networking** | Service-to-service via identity tokens |

**Status**: ❌ No longer recommended. See Cloud Run docs in `deployment/gcp/cloudrun/` for reference only.

---

## Option B: GKE + Cloud SQL (Recommended)

| Aspect | Status |
|--------|--------|
| **Advantages** | Enterprise-grade, durable, true HA/DR, managed Postgres backend |
| **Data persistence** | Postgres with automatic backups, PITR, replication |
| **Restate durability** | Full durability via Cloud SQL backend (Restate state guaranteed) |
| **Cost** | ~$150-300/month (GKE + Cloud SQL) |
| **Operational complexity** | Low (GKE handles orchestration, Cloud SQL handles data) |
| **HA/DR** | Automatic failover, PITR up to 7 days, snapshots |
| **Networking** | Private Service Connection, internal ClusterIP services |

**Status**: ✅ **PRIMARY DEPLOYMENT TARGET**. See GKE deployment guide in `deployment/gcp/GKE-DEPLOYMENT-RUNBOOK.md`.

---

## Detailed Comparison

### 1. Data Persistence

**Cloud Run + DuckDB**:
- DuckDB file stored at `/tmp/agentinvest/duckdb/canonical.duckdb`
- Ephemeral—lost on container restart unless backed up to GCS
- Requires custom startup/shutdown hooks for backup/restore
- Risk: Data loss on unplanned outages
- Restate state also ephemeral (no built-in durability)

**GKE + Cloud SQL**:
- All data in Postgres with automatic daily backups
- Point-in-time recovery (PITR) up to 7 days
- High Availability with automatic failover
- Restate uses Postgres backend for true durability
- Zero risk of data loss (barring catastrophic Cloud SQL failure)

### 2. Cost Analysis

**Cloud Run + DuckDB**:
```
GCR/Artifact Registry:        ~$10/month
Cloud Run (5 services):        ~$250/month (600k requests/month, 128MB-2GB RAM)
Cloud NAT (egress):            ~$30/month
Backup storage (GCS):          ~$5/month
Total:                         ~$295/month
```

**GKE + Cloud SQL**:
```
GKE (3 nodes, e2-standard-2): ~$150/month
Cloud SQL (db-custom-2-8):     ~$100/month (with HA: +$100)
Artifact Registry:             ~$10/month
Cloud NAT (egress):            ~$30/month
Total:                         ~$290/month (standard), ~$390/month (HA)
```

**Verdict**: Similar cost, but GKE + Cloud SQL offers better durability.

### 3. Operational Complexity

**Cloud Run + DuckDB**:
- 5 independent service deployments via `gcloud run deploy`
- Manual secret management and environment variables
- Custom backup/restore logic required
- Limited debugging (Cloud Run doesn't expose internal networks)
- Stateless containers but state management overhead

**GKE + Cloud SQL**:
- Single Kubernetes cluster manages all pods
- Kubernetes namespaces, services, deployments
- Cloud SQL handles backups automatically
- Full Kubernetes debugging (kubectl logs, port-forward, etc.)
- Workload Identity simplifies service account management

**Verdict**: GKE is initially more complex to set up, but operationally simpler once running.

### 4. High Availability and Disaster Recovery

**Cloud Run + DuckDB**:
- Cloud Run automatically scales and replaces failed services
- No data durability (DuckDB files can be lost)
- Manual PITR via GCS restore (complex, error-prone)
- RTO: 15 minutes; RPO: hours (if backups run hourly)

**GKE + Cloud SQL**:
- GKE auto-scales pods; Cloud SQL HA auto-fails over
- Cloud SQL backups every 24 hours; PITR up to 7 days
- Automatic failover to standby replica (if HA enabled)
- RTO: 5 minutes; RPO: 5 minutes (with HA + backups)

**Verdict**: GKE + Cloud SQL is vastly superior for production.

### 5. Networking and Security

**Cloud Run + DuckDB**:
- Service-to-service auth via signed identity tokens
- Cloud Run ingress (public or via Cloud IAP)
- No private VPC option (everything flows through Google's public internet)
- Simple but limited security options

**GKE + Cloud SQL**:
- Private VPC with VPC-native networking
- Cloud SQL Private Service Connection (no public IP)
- Kubernetes NetworkPolicy for pod-to-pod firewall
- GKE Workload Identity for fine-grained IAM
- Cloud Armor for DDoS protection
- IAP for operator UI authentication

**Verdict**: GKE + Cloud SQL offers significantly better security.

---

## Migration Path

### From Cloud Run to GKE + Cloud SQL

1. **Set up GKE cluster** (Step 2 in GKE-DEPLOYMENT-RUNBOOK.md)
2. **Create Cloud SQL instance** (Step 3)
3. **Migrate DuckDB schema to Postgres** (CLOUD-SQL-PERSISTENCE-GUIDE.md Step 3)
4. **Build and push new container images** (with Cloud SQL support)
5. **Deploy to GKE** (Step 11-12 in GKE-DEPLOYMENT-RUNBOOK.md)
6. **Verify all services** (Step 14)
7. **Decommission Cloud Run services** (optional, can run parallel for transition period)

**Downtime**: ~1 hour (during data migration)

---

## Decision Matrix

| Scenario | Cloud Run | GKE + Cloud SQL |
|----------|-----------|-----------------|
| **Development/testing** | ✅ Good | ✅ Better (full debuggability) |
| **Staging** | ✅ Acceptable | ✅ Recommended |
| **Production (SLA < 99.9%)** | ⚠️ Risky | ✅ Recommended |
| **Production (SLA = 99.99%)** | ❌ Not suitable | ✅ Recommended |
| **Cost-conscious** | ✅ Cheaper | ✅ Similar |
| **Durability critical** | ❌ Manual workarounds | ✅ Built-in |
| **Compliance (audit logs)** | ⚠️ Limited | ✅ Full support |

---

## Recommendation

**Use GKE + Cloud SQL for all non-development deployments.**

- Production: **GKE + Cloud SQL (HA enabled)**
- Staging: **GKE + Cloud SQL (standard)**
- Development: **Either (Cloud Run is simpler for quick tests; GKE mirrors production)**

---

## Next Steps

1. Review [GCP-DEPLOYMENT-PLAN-GKE-CLOUDSQL.md](GCP-DEPLOYMENT-PLAN-GKE-CLOUDSQL.md) for detailed architecture
2. Follow [GKE-DEPLOYMENT-RUNBOOK.md](GKE-DEPLOYMENT-RUNBOOK.md) for step-by-step deployment
3. Review [CLOUD-SQL-PERSISTENCE-GUIDE.md](CLOUD-SQL-PERSISTENCE-GUIDE.md) for data layer setup
4. See [Kubernetes manifest templates](kubernetes/) for pod configurations

---

## References

- Cloud Run docs: https://cloud.google.com/run/docs
- GKE docs: https://cloud.google.com/kubernetes-engine/docs
- Cloud SQL docs: https://cloud.google.com/sql/docs
- Restate docs: https://docs.restate.dev
