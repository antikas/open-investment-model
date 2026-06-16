# GCP Deployment Plan for agentINVEST (GKE + Cloud SQL)

**Status**: Updated 2026-06-16 — GKE and Cloud SQL APIs now enabled. Pivoting from Cloud Run to full Kubernetes + managed Postgres architecture.

## 1. Executive Summary

agentINVEST is a durable orchestration runtime built around:
- Restate (distributed workflow substrate with durability guarantees)
- TypeScript handler endpoint (orchestrator logic)
- Python tool service endpoint (LLM planning, dbt, tools)
- MCP stdio sidecar (optional model context protocol)
- Next.js operator UI (monitoring and control)

**Deployment target**: Google Kubernetes Engine (GKE) cluster with Cloud SQL Postgres backend for durability.

**Key decision**: Both Restate and the canonical data layer (DuckDB replacement) will use Cloud SQL Postgres as the backend, eliminating ephemeral state and providing enterprise-grade durability.

---

## 2. Architecture Overview

### Deployment topology

```
GKE Cluster
├── restate-server Pod (Port 8080 ingress, 9070 admin internal)
├── agentinvest-ts-endpoint Pod (Port 9090)
├── agentinvest-py-endpoint Pod (Port 9091)
├── agentinvest-mcp Pod (optional)
└── agentinvest-operator-ui Pod (Port 4180, exposed via Ingress)

Cloud SQL (Private Service Connection)
├── restate_state (Postgres schema for Restate durability)
└── canonical_db (Postgres schema for canonical data + dbt runs)

GCS (for backups)
└── agentinvest-backups/
    ├── dbt-runs/
    └── audit-logs/

Secret Manager
├── ANTHROPIC_API_KEY
├── CLOUD_SQL_CONNECTION_STRING
└── OPERATOR_UI_ADMIN_PASSWORD (optional)
```

### Networking

- **Internal service discovery**: Kubernetes DNS (e.g., `restate-service:8080` for handlers to call Restate)
- **Restate admin**: Internal ClusterIP service (not exposed externally)
- **Operator UI**: Exposed via Kubernetes Ingress with Cloud Armor and IAP
- **Cloud SQL**: Private Service Connection over private VPC (no public IP)
- **Egress**: Anthropic API calls go through NAT Gateway or Cloud NAT for security

---

## 3. Core Components

### 3.1 Restate Runtime

**Container image**: `gcr.io/$PROJECT_ID/agentinvest-restate:latest`

**Pod specification**:
- Replica: 1 (Restate maintains internal HA; single pod is sufficient for now)
- Memory: 2Gi
- CPU: 2 cores
- Startup probe: Restate admin `/health` endpoint (port 9070)

**Key configuration**:
- State backend: Cloud SQL Postgres (connection string from Secret Manager)
- Ingress port: 8080 (handlers register and invoke here)
- Admin port: 9070 (internal only, for monitoring and control)
- Base directory: `/var/lib/restate` (ephemeral, all state in Postgres)

**Cloud SQL schema setup**:
```sql
CREATE DATABASE restate_state;
-- Restate auto-creates tables on first run
```

### 3.2 TypeScript Handler Endpoint

**Container image**: `gcr.io/$PROJECT_ID/agentinvest-ts-endpoint:latest`

**Pod specification**:
- Replicas: 2 (auto-scale 1–5 based on CPU)
- Memory: 1Gi
- CPU: 1 core
- Liveness probe: `/health` endpoint (if implemented)

**Key configuration**:
- Register endpoint with Restate at `http://restate-service:8080`
- Expose handler RPC on port 9090
- Load balancer distributes traffic across replicas

### 3.3 Python Tool Endpoint

**Container image**: `gcr.io/$PROJECT_ID/agentinvest-py-endpoint:latest`

**Pod specification**:
- Replicas: 2 (auto-scale 1–4 based on CPU)
- Memory: 2Gi
- CPU: 2 cores
- Liveness probe: Tool health check

**Key configuration**:
- Register tools with Restate at `http://restate-service:8080`
- Cloud SQL connection string (from Secret Manager)
- dbt profile: Use `PROD` profile targeting Cloud SQL (no longer local DuckDB)
- Anthropic API key (from Secret Manager)
- Expose tool RPC on port 9091

**Cloud SQL schema setup**:
```sql
CREATE DATABASE canonical_db;
-- dbt models run here; Restate append-only stores also land here
```

### 3.4 Operator UI

**Container image**: `gcr.io/$PROJECT_ID/agentinvest-operator-ui:latest`

**Pod specification**:
- Replicas: 2 (auto-scale 1–3 based on CPU)
- Memory: 512Mi
- CPU: 1 core
- Expose on port 4180

**Ingress configuration**:
- HTTPS with Cloud Load Balancer
- Cloud Armor security policies (rate limiting, geo-blocking)
- Cloud IAP for authentication
- Protected with Cloud SQL secrets (read-only connection to `canonical_db`)

---

## 4. Data Persistence Strategy

### 4.1 Restate State Durability

**Solution**: Cloud SQL Postgres backend for Restate state

- Restate is configured to use Postgres as the state store (not local disk)
- All workflow execution logs, completion journal, and state are persisted
- Cloud SQL provides automatic backups, point-in-time recovery, and failover
- No data loss on pod restart or cluster migration

**Setup**:
1. Create `restate_state` database in Cloud SQL
2. Set `RESTATE_DB_CONNECTION_STRING` environment variable pointing to Cloud SQL private IP
3. Restate auto-creates tables on first startup

### 4.2 Canonical Data Layer

**Solution**: Cloud SQL Postgres with dbt integration

