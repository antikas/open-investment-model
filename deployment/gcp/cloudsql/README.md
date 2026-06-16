# Cloud SQL for agentINVEST

This folder documents a Postgres-based deployment path, but the current Cloud Run deployment uses DuckDB instead.

## Notes

- The current Cloud Run deployment is intentionally using **DuckDB** for the canonical data layer.
- Cloud SQL Postgres is not required for the current deployment.
- `reference/dbt/profiles.yml` still contains a Postgres placeholder profile for future migration.

## Optional Cloud SQL variables

If you later migrate to Cloud SQL, these variables are relevant:

- `AGENTINVEST_PG_HOST`
- `AGENTINVEST_PG_PORT`
- `AGENTINVEST_PG_USER`
- `AGENTINVEST_PG_PASSWORD`
- `AGENTINVEST_PG_DBNAME`
- `AGENTINVEST_PG_SCHEMA`

## Optional dbt production profile

The `prod` target in `reference/dbt/profiles.yml` is a future-ready placeholder; the current deployment remains DuckDB-first.
