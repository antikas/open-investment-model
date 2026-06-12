# agentINVEST — canonical data layer (dbt)

Builder-facing runbook for the agentINVEST **canonical data layer**: a dbt
project on the duckdb dev backend (dbt-postgres in production), per the
project's stack-and-topology decision record.
This is the dbt-managed system of record the typed tool surface
reads from; it is a **dbt store**, not an "agent" (the project's topology
vocabulary — the per-Business-Domain layer is a model-free Restate *service*;
there is one orchestrating loop).

> This is a builder document. The reader-facing description of agentINVEST lives
> in `../README.md` and stays clean of build/runbook detail.

## What is here (the scaffold floor + the canonical entities)

The **scaffold floor** (the sample pipeline) plus the **canonical
data contract**: the first ten BD-09 entities as staging models, seeds and tests.

```
reference/dbt/
  dbt_project.yml                 # project config; staging/intermediate/marts dirs
  profiles.yml                    # duckdb dev (default) + postgres prod PLACEHOLDER
  models/
    staging/
      stg_sample_holdings.sql     # ONE sample staging model (generic, NOT a BD-09 entity)
      stg_e01_legal_entity.sql    # E-01 ... E-20, each cross-checked vs model/entities/core/E-NN-*.md
      stg_e02_instrument_asset.sql
      stg_e03_portfolio_mandate.sql
      stg_e04_holding_position.sql   # KEY-PARTITIONED by `book` (dual-book ownership)
      stg_e07_valuation.sql          # as-of/append-only — grain declared (see Bi-temporal grain below)
      stg_e09_asset_class.sql
      stg_e13_entity_alias.sql       # as-of/append-only
      stg_e14_external_identifier.sql
      stg_e19_risk_measurement.sql   # as-of/append-only
      stg_e20_performance_result.sql # as-of/append-only
      schema.yml                  # dbt tests per entity (unique/not_null/accepted_values per the model file)
    intermediate/                 # the bi-temporal log models (see How this extends)
    marts/                        # the mart models (see How this extends)
  seeds/
    raw_sample_holdings.csv       # sample seed (6 rows)
    raw_e01_legal_entity.csv      # ten minimal flat sample seeds (extended by the full synthetic dataset)
    raw_e02_instrument_asset.csv  # ...
    (raw_e03 ... raw_e20)
  tests/
    assert_e04_position_book_unique.sql   # the E-04 (position_id, book) composite-key invariant
  macros/  snapshots/  analyses/  (.gitkeep)  # empty — later items
  README.md                       # this file
```

The Pydantic schemas live in the Python workspace at
`reference/python/src/agentinvest_canonical_model/` (the seed of a later
`@agentinvest/canonical-model` package), with the **schema-drift check**
that keeps the schemas in lock-step with the model files (see below).

**Deliberately NOT in the scaffold floor** (it landed, or lands, as later items —
see *How this extends*):
- the remaining ~63 entities — later items;
- the full synthetic dataset (~5000 rows across BD-09 entities);
- the intermediate + mart models (`mart_fund_nav`, etc.);
- the bi-temporal **materialisation** strategy (snapshot/incremental) for the
  as-of/append-only entities (see *Bi-temporal grain* below).

The sample model is retained (it proves `seed -> staging view -> tests`
runs green and idempotently). Later items drop their models/seeds into the
folders above without moving any existing file.

## The canonical data contract (ten BD-09 entities)

Each of E-01 / E-02 / E-03 / E-04 / E-07 / E-09 / E-13 / E-14 / E-19 / E-20 is
realised as: a typed Pydantic schema (the Python workspace), a `stg_<entity>.sql`
staging view (here), a minimal flat sample seed, and dbt tests (the
key/unique/not-null invariants the model file implies). **The OpenIM model files
(`model/entities/core/E-NN-*.md`) are the single source of truth** — each schema
is column-faithful to its model file's *Attribute schema* table.

### Schema-drift check

The schema-drift validator lives at
`reference/python/src/agentinvest_canonical_model/drift.py`. It parses each
realised entity's model-file *Attribute schema* table and cross-checks it against
the Pydantic schema, failing on any drift (a missing, renamed or retyped column).
Run it:

```sh
cd reference/python
uv run --group dbt python -m agentinvest_canonical_model.drift   # PASS/FAIL, exit 0/1
# or pytest-hosted:
uv run --group dbt pytest tests/test_canonical_drift.py
```

