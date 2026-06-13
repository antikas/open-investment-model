/**
 * The RESOLVE step (between seam 1 PLAN and seam 2 DISPATCH) — the abstract-arg → concrete-input
 * resolution layer.
 *
 * The orchestrator's seam-1 `.plan()` loop produces a `Plan` whose `steps[]` each name a `soId`
 * + ABSTRACT args (the planner knows the fund + the period + a sector axis, but not the concrete
 * begin/end NAV or the per-segment weights — those live in the marts). The DISPATCH step
 * needs the tools' CONCRETE inputs. THIS step bridges them: for each plan step it calls the Python
 * `argResolver.resolveStepArgs` handler over Restate (which READS the marts and DERIVES the concrete
 * inputs), and produces a `ResolvedStep` carrying the concrete args
 * dispatch will pass to `bd09.execute_so`.
 *
 * WHY THIS STEP EXISTS. Without it, dispatch would pass the planner's args AS GIVEN; a step
 * whose args the planner could not resolve would surface as a clean failure, and the args would
 * have to be resolved BY HAND in an explicit script. This step moves that resolution into the
 * orchestrator's flow, so the chain runs AUTONOMOUSLY: the planner decides the tools, the resolver
 * derives their args, dispatch runs them — no by-hand glue.
 *
 * RESOLVE IS MECHANISM, not a reasoning loop. It is DETERMINISTIC (no LLM): it reads the marts and
 * derives the inputs. There is exactly one reasoning loop (the `.plan()` step at seam 1); this is a
 * journaled data-derivation seam.
 *
 * HONESTLY BOUNDED TO THE BD-09 RETURN TOOLS (v0.1). The resolver knows SO-09-01 / SO-09-05. A
 * step naming any other tool, or a step the marts cannot resolve (a
 * missing fund, an unbuilt store), surfaces as a CLEAN FAILURE (`{ status: 'unresolved' }`) — NEVER
 * fabricated inputs (no fake data driving a real-looking attribution). A general resolver for the
 * ~900-tool catalogue is forward work.
 *
 * THE LEGAL RESTATE SHAPE. Each `ctx.serviceClient(ARG_RESOLVER_SERVICE).resolveStepArgs(...)` is a
 * journaled RPC at the handler top level — NO enclosing `ctx.run` (a context action nested inside a
 * `ctx.run` closure is the Restate determinism anti-pattern). The resolution is journaled by the
 * RPC's call semantics, so a crash/replay reads the resolved args back; the marts are not re-read.
 *
 * THE FUND/WINDOW. The resolver needs the fund + window for the marts read. The plan's abstract args
 * carry them inconsistently (the planner fills `args` plausibly but not always with a fund key), so
 * the orchestrator passes the OPERATION'S declared fund/window (from the inbound task params) to the
 * resolver — the abstract args the analyst task names, resolved against the canonical marts. A step
 * whose tool is unresolvable, or a fund the marts lack, is the clean-failure path.
 */
import type { ObjectContext } from '@restatedev/restate-sdk';
import { ARG_RESOLVER_SERVICE, type ResolveStepArgsResult } from './arg-resolver-contract.js';
import type { Plan, PlanStep } from './llm-service-contract.js';

/** The abstract window the operation declares (the fund + period the attribution is over). */
export interface ResolutionWindow {
  /** The fund the attribution is over, e.g. 'PF-0003'. Required to resolve from the marts. */
  fundId: string | null;
  /** The window begin date (YYYY-MM-DD); null → the resolver's canonical default. */
  beginDate: string | null;
  /** The window end date (YYYY-MM-DD); null → the resolver's canonical default. */
  endDate: string | null;
}

