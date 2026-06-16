# Cloud SQL Persistence Guide for agentINVEST

## Overview

Cloud SQL Postgres serves as the durable backend for:
1. **Restate state store** (workflow execution, completion journal, state)
2. **Canonical data layer** (dbt models, application data, append-only stores)

This guide covers setup, migration from local DuckDB, backup/restore, and disaster recovery.

---

## 1. Cloud SQL Instance Setup

### Initial configuration

```sh
export PROJECT_ID="$(gcloud config get-value project)"
export REGION="us-central1"
export INSTANCE_NAME="agentinvest-sql"
export DB_VERSION="POSTGRES_15"

# Create instance with high availability
gcloud sql instances create "${INSTANCE_NAME}" \
  --database-version="${DB_VERSION}" \
  --region="${REGION}" \
  --tier=db-custom-2-8192 \
  --storage-type=PD_SSD \
  --storage-size=100GB \
  --availability-type=REGIONAL \
  --backup-start-time=02:00 \
  --enable-bin-log \
  --retained-backups-count=30 \
  --enable-point-in-time-recovery
```

### Create databases and users

```sql
-- Connect via gcloud sql connect agentinvest-sql --user=postgres

-- Restate state store
CREATE DATABASE restate_state;

-- Canonical data and dbt models
CREATE DATABASE canonical_db;

-- Application user (limited privileges)
CREATE USER agentinvest WITH PASSWORD 'GENERATED_SECURE_PASSWORD';

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE restate_state TO agentinvest;
GRANT ALL PRIVILEGES ON DATABASE canonical_db TO agentinvest;

-- Set schema permissions
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON TABLES TO agentinvest;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON SEQUENCES TO agentinvest;
```

### Enable required extensions

```sql
-- In both databases:
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For full-text search
CREATE EXTENSION IF NOT EXISTS "hstore";   -- For JSON-like data
```

---

## 2. Restate State Backend Configuration

### Initialize Restate database

Restate will automatically create its required tables on first run. Minimal manual setup:

```sql
-- In restate_state database:
-- Restate will create these tables:
-- - app_id
-- - invocation
-- - invocation_status
-- - service
-- - virtual_object_status
-- - etc.

-- Just ensure the database exists and the user has permissions
GRANT ALL ON SCHEMA public TO agentinvest;
```

### Environment variables for Restate pod

```yaml
RESTATE_DB_DRIVER: "postgres"
RESTATE_DB_HOST: "10.0.0.5"  # Private IP from Cloud SQL
RESTATE_DB_PORT: "5432"
RESTATE_DB_USER: "agentinvest"
RESTATE_DB_PASSWORD: "from-secret"
RESTATE_DB_NAME: "restate_state"
RESTATE_DB_SSL_MODE: "require"
```

---

## 3. Migration from Local DuckDB to Cloud SQL

### Step 1: Export DuckDB schema

```bash
# Export DuckDB to SQL (locally, before containerization)
duckdb canonical.duckdb << EOF
.mode list
.output export.sql
.schema
EOF
```

### Step 2: Adapt schema for Postgres

DuckDB and Postgres have different data types. Common adaptations:

| DuckDB | Postgres |
|--------|----------|
| HUGEINT | BIGINT |
| UHUGEINT | NUMERIC(20,0) |
| STRUCT | JSONB |
| LIST | TEXT[] or JSON |
| UBIGINT | NUMERIC(20,0) |

```bash
# Create adaptation script (example)
sed -i 's/HUGEINT/BIGINT/g' export.sql
sed -i 's/STRUCT/JSONB/g' export.sql
```

### Step 3: Load schema into Cloud SQL

```bash
# Connect and load
gcloud sql connect agentinvest-sql --user=agentinvest << EOF
\c canonical_db
\i export.sql
EOF
```

### Step 4: Migrate seed data

