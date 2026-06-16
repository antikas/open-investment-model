# Deployment Strategy Update: GKE + Cloud SQL

**Date**: 2026-06-16  
**Status**: APIs now enabled — Architecture pivot complete

---

## What Changed

On 2026-06-16, GKE (`container.googleapis.com`) and Cloud SQL (`sqladmin.googleapis.com`) APIs became enabled in project `prod-12-378id`.

**Previous Strategy**: Cloud Run + DuckDB (ephemeral, manual backup/restore)  
**New Strategy**: GKE + Cloud SQL (durable Postgres backend)

---

## New Artifacts (Committed to gcp-deployment-plan)

### Documentation

1. **`GCP-DEPLOYMENT-PLAN-GKE-CLOUDSQL.md`** ⭐ NEW
   - Complete architectural overview for GKE + Cloud SQL
   - Deployment topology diagram
   - Component descriptions (Restate, TS/Python endpoints, Operator UI)
   - Data persistence strategy (Cloud SQL backend for both Restate and canonical data)
   - 4-week phased rollout plan
   - Cost estimate and verification criteria

2. **`deployment/gcp/README-GKE.md`** ⭐ NEW
   - Quick-start guide for GKE deployment
   - Links to runbooks and guides
   - Artifacts directory structure
   - Deployment phases overview

3. **`deployment/gcp/GKE-DEPLOYMENT-RUNBOOK.md`** ⭐ NEW (360 lines)
   - **Step-by-step operational guide**
   - 15 executable steps from GKE cluster creation to smoke testing
   - Cloud SQL setup (Private Service Connection, databases)
   - Workload Identity configuration (IAM bindings)
   - Kubernetes secret creation
   - Container image build and push
   - Deployment to GKE with kubectl
   - Ingress setup for Operator UI
   - Troubleshooting procedures
   - Clean-up commands

4. **`deployment/gcp/CLOUD-SQL-PERSISTENCE-GUIDE.md`** ⭐ NEW (450 lines)
   - **Cloud SQL setup and migration guide**
   - Instance configuration (High Availability, backups)
   - Restate state backend configuration
   - Migration from local DuckDB to Postgres:
     - Schema export/adapt
     - Data migration scripts (Python example)
   - dbt integration (profiles.yml for Postgres)
   - Backup and recovery procedures
   - Point-in-time recovery (PITR)
   - Disaster recovery plan (RTO/RPO targets)
   - Monitoring and alerting setup
   - Security best practices
   - Cost optimization tips
   - Operational runbook (daily/weekly/monthly tasks)

5. **`deployment/gcp/ARCHITECTURE-COMPARISON.md`** ⭐ NEW
   - Side-by-side comparison: Cloud Run vs. GKE + Cloud SQL
   - Detailed analysis of each architectural choice
   - Cost, complexity, HA/DR, networking, security comparisons
   - Migration path from Cloud Run to GKE
   - Decision matrix for scenario-based recommendations
   - Strong recommendation: **Use GKE + Cloud SQL for production**

### Deployment Artifacts

1. **`deployment/gcp/Dockerfile.restate`** (FIXED)
   - ✅ Downloads Restate v1.6.2 binary from GitHub releases
   - ✅ Extracts to `/opt/restate/restate-server`
   - ✅ Includes config file copy
   - ✅ No longer a placeholder

2. **`deployment/gcp/kubernetes/` (NEW DIRECTORY)**
   - **`generate-manifests.sh`** — Script to generate all manifests from templates
   - **`namespace.yaml`** — agentinvest namespace
   - **`service-account.yaml`** — Kubernetes service account + Workload Identity annotation
   - **`restate-deployment.yaml`** — Restate Pod + Service (Cloud SQL backend, 1 replica)
   - **`ts-endpoint-deployment.yaml`** — TS endpoint Pod + Service (2 replicas)
   - **`py-endpoint-deployment.yaml`** — Python endpoint Pod + Service (2 replicas, Anthropic key)
   - **`operator-ui-deployment.yaml`** — Operator UI Pod + Service (2 replicas)
   - **`hpa.yaml`** — Horizontal Pod Autoscalers for all endpoints
   - **`network-policy.yaml`** — Kubernetes NetworkPolicy (deny-all + allow specific ingress/egress)

### Updated Documentation

- **`GCP-DEPLOYMENT-PLAN.md`** (Existing)
  - Updated from Cloud Run focus to GKE + Cloud SQL
  - Removed Cloud Run-specific networking notes
  - Removed "avoid Cloud SQL" language
  - Updated verification criteria for GKE/Cloud SQL
  - Updated phased rollout phases

---

## Key Design Decisions

### 1. Persistence Strategy

**Restate State**:
- Cloud SQL Postgres backend (`restate_state` database)
- Automatic backups, PITR up to 7 days
- No state loss on pod restart ✅

**Canonical Data**:
- Cloud SQL Postgres (`canonical_db`) replaces local DuckDB
- dbt models run directly on Postgres
- Zero ephemeral state ✅

### 2. Networking

- **Private Service Connection**: Cloud SQL has no public IP
- **VPC-native GKE**: Pods communicate with Cloud SQL over private network
- **Internal Services**: Restate admin/ingress are ClusterIP (not exposed)
- **External Access**: Operator UI via Ingress + IAP

### 3. Service Accounts

- **GKE Workload Identity** instead of service account keys
- Pods bound to GCP SA via Kubernetes annotations
- Fine-grained IAM roles: Cloud SQL Client, Secret Manager Accessor, Logging Writer

### 4. Autoscaling

