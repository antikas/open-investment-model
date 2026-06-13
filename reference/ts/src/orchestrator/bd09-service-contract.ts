/**
 * Typed cross-language RPC contract for the `bd09` dispatch service (the seam-2 target).
 *
 * The TS↔Python seam the orchestrator's seam-2 DISPATCH step runs over: each plan
 * step is executed by calling the Python `bd09.execute_so` handler over Restate's
 * typed RPC (the same `ctx.serviceClient(...)` path the planner contract and the
 * `pyTools` contract use). The TS side does NOT import Python — it declares a
 * type-only service-definition handle describing the service name + the
 * `execute_so` handler's typed I/O, and `ctx.serviceClient(BD09_SERVICE)` gives a
 * typed client routed to the Python service.
 *
 * Handler name discipline. The wire routing key is the name the Python side
 * REGISTERS the handler under: `bd09_service.py` registers it as
 * `@bd09.handler(name="execute_so")`, so the on-the-wire path is
 * `/bd09/execute_so` and the typed handle keys it `execute_so` (snake_case, as
 * registered) — NOT a camelCased `executeSo`. The orchestrator therefore calls
 * `ctx.serviceClient(BD09_SERVICE).execute_so({ soId, args })`. (A camelCased
 * `.executeSo(...)` shorthand is the same logical call; the registered wire name is
 * `execute_so` and routing correctness requires matching it exactly — this handle
 * consumes the upstream service as-is, it does not rename it.)
 *
 * The service name is agentINVEST-scoped (`bd09`, the `agentinvestPlanner` /
 * `pyTools` naming discipline) so it does not collide with a same-named service
 * from a sibling project on the shared dev Restate.
 *
 * Topology: `bd09` is a model-free Restate *service* — the
 * per-Business-Domain dispatch / tool-hosting boundary. The SOs it dispatches are
 * *tools*. It carries NO reasoning loop: it routes a NAMED `soId` to its tool, it
 * does not decide which tool to call (that decision is the one `.plan()` loop, at
 * seam 1). Dispatch (this seam) is MECHANISM — fan-out + collect — not a second
 * reasoning loop.
 *
 * Schema SSOT: the Python `bd09_service.py` (`ExecuteSoInput` / `ExecuteSoOutput`)
 * is the authority; this file mirrors its shape as TS types for the caller. bd09's
 * `execute_so` validates `args` against the tool's own `extra="forbid"` Pydantic
 * input and classifies every deterministic failure (unknown soId, bad/missing/extra
 * arg, compute failure) as a Restate `TerminalError` (no retry storm),
 * which the dispatch step captures as a clean step-failure.
 */
import type { Context, ServiceDefinition } from '@restatedev/restate-sdk';

/** The Python bd09 dispatch service name — the routing key shared by both sides. */
export const BD09_SERVICE_NAME = 'bd09';

/** The `execute_so` request envelope — a named SO plus its argument dict. */
export interface ExecuteSoInput {
  /** The Service-Operation identifier to dispatch, e.g. 'SO-09-01'. */
  soId: string;
  /**
   * The tool's arguments as a JSON object. NOT validated here — bd09 validates them
   * against the tool's own `extra="forbid"` Pydantic input inside its journaled
   * step; a bad/missing/extra arg is a terminal step-failure (the honest v0.1
   * behaviour when the planner could not fully resolve the args).
   */
  args: Record<string, unknown>;
}

/** Replay-safe provenance — derived from the request + the tool's deterministic output. */
export interface ExecuteSoProvenance {
  soId: string;
  tool: string;
  methodology: string;
}

/** The `execute_so` result envelope — the typed tool result plus provenance. */
export interface ExecuteSoOutput {
  /** The tool's typed output as a JSON object. */
  result: Record<string, unknown>;
  /** Replay-safe provenance (soId, tool name, methodology label). */
  provenance: ExecuteSoProvenance;
  /** Which language + service computed it (e.g. `python:bd09`). */
  computedBy: string;
}

/**
 * The Python `bd09` handlers, expressed in TS so the caller is typed. The key is
 * the REGISTERED wire name `execute_so` (snake_case), so the routed call is
 * `.execute_so(...)`.
 */
export type Bd09Handlers = {
  execute_so: (ctx: Context, input: ExecuteSoInput) => Promise<ExecuteSoOutput>;
};

/**
 * The type-only service-definition handle passed to `ctx.serviceClient(...)`. The
 * `name` is the runtime routing key; the generic gives the TS caller compile-time
 * types on the request and response. The implementation lives behind the wire (in
 * Python).
 */
export const BD09_SERVICE: ServiceDefinition<typeof BD09_SERVICE_NAME, Bd09Handlers> = {
  name: BD09_SERVICE_NAME,
};