```python
# Python script to extract DuckDB, transform, load to Cloud SQL

import duckdb
import psycopg2
import json

# Connect to DuckDB
duckdb_conn = duckdb.connect('canonical.duckdb')

# Connect to Cloud SQL
cloudsql_conn = psycopg2.connect(
    host="PRIVATE_IP",
    port=5432,
    database="canonical_db",
    user="agentinvest",
    password="PASSWORD"
)
cloudsql_cursor = cloudsql_conn.cursor()

# Export and migrate tables
tables = duckdb_conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main'").fetchall()

for table_name, in tables:
    print(f"Migrating {table_name}...")
    
    # Read from DuckDB
    df = duckdb_conn.execute(f"SELECT * FROM {table_name}").fetch_df()
    
    # Insert into Cloud SQL
    for _, row in df.iterrows():
        columns = list(row.index)
        values = list(row.values)
        
        # Handle NaN and special types
        values = [None if pd.isna(v) else json.dumps(v) if isinstance(v, dict) else v for v in values]
        
        insert_sql = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({', '.join(['%s'] * len(columns))})"
        cloudsql_cursor.execute(insert_sql, values)
    
    cloudsql_conn.commit()
    print(f"Migrated {len(df)} rows to {table_name}")

cloudsql_conn.close()
duckdb_conn.close()
```

---

## 4. dbt Integration with Cloud SQL

### Update `reference/dbt/profiles.yml`

```yaml
agentinvest:
  outputs:
    dev:
      type: duckdb
      path: 'canonical.duckdb'
      threads: 4
    
    prod:
      type: postgres
      host: "10.0.0.5"  # Cloud SQL private IP
      user: agentinvest
      password: "{{ env_var('CANONICAL_DB_PASSWORD') }}"
      port: 5432
      dbname: canonical_db
      schema: public
      threads: 4
      keepalives_idle: 0
      
  target: prod
```

### Test dbt build against Cloud SQL

```bash
cd reference/dbt

# Set environment variable for password
export CANONICAL_DB_PASSWORD="from-secret"

# Test connection
dbt debug

# Run models
dbt build

# View results
dbt test
dbt docs generate
```

---

## 5. Backup and Recovery

### Automated backups (Cloud SQL managed)

```bash
# List backups
gcloud sql backups list --instance="agentinvest-sql"

# Restore from backup (creates new instance)
gcloud sql backups restore BACKUP_ID \
  --backup-instance="agentinvest-sql" \
  --backup-configuration="backup-config"
```

### Manual on-demand backup

```bash
# Export to Cloud Storage
gcloud sql export sql agentinvest-sql \
  gs://agentinvest-backups/restate_state_$(date +%Y%m%d_%H%M%S).sql \
  --database=restate_state

gcloud sql export sql agentinvest-sql \
  gs://agentinvest-backups/canonical_db_$(date +%Y%m%d_%H%M%S).sql \
  --database=canonical_db
```

### Point-in-time recovery (PITR)

```bash
# Restore to a specific point in time
gcloud sql backups restore BACKUP_ID \
  --backup-instance="agentinvest-sql" \
  --point-in-time="2026-06-16T10:30:00Z"
```

### Restore from GCS export

```bash
# Create new instance and restore
gcloud sql import sql agentinvest-sql \
  gs://agentinvest-backups/canonical_db_20260616_120000.sql \
  --database=canonical_db
```

---

## 6. Disaster Recovery Plan

### Recovery Time Objective (RTO): 30 minutes
### Recovery Point Objective (RPO): 5 minutes

**Procedure**:

1. **Detect issue** (monitoring alert or manual check)
2. **Assess data integrity** (query recent tables, check replication lag)
3. **Initiate PITR** (choose recovery point from last 7 days)
4. **Failover to restored instance** (update connection strings in GKE)
5. **Verify data** (run smoke tests, check Restate handler registration)
6. **Update DNS** (if needed) and notify users

**Example failover command**:

