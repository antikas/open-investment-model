# agentINVEST — Python tool + data layer (workspace)

Builder-facing runbook for the agentINVEST **Python** workspace: the tool +
data-layer side of the project's decided polyglot split (TypeScript orchestrator /
control surfaces; Python tools + data). This workspace is `uv`-managed.

> This is a builder document. The reader-facing description of agentINVEST lives
> in `../README.md` and stays clean of build/runbook detail.

## Why uv, and why it runs inside WSL2 on Windows

**Dependency manager — uv.** Single fast tool for the virtualenv, dependency
resolution and the lockfile; already on the workstation; resolves and installs
the Restate Python SDK + dev toolchain in one command. (Poetry is the
alternative; it is not installed here, and uv subsumes its role with less
ceremony.)

**Where it runs.** On Windows the Python workspace runs **inside WSL2**, the same
Linux environment the Restate server runs in. This is not a workaround — it is
the decided polyglot placement: the financial-data Python ecosystem (and the
Restate Python SDK) is Linux-native. The Restate Python SDK ships only as a
Linux/macOS wheel (`manylinux` / `apple-darwin`); there is no Windows wheel, and
its source build needs a Rust toolchain. Inside WSL2 the wheel installs in
milliseconds with no build step. The Python Restate endpoint therefore runs
inside WSL2 and is reached by the WSL2-resident Restate over `localhost`. On
native Mac/Linux there is no WSL2 layer; everything is local.

## Prerequisites

- `uv` (https://docs.astral.sh/uv/). On Windows, install it **inside WSL2**:
  `curl -LsSf https://astral.sh/uv/install.sh | sh`.
- The shared Restate substrate running (OpenIM-owned launcher — see
  `../ts/README.md` step 1: `cd reference && pnpm dev:restate`).

## Toolchain (lint / type-check / test) — all green

Run these from `reference/python/` (inside WSL2 on Windows):

```sh
uv sync                       # create the venv + install deps from uv.lock
uv run ruff check .           # lint
uv run mypy                   # type-check (strict)
uv run pytest                 # test
```

`uv run ruff format --check .` checks formatting; `uv run ruff check . --fix`
applies lint fixes.

## The cross-language RPC smoke (TS ↔ Python)

The load-bearing cross-language proof: a TypeScript orchestrator handler invokes this
workspace's Python `pyTools/computeSimpleReturn` tool over Restate's typed RPC,
the payload round-tripping as a typed structure. See `../ts/README.md` for the
single command that runs the whole round-trip from a fresh checkout, and
`src/agentinvest_tools/py_tools_service.py` for the Python handler.

```sh
# Python side of the smoke (started by the smoke runner; shown for reference):
uv run python -m agentinvest_tools.endpoint     # serves pyTools on :9091
```

## Directory shape (and how it extends)

```
reference/python/
  pyproject.toml                 # uv project: deps (restate-sdk, pydantic) + ruff/mypy/pytest + dbt group
  uv.lock                        # the single Python lockfile
  src/agentinvest_tools/
    sample.py                    # pure compute (compute_simple_return) + its types
    py_tools_service.py          # the typed Restate `pyTools` service (cross-lang seam)
    bd09/                        # the five BD-09 performance/return tools (SO-09-01…05)
    bd12/                        # the BD-12 IBOR/ABOR book-of-record read tools
    bd12_recon/                  # the four SD-12.10 reconcile tools + the append-only break store
    bd09_service.py / bd12_service.py / bd12_recon_service.py
                                 # the model-free per-BD Restate dispatch services
    arg_resolver_service.py      # the orchestrator's resolve seam (marts-read, deterministic)
    nav_data_service.py / canonical_data_service.py
                                 # read-only marts/canonical-data seams (NAV workflow, operator UI)
    mcp_server.py                # the MCP face over the bd09/bd12/bd12Recon catalogues
    openapi_surface.py           # the self-served OpenAPI 3.1 surface
    endpoint.py                  # serves the Python endpoint, registers against Restate
  src/agentinvest_orchestrator/  # the planner (the one LLM loop) + plan schema + tool catalogue
  src/agentinvest_canonical_model/  # the @agentinvest/canonical-model package seed
    base.py                      # CanonicalEntity base + the ownership patterns
    entities.py                  # the thirteen canonical Pydantic schemas (E-01 … E-24), model-file-faithful
    drift.py                     # the schema-drift check — fails on model-file divergence
  src/agentinvest_evals/         # the eval harness (see ../evals/README.md)
  src/agentinvest_demo/          # demo / data-access helpers (marts, dual book, comparator feeds)
  tests/                         # pytest suites over the tools, services, schemas, drift and evals
```

- The **canonical data layer** (`reference/dbt/`) sits beside this; the
  Python tools read from it.
- The `agentinvest_canonical_model` package carries the typed
  Pydantic schemas for the thirteen realised canonical entities (the seed of a
  later `@agentinvest/canonical-model` package) and the schema-drift check that
  keeps them in lock-step with `model/entities/core/E-NN-*.md`. The drift check
  reads the model files relative to the repo root and needs the `dbt` group only
  if invoked through the dbt-build path; standalone it runs in the base venv. Run
  it with `uv run --group dbt python -m agentinvest_canonical_model.drift`.
- The full synthetic dataset, the bi-temporal materialisation and the typed
  per-Service-Operation tool surface are in place: the BD-09 performance/return
  tools, the BD-12 IBOR/ABOR read tools and the SD-12.10 reconcile tools, each
  hosted by its model-free dispatch service (`bd09` / `bd12` / `bd12Recon`).

Nothing here is named "agent": `pyTools` is a model-free Restate *service* — a
namespace + dispatch boundary — never an "agent" and carrying no reasoning loop.
