# agentINVEST — TypeScript reference surface (workspace package)

Builder-facing runbook for the agentINVEST **TypeScript** package — the
orchestrator/control-surface side of the polyglot workspace: the operator CLI
(`agentinvest-cli`), the Restate handler endpoint, and the TS side of the
cross-language RPC seam. The Python tool+data layer is a sibling package at
`../python` (see its own README); OpenIM's OWN Restate substrate launcher lives
at `../scripts` + `../config`.

> This is a builder document. The reader-facing description of agentINVEST lives
> in `../README.md` and stays clean of build/runbook detail.

## The substrate: OpenIM owns its launcher, shares the running instance

agentINVEST owns its Restate **substrate launcher, installer, config and version
pin** (`../scripts/run-restate-server.mjs`, `../scripts/install-restate.mjs`,
`../config/restate-dev.toml`). A fresh OpenIM checkout boots its substrate with
OpenIM's OWN scripts and **never reads another project's source files**. At dev
time the *running* instance may be shared with another local project using the
same dev substrate — same
pinned binary, same ports, one journal, no second cluster — but the version
contract is OpenIM's.

On a typical Windows dev setup the reach mechanism is:

- `restate-server` (pinned v1.6.2, installed into `../tools/` by OpenIM's own
  installer) runs **inside WSL2** (the Linux-musl binary). Its admin API is on
  `127.0.0.1:9070` and its HTTP ingress on `127.0.0.1:8080`, both visible from
  the Windows host via WSL2's localhost-forwarding.
- The agentINVEST handler endpoint runs in a Node process **on the Windows host**
  (port `9090`). For Restate-inside-WSL2 to call back into it, the endpoint is
  registered at the **WSL2 default-gateway IP** (the Windows host as seen from
  inside WSL2), discovered automatically. On Mac/Linux there is no WSL2 layer and
  `localhost` is used throughout.

## Package manager — pnpm (workspace)

This workspace uses **pnpm** — one
lockfile at `../pnpm-lock.yaml`, no per-package `package-lock.json`; the clean
way to tie the TS packages together as more are added. Install from the
workspace root:

```sh
cd reference
pnpm install               # installs all workspace packages (ts/ here)
```

> pnpm forwards `--` literally to scripts, so for the CLI's top-level help use
> `pnpm agentinvest --help` (no extra `--`). Subcommand help is
> `pnpm agentinvest bootstrap --help` etc., or `npx tsx src/cli/... --help`.

## Prerequisites