It is scoped to the realised entities (NOT a general 73-entity parser —
generalising is a later item). **CI residual:** it is CI-ready but not yet *wired into* CI, because
`reference/` has no CI runner yet (the same residual documented for the
launcher's Linux-CI branch); it runs in the local toolchain and in pytest today.

### Parity-aware SQL (the prod-cutover risk)

The ten staging models avoid duckdb-only idioms the dbt-postgres prod target
can't render. Specifically: money/quantity columns cast to `decimal(p,s)` (NOT
duckdb's bare `double` — the sample model's `double` cast is a duckdb-only idiom
**noted for the parity register**); the `float` confidence columns cast to
`double precision` (portable, unlike bare `double`); identifiers/dates use
`varchar`/`date`. No duckdb-only idiom remains in the canonical models. The prod
postgres target is still never parsed (parity stays *untested* until a later item
integration-tests both backends) — but the SQL is written to render on both.

### Bi-temporal grain — declared; materialisation decided with the full dataset

E-07 Valuation, E-19 Risk Measurement and E-20 Performance Result are
**as-of / append-only** entities (the computed-metric-as-entity shape): a
restatement for a prior date/period is a NEW row, never an
overwrite. Their **bi-temporal grain is declared** — the as-of columns
(`valuation_date`, `as_of_date`, `period_start`/`period_end`) are on the schema and
in each Pydantic schema's `GRAIN`, and the sample seeds carry multi-as-of
trajectories (e.g. POS-0005's valuation has marks at two dates plus a same-date
model mark).

**The materialisation *strategy* is NOT picked here — it is a named
coordination point.** These staging models are
**views** (the staging default), NOT dbt snapshots or incremental models. Whether
the as-of/append-only entities materialise as dbt snapshots (SCD-2), incremental
appends, or views over an append-only seed is decided with the
full ~5000-row bi-temporal seed in hand. The scaffold deliberately does **not**
silently inherit the sample pipeline's flat drop-recreate as the forever strategy — it
declares the grain and seeds flat, and surfaces the decision.

### E-04 key-partitioned by `book`

E-04 is one entity, key-partitioned by `book`: SD-12.1 IBOR owns `book = ibor`,
SD-12.2 ABOR owns `book = abor`, co-equally. `book` is part of identity, so the
sample seed carries IBOR/ABOR *pairs* that genuinely diverge (POS-0005/0006's
market values differ), and the composite-key invariant `(position_id, book)`
unique is asserted by `tests/assert_e04_position_book_unique.sql` (a singular
test — no `dbt_utils` dependency; parity-aware SQL).

### The dual-book extension (landed)

The reconciliation build extended the contract the same way: E-05 Transaction and
E-06 Cash Flow Event staging models + seeds; the external comparator feeds the
reconciliation engine reads (`stg_custodian_holdings` / `stg_custodian_cash` /
`stg_admin_statement`); and the labelled-break oracle the engine is scored
against (`stg_break_labels` — it labels the feed, it is not part of the book).
Thirteen canonical entities are realised in the Pydantic package today (including
E-24 Reconciliation Break — whose persisted break store is engine-owned and
deliberately NOT a dbt model).

## Prerequisites

- The Python uv env synced with the **dbt** dependency group (the dbt toolchain
  lives in `reference/python/`, not a separate venv):
  ```sh
  cd reference/python && uv sync --group dbt    # (inside WSL2 on Windows)
  ```
- On Windows, this runs **inside WSL2** — the same Linux env the Python tool
  layer and the Restate server run in. dbt + duckdb are Linux-native
  and the duckdb file lands on WSL2 ext4 (see *Where the duckdb database file
  lands* below).

## Run it

From `reference/` (Windows host or native Linux/Mac):

```sh
pnpm dbt:build                 # node scripts/dbt-build.mjs -> dbt build (seed + run + test)
# forward args to dbt:
node scripts/dbt-build.mjs --select staging
node scripts/dbt-build.mjs seed        # seed only
```

