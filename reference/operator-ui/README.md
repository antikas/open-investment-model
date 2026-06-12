# agentINVEST Operator UI — v0.1 (thin slice)

A small Next.js + Tailwind operator console for the four surfaces of the
agentINVEST reference implementation:

- **Approvals queue** — lists the high-stakes operations paused for a decision and lets
  the operator **approve** (proceed) or **reject** (abort, no publish) with a reason. The
  decision is recorded at the engine's awakeable — the gate's own path of record.
- **Operations** — read-only: the operations the engine has run, each with its recorded
  audit trail (the `operation-closed` audit record / the NAV publish record).
- **Deployments** — read-only: the registered deployments and services, with the
  in-flight-operation count correlated by service.
- **Canonical-data inspector** — read-only: the dbt marts and realised staging entities,
  with row counts and a capped sample per table (allowlisted table names, a parameterised
  capped sample — no free-form SQL).

## How it reads the engine

The pages fetch on the **server** from the local engine:

- the **admin API** (`http://127.0.0.1:9070`) — registered services + invocation
  introspection;
- the **ingress** (`http://127.0.0.1:8080`) — the pending-approvals registry reader, each
  operation's recorded `status`, and the awakeable resolve.

No engine URL or key reaches the browser — the data layer (`src/lib/restate.ts`) is
`import 'server-only'`, so a build fails loudly if it is ever pulled into a client bundle.

The pending-approvals list is a **real** source: it reads a small pending-approvals
registry that the high-stakes gate records each notice in (the gate's own pause / resolve /
timeout behaviour is unchanged — the registry is a passive read mirror, never a second
control path). **Each pending row is a live operation paused at the gate.** The list keeps
that true on every resolution path: the gate marks an entry resolved when the operation
approves, rejects or times out (so an out-of-band resolve — a CLI/raw-ingress decision or a
durable timeout — also leaves the queue, not just a decision made in this UI), and the list
reader reconciles each pending row against the operation's actual recorded state and ages
out any whose operation has already finished or gone. Acting on a row whose operation is no
longer suspended is refused honestly ("no longer pending") and records nothing.

## Posture (v0.1)

- **No app-layer sign-in.** A single operator on a trusted localhost; a network boundary
  (a Tailscale ACL) is the access control, applied at the deploy step (a forward item). The
  dev UI is unauthenticated on localhost — correct for the single-operator workstation, not
  a production auth posture.
- **Synthetic data**, **local**. All four pages — Approvals, Operations, Deployments and
  the canonical-data inspector — are built.

## Run

```sh
# from reference/ — the engine must be up (pnpm dev:restate) and the agentINVEST
# handlers registered (the endpoint, or a proof endpoint, must be running).
pnpm operator-ui:dev      # http://localhost:4180
pnpm operator-ui:build    # production build + type-check
```

Override the engine URLs with `RESTATE_ADMIN_URL` / `RESTATE_INGRESS_URL` if they differ.
