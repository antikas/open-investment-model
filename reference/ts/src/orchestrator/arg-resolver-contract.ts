/**
 * Typed cross-language RPC contract for the `argResolver` service — the orchestrator's
 * abstract-arg → concrete-tool-input resolution seam (the resolve step).
 *
 * The orchestrator's seam-1 `.plan()` loop emits a plan whose steps name a tool (`soId`) and
 * ABSTRACT window args (a fund + a period + a sector/asset-class axis) — the planner cannot know
 * the concrete begin/end NAV or per-segment weights, those live in the marts. The RESOLVE
 * step (between plan and dispatch) calls the Python `argResolver.resolveStepArgs` handler over
 * Restate's typed RPC to derive each step's CONCRETE inputs from the marts; the resolved args then
 * feed the seam-2 DISPATCH step. The TS side does NOT import Python — it declares a type-only
 * service-definition handle describing the service name + the handler's typed I/O, and
 * `ctx.serviceClient(ARG_RESOLVER_SERVICE)` gives a typed client routed to the Python service.
 *
 * REUSE, NOT RE-IMPLEMENTATION. The Python resolver IMPORTS the demo's marts→tool-input
 * derivation (`read_fund_window` + `_total_return_args` / `_breakdown_args`); this seam READS those
 * derived inputs. The orchestrator does NOT re-derive them.
 *
 * Handler name discipline. The wire routing key is the name the Python side REGISTERS the handler
 * under: `arg_resolver_service.py` registers it as `@argResolver.handler(name="resolveStepArgs")`,
 * so the routed call is `.resolveStepArgs(...)` (camelCase, as registered — matching the `navData`
 * / `pyTools` convention).
 *
 * Topology: `argResolver` is a model-free Restate *service* — a data tool boundary. It
 * carries NO reasoning loop (it is mechanism — read the marts, derive the inputs — not a second
 * `.plan()`).
 *
 * Schema SSOT: the Python `arg_resolver_service.py` (`ResolveStepArgsResult`) is the authority;
 * this file mirrors its shape as TS types for the caller. Money figures inside `args` are exact
 * decimal STRINGS (no float drift across the boundary).
 */
import type { Context, ServiceDefinition } from '@restatedev/restate-sdk';

/** The Python argResolver service name — the routing key shared by both sides. */
export const ARG_RESOLVER_SERVICE_NAME = 'argResolver';

/**
 * The `resolveStepArgs` request — one plan step's tool + its abstract window args.
 *
 * `soId` is the tool the plan step selected; `fundId` is the fund the attribution is over;
 * `beginDate` / `endDate` are the window (optional — the resolver defaults them to the canonical
 * one-year window when omitted, so a plan naming a fund but not an explicit window still resolves).
 */
export interface ResolveStepArgsRequest {
  /** The tool the plan step selected, e.g. 'SO-09-01'. */
  soId: string;
  /** The fund the attribution is over, e.g. 'PF-0003'. */
  fundId: string;
  /** The window begin date (YYYY-MM-DD); omitted → the canonical default window. */
  beginDate?: string | null;
  /** The window end date (YYYY-MM-DD); omitted → the canonical default window. */
  endDate?: string | null;
}

/**
 * The resolved concrete tool inputs + the window provenance. `args` is the tool's CONCRETE input
 * dict (ready to dispatch to `bd09.execute_so` for `soId`), derived from the marts via the demo
 * derivation. The window fields (`fundName`, `beginDate`, `endDate`, `periodDays`, `beginNav`,
 * `endNav`) echo the resolved window so the orchestrator + the aggregate can carry it. Money
 * figures inside `args` are exact decimal strings (no float).
 */
export interface ResolveStepArgsResult {
  soId: string;
  fundId: string;
  fundName: string;
  beginDate: string;
  endDate: string;
  periodDays: number;
  /** The fund's begin NAV over the window (exact decimal string). */
  beginNav: string;
  /** The fund's end NAV over the window (exact decimal string). */
  endNav: string;
  /** The tool's CONCRETE input dict (the resolved args dispatch passes to bd09). */
  args: Record<string, unknown>;
  /** Which language + service resolved it (e.g. `python:argResolver`). */
  computedBy: string;
}

/**
 * The Python `argResolver` handlers, expressed in TS so the caller is typed. The key is the
 * REGISTERED wire name (camelCase), so the routed call is `.resolveStepArgs(...)`.
 */
export type ArgResolverHandlers = {
  resolveStepArgs: (ctx: Context, req: ResolveStepArgsRequest) => Promise<ResolveStepArgsResult>;
};

/**
 * The type-only service-definition handle passed to `ctx.serviceClient(...)`. The `name` is the
 * runtime routing key; the generic gives the TS caller compile-time types on the request and
 * response. The implementation lives behind the wire (in Python).
 */
export const ARG_RESOLVER_SERVICE: ServiceDefinition<
  typeof ARG_RESOLVER_SERVICE_NAME,
  ArgResolverHandlers
> = {
  name: ARG_RESOLVER_SERVICE_NAME,
};