/** One step's resolution outcome — resolved (concrete args) or unresolved (a surfaced failure). */
export type ResolvedStep =
  | {
      /** The step's 0-based index in `plan.steps` (stable ordering). */
      index: number;
      /** The Service-Operation the step calls. */
      soId: string;
      /** The step resolved: the marts-derived concrete inputs are ready to dispatch. */
      status: 'resolved';
      /** The CONCRETE args dispatch passes to `bd09.execute_so` (replaces the plan's abstract args). */
      args: Record<string, unknown>;
      /** The full resolver result (the resolved window + provenance) — carried for the audit record. */
      resolution: ResolveStepArgsResult;
    }
  | {
      index: number;
      soId: string;
      /**
       * The step could NOT be resolved cleanly: a tool the v0.1 resolver does not know (anything
       * but SO-09-01/05), a missing fund, or an unbuilt store. Surfaced as a clean failure — dispatch
       * SKIPS it (it never dispatches on fabricated inputs), and the aggregate surfaces it honestly.
       */
      status: 'unresolved';
      /** The surfaced resolver error (the argResolver TerminalError text), never swallowed. */
      error: string;
    };

/** The collected outcome of resolving a whole plan — every step, resolved or unresolved. */
export interface ResolveResult {
  /** One `ResolvedStep` per `plan.steps[]`, in plan order. */
  resolvedSteps: ResolvedStep[];
  /** How many steps the marts resolved to concrete inputs. */
  resolvedCount: number;
  /** How many steps surfaced a clean resolution failure. */
  unresolvedCount: number;
}

/** A clean, key-free error message from a rejected resolution. */
function describeReason(reason: unknown): string {
  if (reason instanceof Error) return reason.message;
  if (typeof reason === 'string') return reason;
  try {
    return JSON.stringify(reason);
  } catch {
    return String(reason);
  }
}

/**
 * Resolve every step of `plan` against the marts via `argResolver.resolveStepArgs`, IN PARALLEL,
 * and collect the per-step outcomes. The LEGAL Restate shape: each
 * `ctx.serviceClient(...).resolveStepArgs(...)` is a journaled RPC at the handler top level — NO
 * enclosing `ctx.run`. `Promise.allSettled` is the clean-failure contract: a step the resolver
 * rejects is captured cleanly (`{ status: 'unresolved' }`), the siblings still resolve.
 *
 * NEVER fabricates inputs: an unresolvable step is surfaced, not guessed. The resolved args REPLACE
 * the plan's abstract args (which were the planner's plausible-but-not-concrete fill).
 *
 * @param ctx    the orchestrator's object context (the production VO's context).
 * @param plan   the journaled plan whose steps are resolved.
 * @param window the operation's declared fund/window (the abstract args the analyst task names).
 * @returns the collected `resolvedSteps` + the resolved/unresolved counts.
 */
export async function resolvePlan(
  ctx: ObjectContext,
  plan: Plan,
  window: ResolutionWindow,
): Promise<ResolveResult> {
  const client = ctx.serviceClient(ARG_RESOLVER_SERVICE);

  const settled = await Promise.allSettled(
    plan.steps.map((step: PlanStep) =>
      client.resolveStepArgs({
        soId: step.soId,
        fundId: window.fundId ?? '',
        beginDate: window.beginDate ?? null,
        endDate: window.endDate ?? null,
      }),
    ),
  );

  const resolvedSteps: ResolvedStep[] = settled.map((outcome, index) => {
    const soId = plan.steps[index].soId;
    if (outcome.status === 'fulfilled') {
      const resolution = outcome.value as ResolveStepArgsResult;
      return { index, soId, status: 'resolved', args: resolution.args, resolution };
    }
    // A clean resolution failure — surfaced, NEVER replaced with a fabricated input.
    return { index, soId, status: 'unresolved', error: describeReason(outcome.reason) };
  });

  const resolvedCount = resolvedSteps.filter((r) => r.status === 'resolved').length;
  const unresolvedCount = resolvedSteps.length - resolvedCount;

  return { resolvedSteps, resolvedCount, unresolvedCount };
}
