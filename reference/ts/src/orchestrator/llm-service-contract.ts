/**
 * Typed cross-language RPC contract for the `agentinvestPlanner` planner.
 *
 * The TS↔Python seam for the ONE reasoning loop: the orchestrator's seam-1
 * `.plan()` step calls the Python `agentinvestPlanner.planTask` handler over
 * Restate's typed RPC (the same `ctx.serviceClient(...)` path the `pyTools`
 * contract uses). The TS side does NOT import Python — it declares a type-only
 * service-definition handle describing the service name + the `planTask` handler's
 * typed I/O, and `ctx.serviceClient(PLANNER_SERVICE)` gives a typed client routed
 * to the Python service.
 *
 * The service name is agentINVEST-scoped (`agentinvestPlanner`, the `bd09` /
 * `pyTools` naming discipline) so it does not collide with a same-named service
 * from a sibling project on the shared dev Restate.
 *
 * Topology: `agentinvestPlanner` is a model-free Restate *service* — the
 * hosting/dispatch boundary the single reasoning loop runs in. The SOs it plans
 * over are *tools* in a typed catalogue. There is ONE loop, here. The plan it
 * returns is GENERATED, not executed (dispatch is a later step) — a valid plan is
 * a structure + tool-selection claim, not an outcome.
 *
 * Schema SSOT: the Python `PlanSchema` (Pydantic) is the authority. This file
 * mirrors its shape as TS types for the caller, and `parsePlan` (in
 * `plan-parse.ts`) does a thin defensive structural check on the returned JSON
 * (no new dependency) — the service returns an ALREADY-VALIDATED plan, the
 * orchestrator parses it defensively before trusting it.
 */
import type { Context, ServiceDefinition } from '@restatedev/restate-sdk';

/** The Python planner service name — the routing key shared by both sides. */
export const PLANNER_SERVICE_NAME = 'agentinvestPlanner';

/** One candidate tool the planner may select among (the per-task catalogue). */
export interface CandidateTool {
  /** The Service-Operation id of the candidate tool. */
  soId: string;
  /** The tool's display name. */
  name: string;
  /** The tool's natural-language summary. */
  summary: string;
  /** The tool's input JSON schema, when available (the live bd09 tools carry it). */
  inputSchema?: Record<string, unknown> | null;
}

/** The `planTask` request — a task + the candidate tool catalogue + guardrails. */
export interface PlanTaskInput {
  /** The analyst task to plan (a natural-language request). */
  task: string;
  /** The candidate tool descriptors the planner selects among (the tool-RAG seam output). */
  catalogue: CandidateTool[];
  /** Optional planning guardrails (defaults to the planner's own). */
  guardrails?: string | null;
}

/** One step of a returned plan — a named tool plus its args (mirror of `PlanStep`). */
export interface PlanStep {
  /** The Service-Operation id of the catalogue tool this step calls. */
  soId: string;
  /** The tool's arguments as a JSON object (validated at dispatch, not here). */
  args: Record<string, unknown>;
  /** Short justification for selecting this tool (for the audit trail). */
  rationale?: string | null;
}

/**
 * A returned, validated plan (mirror of the Python `PlanSchema`). The plan is
 * GENERATED, not executed: a valid plan is a structure + tool-selection claim,
 * not an outcome. `riskScore` is declared for the approval gate, NOT exercised
 * by the planner itself.
 */
export interface Plan {
  /** The ordered tool-call steps the planner proposes (at least one). */
  steps: PlanStep[];
  /** How high-stakes the plan is, in [0,1], for the future approval gate (declared, not exercised). */
  riskScore: number;
  /** One-line natural-language description of the plan (audit trail). */
  summary?: string | null;
}

/** The Python `agentinvestPlanner` handlers, expressed in TS so the caller is typed. */
export type LlmServiceHandlers = {
  planTask: (ctx: Context, input: PlanTaskInput) => Promise<Plan>;
};

/**
 * The type-only service-definition handle passed to `ctx.serviceClient(...)`. The
 * `name` is the runtime routing key; the generic gives the TS caller compile-time
 * types on the request and response. The implementation lives behind the wire (in
 * Python).
 */
export const PLANNER_SERVICE: ServiceDefinition<typeof PLANNER_SERVICE_NAME, LlmServiceHandlers> = {
  name: PLANNER_SERVICE_NAME,
};
