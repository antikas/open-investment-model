# Secret Manager for agentINVEST

Use Secret Manager to store the following values for the current Cloud Run deployment:

- `ANTHROPIC_API_KEY` or Vertex AI credentials
- `RESTATE_ADMIN_URL`
- `RESTATE_INGRESS_URL`
- any other runtime secrets required by the services

## Optional Postgres secrets

These values are only required if you later migrate to Cloud SQL:

- `AGENTINVEST_PG_HOST`
- `AGENTINVEST_PG_PORT`
- `AGENTINVEST_PG_USER`
- `AGENTINVEST_PG_PASSWORD`
- `AGENTINVEST_PG_DBNAME`
- `AGENTINVEST_PG_SCHEMA`

## Best practices

- Use IAM bindings with least privilege.
- Grant Cloud Run service accounts access to only the secrets they need.
- Do not store secrets in plaintext in container images or ConfigMaps.