- Node ≥ 22 (this repo is developed against v22.x) + pnpm.
- The Restate substrate running (see next section — OpenIM's OWN launcher).
- On Windows: WSL2 with a registered distro (discovered automatically; override
  with `RESTATE_WSL_DISTRO`). The Linux-musl restate-server runs there.

## Step 1 — start the substrate with OpenIM's OWN launcher

```sh
# Windows / Mac / Linux — warm boot is < 5s once the binary is present.
cd reference
pnpm dev:restate           # OpenIM-owned: installs (pinned) + holds restate-server; Ctrl-C to stop
```

The first run downloads + SHA-verifies + installs the pinned `restate-server`
binary into `../tools/` (gitignored). On a TLS-interception workstation set
`NODE_EXTRA_CA_CERTS` to the intercepting root CA so the download trusts the
chain.

The server is ready when `http://localhost:9070/health` returns HTTP 200:

```sh
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:9070/health   # -> 200
```

If the admin port does not answer from the Windows host: check the WSL2 networking
mode with `wsl -d <distro> -- wslinfo --networking-mode` (`mirrored` avoids the
cold-forwarding flakiness `NAT` localhost-forwarding can show), then restart
**only** Restate with `pnpm dev:restate` (idempotent, leaves WSL up).
**⚠️ NEVER `wsl --shutdown`** — the dev Restate server may be **shared with other
local projects**; a shutdown kills another project's server mid-flight. Never
kill the WSL VM as a recovery step — restart **only** the Restate process
(`pnpm dev:restate`).

## Step 2 — install + prove the substrate (from this directory)

```sh
cd reference
pnpm install               # one-time; fetches @restatedev/restate-sdk + tsx + toolchain

pnpm -C ts bootstrap       # the end-to-end proof (see below)
# or: cd ts && npx tsx src/cli/agentinvest-cli.ts bootstrap
```

`bootstrap` does the load-bearing proof:

1. waits for the shared Restate admin API;
2. starts the agentINVEST handler endpoint (port 9090; binds `0.0.0.0` on
   Windows so Restate-in-WSL2 can reach it);
3. registers the endpoint with the shared Restate (admin `/deployments`);
4. invokes `agentinvestPlaceholder/ping` (baseline) — expects `attempts=1`;
5. invokes it again with a forced crash — expects `attempts=2` and the **same
   journaled step-id** (the journal-replay proof);
6. invokes `agentinvestPlaceholder/health` over the ingress;
7. runs the canonical-data `dbt build` (the data half: seed
   + staging + tests on the duckdb dev backend), then exits 0.

## The CLI — `agentinvest-cli`

```sh
pnpm agentinvest --help           # top-level help (pnpm forwards -- literally)
pnpm -C ts bootstrap              # the substrate proof + dbt data-half (above)
pnpm -C ts seed                   # build the canonical data layer (dbt build)
pnpm -C ts serve                  # start + register the endpoint, hold it running
```

Every subcommand has its own `--help`:

```sh
npx tsx src/cli/agentinvest-cli.ts bootstrap --help
npx tsx src/cli/agentinvest-cli.ts seed --help
npx tsx src/cli/agentinvest-cli.ts serve --help
```

| Subcommand | At the floor | Owned later by |
|---|---|---|
| `bootstrap` | substrate proof (live) + dbt data-half (live) | extended by the typed tool surface |
| `seed`      | runs `dbt build` over `reference/dbt/` (live) | the full synthetic seeds + marts |
| `serve`     | starts + registers the handler endpoint (live) | extended by the orchestrator handlers |

## Invoke the placeholder by hand (optional)

With the endpoint registered (after `bootstrap --keep-serving` or `serve`):

```sh
curl -s -X POST http://localhost:8080/agentinvestPlaceholder/ping \
  -H 'content-type: application/json' -d '{"crashOnFirstAttempt":false}'
# -> {"stepId":"<uuid>","attempts":1,"service":"agentinvestPlaceholder"}

curl -s -X POST http://localhost:8080/agentinvestPlaceholder/health \
  -H 'content-type: application/json' -d '{}'
# -> {"ok":true,"service":"agentinvestPlaceholder"}
```

The Restate web UI (journal inspector) is at `http://localhost:9070/`.

## Toolchain (lint / type-check / test) — all green

```sh
pnpm -C ts lint            # eslint (type-aware over src/**)
pnpm -C ts type-check      # tsc --noEmit
pnpm -C ts test            # vitest (unit tests under src/**/*.test.ts)
```

## The cross-language RPC smoke (TS ↔ Python) — the load-bearing proof

A TypeScript orchestrator handler invokes the Python `pyTools/computeSimpleReturn`
tool over Restate's **typed** RPC; the payload round-trips as a typed structure.
This is the seam every later Python-tool-from-TS-orchestrator call rides on.

One command, from a fresh checkout (with the substrate up via `pnpm dev:restate`):

```sh
cd reference
pnpm smoke:cross-language   # starts the Python endpoint (in WSL2), runs the TS→Python proof, tears down
```

What it proves (asserted, not just printed): the TS handler reaches into the
Python service over Restate, the typed result comes back with
`computedBy: "python:pyTools"` (a marker only the Python service can set, so the
boundary was genuinely crossed) and the maths is correct. See
`src/rpc/py-tools-contract.ts` (the shared typed contract) and
`src/rpc/cross-language-smoke.ts` (the TS side). The Python endpoint runs inside
WSL2 because the Restate Python SDK is Linux-native (no Windows wheel) — that is
the decided polyglot placement, not a workaround; see `../python/README.md`.

## Configuration (env overrides)

| Var | Default | Notes |
|---|---|---|
| `RESTATE_ADMIN_URL` | `http://localhost:9070` | shared Restate admin API |
| `RESTATE_INGRESS_URL` | `http://localhost:8080` | shared Restate HTTP ingress |
| `AGENTINVEST_ENDPOINT_PORT` | `9090` | the TS handler endpoint port (distinct from other local Restate endpoints) |
| `AGENTINVEST_PY_ENDPOINT_PORT` | `9091` | the Python handler endpoint port (its own registration, distinct from the TS endpoint's) |
| `AGENTINVEST_SMOKE_TS_PORT` | `9092` | the cross-language smoke's own TS endpoint port |
| `AGENTINVEST_ENDPOINT_BIND` | `127.0.0.1` (auto `0.0.0.0` on Windows) | endpoint bind host |
| `AGENTINVEST_ENDPOINT_DEPLOY_URL` | (auto: WSL2 gateway IP on Windows) | explicit register URL override |
| `RESTATE_WSL_DISTRO` | (discovered; first installed distro) | which WSL2 distro Restate runs in (Windows only) |

## Directory shape (and how it extends)

```
reference/
  README.md            # reader-facing surface (kept clean)
  package.json         # pnpm workspace root + substrate scripts (dev:restate, smoke:cross-language)
  pnpm-workspace.yaml  # workspace manifest (packages: ts, operator-ui)
  config/
    restate-dev.toml   # OpenIM-owned Restate config
  scripts/
    install-restate.mjs        # OpenIM-owned installer (pinned v1.6.2)
    run-restate-server.mjs     # OpenIM-owned launcher
    smoke-cross-language.mjs   # one-command TS↔Python RPC smoke orchestrator
  tools/               # downloaded Restate binaries (gitignored)
  ts/                  # THIS — the TS orchestrator/control-surface package
    src/
      cli/agentinvest-cli.ts        # operator CLI (bootstrap / seed / serve)
      substrate/
        restate-reach.ts            # substrate reach + WSL2 deploy-URL + 2nd-endpoint port
        endpoint.ts                 # binds handlers, serves the endpoint
        placeholder-service.ts      # the single placeholder Restate service
      orchestrator/                 # the InvestmentOperation virtual object (the one loop),
                                    # the NavCalculationWorkflow, the approval gate + registry
      audit/                        # hash-chained audit-journal export + tamper-detecting verifier
      rpc/
        py-tools-contract.ts        # shared TYPED cross-language contract (TS side)
        cross-language-smoke.ts     # TS orchestrator that calls Python over typed RPC
  python/              # the Python tool+data package (uv-managed) — see ../python/README.md
```

Designed so later items extend rather than move these files — and they have:

- The **canonical data layer** (`reference/dbt/`) sits beside `python/`; the
  `seed` subcommand drives real dbt-driven seeding.
- The typed per-Service-Operation tool surface rides the cross-language RPC seam
  proved here: the BD-09 performance/return tools, the BD-12 IBOR/ABOR read
  tools and the SD-12.10 reconcile tools are hosted by the Python-side `bd09` /
  `bd12` / `bd12Recon` services, beside the original `pyTools` sample.
- The **orchestrator** (the `InvestmentOperation` virtual object) is bound in
  `substrate/endpoint.ts` and its full loop — plan → resolve → dispatch →
  approve → aggregate → close — is built, alongside the `NavCalculationWorkflow`
  (the NAV strike with the approval gate at publish).
- Shared TS lifts into `@agentinvest/canonical-model` /
  `@agentinvest/runtime` packages beside `ts/` — the pnpm workspace already
  supports it.

Nothing here is named "agent": the per-Business-Domain layer is a model-free
Restate *service*; the single orchestrating loop is the orchestrator's `.plan()`
step. The placeholder service carries no reasoning loop.