```bash
# Create new instance from PITR
gcloud sql backups restore LATEST_BACKUP_ID \
  --backup-instance="agentinvest-sql" \
  --point-in-time="2026-06-16T10:25:00Z"

# Update GKE secrets with new connection string
kubectl patch secret cloudsql-connection \
  -p '{"data":{"connection-string":"postgresql://agentinvest:PASSWORD@NEW_PRIVATE_IP:5432/canonical_db"}}' \
  -n agentinvest

# Restart pods to pick up new connection
kubectl rollout restart deployment restate -n agentinvest
kubectl rollout restart deployment py-endpoint -n agentinvest
```

---

## 7. Monitoring and Alerting

### Key metrics to monitor

- **CPU utilization** (alert if >80%)
- **Memory usage** (alert if >85%)
- **Disk space** (alert if >90%)
- **Replication lag** (High Availability, alert if >1000ms)
- **Connection count** (alert if >500)
- **Query latency** (p95 latency)

### Create monitoring dashboard

```bash
# Use Cloud Monitoring to create custom dashboard
# Key metrics:
# - cloudsql.googleapis.com/database/cpu/utilization
# - cloudsql.googleapis.com/database/memory/utilization
# - cloudsql.googleapis.com/database/disk/utilization
```

### Create alerts

```bash
# Example: Alert on high CPU
gcloud alpha monitoring policies create \
  --display-name="Cloud SQL High CPU" \
  --condition-display-name="CPU > 80%" \
  --condition-threshold-value=0.8 \
  --condition-threshold-filter='resource.type="cloudsql_database"'
```

---

## 8. Security Best Practices

### Network security

- [ ] Private Service Connection enabled (no public IP)
- [ ] VPC Firewall rules restrict access to GKE subnet only
- [ ] SSL/TLS required for all connections

### Access control

- [ ] Separate IAM roles for dbt (read), Restate (read/write), backups (export)
- [ ] Workload Identity instead of service account keys
- [ ] Regular access reviews

### Data protection

- [ ] Automated backups to immutable GCS bucket
- [ ] Point-in-time recovery enabled (7-day window)
- [ ] Encryption at rest (Cloud SQL default)
- [ ] Audit logging enabled

### Compliance

- [ ] Retention policies: 90 days for backups
- [ ] Data residency: US region only
- [ ] Encryption in transit: TLS required

---

## 9. Cost Optimization

| Component | Cost | Notes |
|-----------|------|-------|
| Cloud SQL (db-custom-2-8, HDD) | $60/month | High Availability: +$60 |
| Storage (100GB, SSD) | $20/month | Auto-scaling: +$0.17/GB over 100GB |
| Backups (30-day retention) | $10/month | ~1 backup per day |
| **Total** | **$90-150/month** | Includes HA and 7-day PITR |

**Cost reduction tips**:
- Use shared-core machine for development (db-f1-micro: $15/month)
- Enable committed use discounts (1-year: ~25% savings)
- Set appropriate backup retention (30 days is standard)

---

## 10. Operational Runbook

### Daily operations

```bash
# Check instance status
gcloud sql instances describe agentinvest-sql

# View recent slow queries
gcloud sql operations list --instance=agentinvest-sql --limit=10

# Monitor via Cloud Console
# https://console.cloud.google.com/sql/instances
```

### Weekly maintenance

```bash
# Test restore procedure
gcloud sql backups create \
  --instance=agentinvest-sql \
  --description="Weekly test backup"

# Review access logs
gcloud logging read "resource.type=cloudsql_database" --limit=100
```

### Monthly reviews

- [ ] Backup retention policy review
- [ ] Access control audit
- [ ] Cost analysis and optimization
- [ ] PITR test restore
- [ ] Disaster recovery drill

---

## References

- [Cloud SQL High Availability](https://cloud.google.com/sql/docs/postgres/high-availability)
- [Cloud SQL PITR](https://cloud.google.com/sql/docs/postgres/point-in-time-recovery)
- [dbt Postgres adapter](https://docs.getdbt.com/reference/warehouse-setups/postgres-setup)
- [Restate Postgres backend](https://docs.restate.dev/deploy/self-hosted#postgres-state-store)