Or through the operator CLI (the `seed` subcommand is real, and
`bootstrap`'s data-half runs the same build):

```sh
cd reference/ts
npx tsx src/cli/agentinvest-cli.ts seed          # = dbt build
npx tsx src/cli/agentinvest-cli.ts bootstrap     # substrate proof + dbt build
npx tsx src/cli/agentinvest-cli.ts bootstrap --skip-data   # substrate proof only
```

A green run ends with `Done. PASS=… WARN=0 ERROR=0 SKIP=0` (the node count grows
with the data — the seed, staging, bi-temporal intermediate models and their tests).
The dbt **pipeline** runs in ~13–14s (well under the 30s budget); see *Performance
note* for the pipeline-vs-cold-import distinction.

## Where the duckdb database file lands (ext4, NOT the 9p mount)

**Decision:** the duckdb **database file** lands on **WSL2-native
ext4**, at:

```
$HOME/.local/share/agentinvest/duckdb/canonical.duckdb
# (resolved inside WSL2 on Windows; the local filesystem on native Linux/Mac)
```

It is **NOT** on the 9p `/mnt/d` repo mount.

**Why.** duckdb on a 9p mount is a known **locking + performance hazard**: 9p
does not honour the POSIX file-locking duckdb relies on for its single-writer
guarantee, and read/write throughput across the 9p boundary is poor. The Python
+ dbt layer already runs in WSL2, so ext4 is local and fast there.

**Why `~/.local/share/...` and not `/var/lib/agentinvest/duckdb/`**: `/var/lib`
is a system-service location that needs
root/sudo to create and is the right home for a *production daemon's* data. For a
single-operator **dev** duckdb file, the XDG data dir (`~/.local/share`,
[XDG Base Directory spec]) is the idiomatic, no-privilege-escalation placement,
created automatically by the build script. The dev→prod path is documented
(prod is **postgres**, not a dev duckdb file on `/var/lib` — see *Dev→prod path*
below), so nothing depends on the dev path matching the prod service path.

**How the source-in-repo / db-on-ext4 split works.** The dbt *source* (this
README, `dbt_project.yml`, `profiles.yml`, `models/`, `seeds/`) stays in the repo
at `reference/dbt/` (on `/mnt/d` — version-controlled). Only the *materialised
output* — the duckdb file and dbt's `target/`/`logs/` — is generated; the duckdb
file goes to ext4 and is **gitignored** (`*.duckdb`, `dbt/target/`, `dbt/logs/`).
`scripts/dbt-build.mjs` sets `DBT_PROFILES_DIR` to this directory (so a fresh
checkout needs no `~/.dbt/profiles.yml`) and `mkdir -p`s the ext4 directory
before dbt connects. dbt reads its project from `/mnt/d` and writes its database
to ext4 — the split is clean.

**Checkout-keyed default + override.** When invoked through a launcher
(`scripts/dbt-build.sh`, and so `pnpm dbt:build` / `agentinvest-cli seed`), the
duckdb path is **keyed on this checkout's repo root** —
`~/.local/share/agentinvest/duckdb/canonical-<token>.duckdb`, the same `<token>`
that keys the venv — so two checkouts/worktrees (or a CI matrix) get distinct
duckdb files and never collide on duckdb's single-writer file lock. Set
`AGENTINVEST_DUCKDB_PATH` (an absolute path) to override (a CI runner or an
isolated audit pins its own file); the `profiles.yml` `env_var()` literal
(`…/canonical.duckdb`) is only the fallback for a bare `dbt` run that did not go
through a launcher.

**Recovering from a stale duckdb (seed/model reshape).** The duckdb file is
gitignored output that lives outside the repo, so a clean checkout has none and
the first `dbt build` creates it fresh. If you reshape a **seed** CSV (add/rename
a column) against an **already-persisted** duckdb, dbt-duckdb's seed loader fails
loud (a red `ERROR loading seed file …`, non-zero exit — never silent
corruption) because the cached column-spec no longer matches the wider CSV. The
recovery is one line — delete the gitignored duckdb and rebuild fresh:

```sh
rm -f "${AGENTINVEST_DUCKDB_PATH:-$HOME/.local/share/agentinvest/duckdb/}"*.duckdb
pnpm dbt:build        # rebuilds the database from scratch -> PASS
# or, narrower: node scripts/dbt-build.mjs seed -- --full-refresh
```

**Proof the file is on ext4 (not 9p):**
```sh
wsl -e bash -c 'ls "$HOME/.local/share/agentinvest/duckdb/"*.duckdb | head -1 | xargs -I{} sh -c "realpath {}; df -T {} | tail -1"'
# -> $HOME/.local/share/agentinvest/duckdb/canonical-<token>.duckdb
# -> /dev/sdX  ext4  ...  /         (NOT a /mnt/* 9p line)
```

## Dev → prod path

- **dev** — `dbt-duckdb`, in-process, the duckdb file on ext4 (above). The
  default target.
- **prod** — `dbt-postgres` (the `prod` target in `profiles.yml`). A
  **placeholder**: it documents the path and need not connect for this scaffold.
  Its connection params are env-var driven (`AGENTINVEST_PG_*`), so no
  credentials are committed. Production co-locates the canonical store with
  Restate's Postgres backend but in a **separate schema**
  (`agentinvest_canonical.*`), distinct from Restate's own backend schema.

dbt model behavioural drift between duckdb and postgres is a known risk;
the mitigation is to test the marts against
both backends before any prod cutover (a named later item).

## The dev environment, plainly

- **No Docker.** The Restate server is a single pinned binary run **directly
  inside WSL2** (on Windows) by the project's own launcher
  (`reference/scripts/run-restate-server.mjs`); the TS endpoint is a Node
  process on the host; the Python + dbt layer runs in the WSL2 uv env.
  No containers, no compose file.

- **The canonical data store is distinct from Restate's own backend.** These are
  two different databases for two different jobs:
  - **Restate backend** — the durable-execution journal + virtual-object state.
    sqlite in dev; its own Postgres DB in prod.
  - **agentINVEST canonical data** — the dbt-managed system of record (entities,
    marts). A duckdb file on ext4 in dev; an `agentinvest_canonical.*` schema on
    the prod Postgres cluster in prod.

  In dev the canonical store is duckdb, full stop — it needs no separate
  Postgres "for isolation"; that is a production posture.

## How this extends

- The ten BD-09 entity staging models
  (`stg_e01_legal_entity` … `stg_e20_performance_result`, landed) sit beside
  `stg_sample_holdings.sql`, each cross-checked against
  `model/entities/core/E-NN-*.md` by the schema-drift check, plus their Pydantic
  schemas (`reference/python/src/agentinvest_canonical_model/`) and per-entity
  seeds + tests. See *The canonical data contract* above.
- The realistic synthetic dataset (landed) spans the ten BD-09
  entities (the three funds — see `seeds/README.md`), with the **bi-temporal
  materialisation** of the three append-only entities (Valuation, Risk Measurement,
  Performance Result) as the `int_e07/e19/e20_*` models in `intermediate/` — an
  append-only log (incremental) plus derived system-time bounds, exposing current
  and as-of-knowledge access. The `intermediate` model-config block is now live in
  `dbt_project.yml`.

  > **dbt mental-model note — the bi-temporal logs are incremental and append-only.**
  > A re-run of `dbt build` appends each NEW append-only row (a new
  > `valuation_id` / `measurement_id` / `performance_result_id`) exactly once and
  > appends nothing on an idempotent re-run. A correction is therefore a **new
  > row with a new id**, never an in-place rewrite — which matches the model's own
  > append-only semantics. The corollary surprises the standard view-materialised
  > mental model: editing an **existing** seed row in place (same id, changed
  > value) is **ignored** by the incremental log on re-run (the
  > `where … not in {{ this }}` guard skips an already-loaded id). Use
  > `dbt build --full-refresh` (or the stale-duckdb rebuild above) to re-load the
  > log from a corrected seed.
- The marts (`mart_portfolio_holdings`, `mart_fund_nav`,
  `mart_performance_appraisal`) land in the `marts/` folder, with invariant tests
  (e.g. NAV = sum of position values − fees). The `marts` model-config block
  (commented in `dbt_project.yml`) is uncommented when the first mart arrives.

The shadow-accounting pattern this project will carry
doubles as an eval oracle, so correctness and
idempotence matter more than breadth — hence the scaffold floor proves the
pipeline, not the BD-09 data.

## Performance note (pipeline time vs cold import)

Two distinct timings, both within budget:

- **The dbt pipeline** (seed + run + test of the full canonical layer — now ~166
  nodes including the ~5000-row synthetic dataset and the bi-temporal intermediate
  models) runs in **~13–14s** on a typical dev machine (the `dbt … in N seconds` line).
  This is the figure the `< 30s` gate is worded against — and it is comfortably
  under it.
- **The dbt cold import** (importing dbt-core + its adapters + the macro tree
  before the pipeline starts) was the old ~40s 9p-venv tax; moving the uv
  venv to WSL2-native ext4 cut the cold `dbt --version` to ~4s. The venv is now
  also keyed per checkout so concurrent checkouts / CI do not share one
  venv — still on ext4, so the perf win is preserved (see
  `scripts/lib/agentinvest-venv-path.sh`).

So the `< 30s` budget is met on pipeline time with wide margin; the import cost is
separate and already paid down.

[XDG Base Directory spec]: https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html