- **Before**: DuckDB files stored locally (ephemeral on Cloud Run)
- **Now**: Postgres tables in `canonical_db` managed by dbt
- dbt profiles.yml references Cloud SQL via Private Service Connection
- Python endpoint reads/writes canonical data directly to Postgres

**Migration path**:
1. Export current DuckDB schema to Postgres CREATE statements
2. Load seed data to Postgres
3. Point Python endpoint and dbt to Cloud SQL `canonical_db`
4. Disable local DuckDB

### 4.3 Backup and Recovery

**Automated backups**:
- Cloud SQL automated backups (daily, 30-day retention)
- Point-in-time recovery window: 7 days

**Manual exports** (for audit/compliance):
```bash
gcloud sql export sql $INSTANCE canonical_db gs://agentinvest-backups/canonical_db_$(date +%Y%m%d).sql
gcloud sql export sql $INSTANCE restate_state gs://agentinvest-backups/restate_state_$(date +%Y%m%d).sql
```

**Audit journal export**:
- dbt audit model writes to `canonical_db.audit_journal` table
- Daily export to GCS immutable bucket

---

## 5. Networking and Security

### 5.1 VPC and Connectivity

- GKE cluster uses VPC-native networking (Alias IP ranges)
- Cloud SQL private Service Connection enabled
- Cloud SQL has private IP only (no public IP)
- Cloud NAT gateway for egress (e.g., Anthropic API calls)

### 5.2 Service-to-Service Authentication

- Kubernetes NetworkPolicy restricts pod-to-pod traffic
- Restate admin API (port 9070) only accessible from within cluster
- Restate ingress (port 8080) only accessible from handler/tool pods

### 5.3 External Access

- Operator UI exposed via Ingress (HTTPS, Cloud IAP)
- No direct access to Restate admin or individual service endpoints
- All API access routed through operator UI or authenticated Ingress

### 5.4 Secrets Management

All sensitive data stored in Secret Manager:
- `ANTHROPIC_API_KEY`: LLM model credentials
- `CLOUD_SQL_CONNECTION_STRING`: Postgres connection details
- `OPERATOR_UI_ADMIN_PASSWORD`: UI authentication (optional)

Pods access secrets via GKE Workload Identity + IAM bindings.

---

## 6. Deployment Phases

### Phase 1: GKE Setup (Week 1)
- Create GKE cluster (standard, 3 nodes, auto-scaling enabled)
- Configure VPC and Private Service Connection
- Set up Cloud SQL instance (Postgres 15+, 2 CPUs, 8GB RAM)
- Create databases: `restate_state` and `canonical_db`

### Phase 2: Service Deployment (Week 2)
- Build and push container images to Artifact Registry
- Create Kubernetes namespaces and service accounts
- Deploy Restate pod with Cloud SQL state backend
- Deploy TS endpoint, Python endpoint, Operator UI
- Verify pod-to-pod connectivity and Restate registration

### Phase 3: Data Migration (Week 3)
- Export DuckDB schema to Postgres
- Migrate seed data to Cloud SQL
- Update dbt profiles to point to Cloud SQL
- Test dbt build against Cloud SQL
- Cut over Python endpoint to use Cloud SQL

### Phase 4: Observability & Hardening (Week 4)
- Enable Cloud Logging and Cloud Monitoring
- Set up Cloud IAP for Operator UI
- Configure Cloud Armor policies
- Enable audit logging to GCS
- Test backup and recovery procedures

---

## 7. Verification Criteria

- [ ] GKE cluster is running with 3 nodes
- [ ] Cloud SQL instance is accessible via Private Service Connection
- [ ] Restate pod starts successfully with Cloud SQL state backend
- [ ] TS and Python endpoints register handlers/tools with Restate
- [ ] Pod-to-pod communication verified (DNS resolution, network policies)
- [ ] dbt build succeeds against Cloud SQL `canonical_db`
- [ ] Canonical data is readable from Postgres (no local DuckDB)
- [ ] Operator UI is accessible via Ingress + Cloud IAP
- [ ] Anthropic API calls succeed (egress via Cloud NAT)
- [ ] Cloud SQL backups are automated and testable

---

## 8. Cost Estimate (Monthly)

| Component | Estimate | Notes |
|-----------|----------|-------|
| GKE cluster (3x e2-standard-2) | $150 | Standard pricing; auto-scaling can reduce cost |
| Cloud SQL (db-custom-2-8192, HDD) | $100 | High availability recommended: +$100 |
| Artifact Registry storage | $10 | Container images |
| Cloud NAT egress | $30 | Variable; depends on API call volume |
| Ingress + Load Balancer | $20 | Cloud Load Balancer + Cloud Armor |
| **Total** | **$310** | Minimum viable production setup |

---

## 9. Next Steps

1. **Request GKE cluster setup** (or use Terraform script in `deployment/gcp/terraform/`)
2. **Request Cloud SQL instance** with Private Service Connection
3. **Update Dockerfiles** to support Cloud SQL connection strings
4. **Create Kubernetes manifests** (Deployment, Service, StatefulSet, ConfigMap, Secret)
5. **Update deployment runbook** with GKE-specific commands
6. **Test locally** with docker-compose + Postgres
7. **Dry-run on GKE** with limited traffic
8. **Enable monitoring and alerting**
9. **Finalize backup/recovery procedures**

---

## 10. References

- [GKE Architecture](https://cloud.google.com/kubernetes-engine/docs/concepts/architecture)
- [Cloud SQL Private Service Connection](https://cloud.google.com/sql/docs/postgres/private-ip-overview)
- [Restate Postgres State Backend](https://docs.restate.dev/deploy/self-hosted#postgres-state-store)
- [GKE Workload Identity](https://cloud.google.com/kubernetes-engine/docs/workload-identity)