- **Restate**: 1 replica (stateful, doesn't need to scale)
- **TS Endpoint**: 1–5 replicas (HPA on CPU/memory)
- **Python Endpoint**: 1–4 replicas (HPA on CPU/memory)
- **Operator UI**: 1–3 replicas (HPA)

---

## Cost Implications

| Aspect | Cloud Run | GKE + Cloud SQL |
|--------|-----------|-----------------|
| **Base cost** | ~$295/month | ~$290/month (standard) / ~$390/month (HA) |
| **Data durability** | Manual workarounds | Built-in ✅ |
| **Operational complexity** | Medium | Low (once set up) |
| **Production-ready** | ❌ No | ✅ Yes |

**Recommendation**: The cost is nearly identical, but GKE + Cloud SQL is vastly superior for production workloads.

---

## How to Use These Artifacts

### For Deployment

1. **Read** [GCP-DEPLOYMENT-PLAN-GKE-CLOUDSQL.md](../GCP-DEPLOYMENT-PLAN-GKE-CLOUDSQL.md) for architecture overview
2. **Follow** [deployment/gcp/GKE-DEPLOYMENT-RUNBOOK.md](GKE-DEPLOYMENT-RUNBOOK.md) step-by-step
3. **Reference** [deployment/gcp/CLOUD-SQL-PERSISTENCE-GUIDE.md](CLOUD-SQL-PERSISTENCE-GUIDE.md) for data migration
4. **Apply** Kubernetes manifests from `deployment/gcp/kubernetes/`

### For Operations

- **Daily**: Check logs with `kubectl logs -n agentinvest -f`
- **Weekly**: Review Cloud SQL backups and test PITR restore
- **Monthly**: Audit IAM roles, review costs, run DR drill

### For Questions

- **Why GKE vs. Cloud Run?** → See [ARCHITECTURE-COMPARISON.md](ARCHITECTURE-COMPARISON.md)
- **How do I persist data?** → See [CLOUD-SQL-PERSISTENCE-GUIDE.md](CLOUD-SQL-PERSISTENCE-GUIDE.md)
- **What are the exact deployment commands?** → See [GKE-DEPLOYMENT-RUNBOOK.md](GKE-DEPLOYMENT-RUNBOOK.md)

---

## Files Summary

| File | Type | Status | Purpose |
|------|------|--------|---------|
| GCP-DEPLOYMENT-PLAN-GKE-CLOUDSQL.md | Doc | ✅ NEW | Architectural blueprint |
| deployment/gcp/README-GKE.md | Doc | ✅ NEW | Quick-start guide |
| deployment/gcp/GKE-DEPLOYMENT-RUNBOOK.md | Doc | ✅ NEW | Step-by-step deployment (360 lines) |
| deployment/gcp/CLOUD-SQL-PERSISTENCE-GUIDE.md | Doc | ✅ NEW | Data migration & ops (450 lines) |
| deployment/gcp/ARCHITECTURE-COMPARISON.md | Doc | ✅ NEW | GKE vs. Cloud Run analysis |
| deployment/gcp/Dockerfile.restate | Code | ✅ FIXED | Now downloads Restate v1.6.2 |
| deployment/gcp/kubernetes/ | Dir | ✅ NEW | Manifests + generator script |
| GCP-DEPLOYMENT-PLAN.md | Doc | ✅ UPDATED | Removed Cloud Run language |
| deployment/gcp/cloudrun/ | Dir | ⚠️ LEGACY | Still available, not recommended |

---

## What's Next

### Immediate (This Week)
- [ ] Review architecture with team
- [ ] Verify GKE cluster creation pre-requisites
- [ ] Reserve static IP for Operator UI
- [ ] Finalize Anthropic API key management

### Short-term (Next Week)
- [ ] Create GKE cluster (Step 2)
- [ ] Create Cloud SQL instance (Step 3)
- [ ] Test data migration scripts
- [ ] Build Docker images
- [ ] Deploy to GKE
- [ ] Run smoke tests

### Medium-term (Weeks 3–4)
- [ ] Set up Cloud Monitoring dashboards
- [ ] Configure Cloud IAP for Operator UI
- [ ] Test disaster recovery (PITR, backup restore)
- [ ] Document operational runbooks for team
- [ ] Performance test and optimize

---

## Commits on gcp-deployment-plan Branch

All artifacts in this update are committed to the `gcp-deployment-plan` branch:

```bash
git branch: gcp-deployment-plan
Commits:
  - [DEPLOYMENT] Pivot architecture from Cloud Run to GKE + Cloud SQL
  - [DOCS] Add GKE deployment runbook (360 lines)
  - [DOCS] Add Cloud SQL persistence guide (450 lines)
  - [DOCS] Add architecture comparison
  - [DOCKER] Fix Dockerfile.restate to download Restate v1.6.2
  - [K8S] Add Kubernetes manifests and generator script
  - [DOCS] Update GCP-DEPLOYMENT-PLAN.md for GKE + Cloud SQL
```

---

## Summary

**The deployment architecture is now fully defined and operationalized:**

- ✅ GKE + Cloud SQL provides enterprise-grade durability
- ✅ Restate gains true state durability via Postgres backend
- ✅ Canonical data (DuckDB → Postgres) ensures zero data loss
- ✅ Complete operational runbooks enable hands-off deployments
- ✅ Kubernetes manifests ready for kubectl apply
- ✅ Cost is competitive with Cloud Run
- ✅ HA/DR built-in (backups, PITR, failover)

**Next action**: Follow GKE-DEPLOYMENT-RUNBOOK.md step-by-step for deployment.
