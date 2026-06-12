/**
 * The DISPATCH step (seam 2) — execute the planner's plan over the `bd09` service.
 *
 * The orchestrator's seam-1 `.plan()` loop produces a `Plan` whose `steps[]` each
 * name a `soId` + `args`. THIS step RUNS that plan: it dispatches every step to the
 * `bd09` dispatch service via `ctx.serviceClient(BD09_SERVICE).execute_so({ soId,
 * args })` over Restate, IN PARALLEL, and collects the per-step outcomes into a
 * `stepResults` structure. The first time the planner's plan is actually executed.
 *
 * Dispatch is MECHANISM, not a reasoning loop. It fans the plan's steps out to the
 * model-free `bd09` service and collects what comes back. It does not decide which
 * tool to run (that is the one `.plan()` loop, seam 1) and it does not aggregate the
 * results into a coherent answer (that is a forward seam — OIM-133/134); it collects
 * the raw per-step outcomes.
 *
 * THREE load-bearing properties, all proven on the PRODUCTION `investmentOperation`
 * VO (not a probe):
 *
 *  - **Parallel fan-out.** The independent steps are dispatched CONCURRENTLY with
 *    `Promise.allSettled` over `plan.steps.map(...)`. N parallel `execute_so` RPCs
 *    from one handler complete in ~max(step) not ~sum(step) — a measured latency
 *    improvement vs a serial baseline. This discharges the OIM-104 carry-forward
 *    (intra-handler outbound fan-out, "to be proven at OIM-131's gate").
 *
 *  - **Clean partial-failure.** `Promise.allSettled` (NOT `Promise.all`): one step
 *    failing must NOT abort the siblings or retry-storm the operation. A
 *    deterministic tool error is the bd09-classified `TerminalError` (OIM-113 —
 *    invalid/incomplete args → terminal 400/422, `retry_count=0`): it is captured
 *    as a clean step-failure (`{ status: 'rejected', error }`), the siblings
 *    complete (`{ status: 'fulfilled', result }`), and the failure is SURFACED in
 *    the collected `stepResults` — never swallowed, never a silent drop, never a
 *    whole-operation abort. (`Promise.all` would reject fail-fast and kill the
 *    siblings — that fails the gate.)
 *
 *  - **Journaled.** Each `ctx.serviceClient(...).execute_so(...)` RPC is journaled
 *    by Restate's call semantics — the LEGAL shape (no context-action nested inside
 *    a `ctx.run` closure). On a crash/replay the dispatched results are read back
 *    from the journal; the tools are NOT re-executed. The fiduciary-determinism
 *    property holds through dispatch.
 *
 * HONEST BOUNDARY (v0.1). plan→dispatch is built; the approval gate (OIM-132 —
 * `riskScore` declared-not-gated), aggregate-into-a-coherent-answer + the
 * close/audit-record seam (OIM-133/134), and the NAV-strike workflow (OIM-133) are
 * forward. The planner's abstract `args` → concrete tool-input resolution
 * (resolving "fund X over Q1" into the begin/end NAV from the marts — what the
 * OIM-115 demo did by hand) is forward: dispatch passes `args` AS GIVEN; bd09
 * validates them; a step whose args the planner could not resolve surfaces as a
 * CLEAN FAILURE (the honest v0.1 behaviour, not a bug). Synthetic data;
 * supervised-autonomous; frontier-only.
 *
 * v0.1 parallelism note. `PlanSchema` carries NO inter-step dependency field, so
 * every step is treated as INDEPENDENT → all-parallel `allSettled`. Inter-step data
 * dependencies (feeding one step's output into another's args) are a forward
 * concern; this step does not express them.
 */
import type { ObjectContext } from '@restatedev/restate-sdk';
import { BD09_SERVICE, type ExecuteSoOutput } from './bd09-service-contract.js';
import type { Plan, PlanStep } from './llm-service-contract.js';
import type { ResolvedStep } from './resolve.js';

/** One step's dispatch outcome — fulfilled (the tool result) or rejected (a surfaced failure). */
export type StepResult =
  | {
      /** The step's 0-based index in `plan.steps` (stable ordering, even under parallel completion). */
      index: number;
      /** The Service-Operation the step dispatched. */
      soId: string;
      /** The step completed: bd09 ran the tool and returned a typed result. */
      status: 'fulfilled';
      /** The `bd09.execute_so` result envelope (tool result + provenance + computedBy). */
      result: ExecuteSoOutput;
    }
  | {
      index: number;
      soId: string;
      /**
       * The step failed cleanly: a deterministic bd09 `TerminalError` (OIM-113 —
       * bad/missing/extra arg, unknown soId, or a deterministic compute failure),
       * captured here, NOT propagated as a whole-operation abort. The siblings
       * still ran. This is the honest v0.1 behaviour when the planner could not
       * resolve a step's args.
       */
      status: 'rejected';
      /** The surfaced error message (the bd09 TerminalError text), never swallowed. */
      error: string;
    };

/** The collected outcome of dispatching a whole plan — every step, fulfilled or rejected. */
export interface DispatchResult {
  /** One `StepResult` per `plan.steps[]`, in plan order (re-sorted after parallel completion). */
  stepResults: StepResult[];
  /** How many steps the tools ran successfully. */
  fulfilledCount: number;
  /** How many steps surfaced a clean failure (a deterministic bd09 TerminalError). */
  rejectedCount: number;
}

/**
 * Extract a clean, key-free error message from a rejected dispatch. Restate
 * surfaces a `TerminalError` (and the SDK's transient-fault wrapper) as an `Error`
 * with a `.message`; anything else is stringified. The message is the bd09
 * TerminalError text (e.g. "SO-09-01 (compute_total_return): invalid arguments …").
 */
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
 * Dispatch every step of `plan` to `bd09.execute_so` IN PARALLEL and collect the
 * per-step outcomes. The LEGAL Restate shape: each `ctx.serviceClient(...)
 * .execute_so(...)` is a journaled RPC at the handler top level — there is NO
 * enclosing `ctx.run` (a context action nested inside a `ctx.run` closure is the
 * Restate determinism anti-pattern). `Promise.allSettled` is the partial-failure
 * contract: a rejected step is captured cleanly, the siblings complete.
 *
 * @param ctx  the orchestrator's object context (the production VO's context).
 * @param plan the journaled plan whose steps are dispatched.
 * @returns the collected `stepResults` + the fulfilled/rejected counts.
 */
export async function dispatchPlan(ctx: ObjectContext, plan: Plan): Promise<DispatchResult> {
  const client = ctx.serviceClient(BD09_SERVICE);

  // PROOF-ONLY SEAM — a serial baseline. The PRODUCTION dispatch is ALWAYS the
  // parallel `Promise.allSettled` fan-out below. When AGENTINVEST_DISPATCH_SERIAL is
  // set (ONLY by the fan-out latency proof, on its own endpoint process), the SAME
  // execute_so RPCs are awaited one-at-a-time instead, giving an apples-to-apples
  // serial baseline (~sum(step)) to measure the parallel win (~max(step)) against —
  // both over the real bd09 RPCs on the production VO. It is a NO-OP in production
  // (the env is unset, so this branch is never taken). It still uses allSettled
  // semantics (a rejection is captured, not thrown) so the serial path collects the
  // same shape; it just forfeits the concurrency, which is the whole point of the
  // baseline.
  let settled: PromiseSettledResult<ExecuteSoOutput>[];
  if (process.env.AGENTINVEST_DISPATCH_SERIAL) {
    settled = [];
    for (const step of plan.steps) {
      settled.push(
        await Promise.allSettled([client.execute_so({ soId: step.soId, args: step.args })]).then(
          (s) => s[0],
        ),
      );
    }
  } else {
    // The parallel fan-out: one journaled `execute_so` RPC per step, dispatched
    // concurrently. `Promise.allSettled` — NOT `Promise.all` — so one step's
    // terminal failure does not reject the whole batch (which would kill the
    // siblings); every step settles independently. N parallel RPCs complete in
    // ~max(step), not ~sum.
    settled = await Promise.allSettled(
      plan.steps.map((step: PlanStep) =>
        client.execute_so({ soId: step.soId, args: step.args }),
      ),
    );
  }

  // Collect every settlement into a stable, plan-ordered `stepResults`. A fulfilled
  // settlement carries the tool result; a rejected settlement carries the SURFACED
  // bd09 TerminalError message (never swallowed). The index keeps plan order stable
  // regardless of which step's RPC completed first.
  const stepResults: StepResult[] = settled.map((outcome, index) => {
    const soId = plan.steps[index].soId;
    if (outcome.status === 'fulfilled') {
      return { index, soId, status: 'fulfilled', result: outcome.value };
    }
    return { index, soId, status: 'rejected', error: describeReason(outcome.reason) };
  });

  const fulfilledCount = stepResults.filter((r) => r.status === 'fulfilled').length;
  const rejectedCount = stepResults.length - fulfilledCount;

  return { stepResults, fulfilledCount, rejectedCount };
}

/**
 * Dispatch the RESOLVED plan (OIM-134) — dispatch each RESOLVED step's CONCRETE args to
 * `bd09.execute_so` IN PARALLEL, and surface an UNRESOLVED step as a clean failure WITHOUT
 * dispatching it. This is the resolve→dispatch composition: the resolve step (OIM-134) turned the
 * planner's abstract args into the tools' concrete inputs from the marts; this dispatches those
 * concrete inputs. The difference from `dispatchPlan` is the args source — here the marts-derived
 * resolved args, not the planner's as-given abstract args — and the honest handling of an
 * unresolved step.
 *
 * NEVER dispatches on fabricated inputs. A step the resolver could not resolve (`status:
 * 'unresolved'` — an unknown tool, a missing fund, an unbuilt store) is surfaced DIRECTLY as a
 * `{ status: 'rejected' }` step-failure carrying the resolution error; it is NOT sent to `bd09`
 * with guessed args. The resolved steps dispatch over the real journaled `execute_so` path; the
 * three load-bearing properties (parallel fan-out, clean partial-failure, journaled) are unchanged
 * — they are exactly `dispatchPlan`'s, over the resolved-args subset.
 *
 * The LEGAL Restate shape: each resolved step's `ctx.serviceClient(...).execute_so(...)` is a
 * journaled RPC at the handler top level — NO enclosing `ctx.run`. `Promise.allSettled` keeps the
 * partial-failure contract (a rejected dispatch is captured, the siblings complete). The collected
 * `stepResults` stay plan-ordered (index-keyed), interleaving the dispatched outcomes with the
 * surfaced unresolved-step failures.
 *
 * @param ctx           the orchestrator's object context (the production VO's context).
 * @param resolvedSteps the resolve step's per-step outcomes (resolved → dispatch; unresolved → surface).
 * @returns the collected `stepResults` + the fulfilled/rejected counts (in plan order).
 */
export async function dispatchResolvedPlan(
  ctx: ObjectContext,
  resolvedSteps: ResolvedStep[],
): Promise<DispatchResult> {
  const client = ctx.serviceClient(BD09_SERVICE);

  // Dispatch ONLY the resolved steps (their marts-derived concrete args); an unresolved step is
  // surfaced as a clean failure WITHOUT a bd09 call (never dispatch on fabricated inputs).
  const settled = await Promise.allSettled(
    resolvedSteps.map((step) =>
      step.status === 'resolved'
        ? client.execute_so({ soId: step.soId, args: step.args })
        : // A resolved-promise carrier for the unresolved step, so allSettled keeps plan order and
          // the collection below surfaces the resolution error as a clean rejected step.
          Promise.resolve(null),
    ),
  );

  const stepResults: StepResult[] = settled.map((outcome, index) => {
    const step = resolvedSteps[index];
    const soId = step.soId;
    if (step.status === 'unresolved') {
      // Surfaced as a clean failure — the resolution error, NEVER a dispatch on fabricated inputs.
      return { index, soId, status: 'rejected', error: step.error };
    }
    if (outcome.status === 'fulfilled') {
      return { index, soId, status: 'fulfilled', result: outcome.value as ExecuteSoOutput };
    }
    return { index, soId, status: 'rejected', error: describeReason(outcome.reason) };
  });

  const fulfilledCount = stepResults.filter((r) => r.status === 'fulfilled').length;
  const rejectedCount = stepResults.length - fulfilledCount;

  return { stepResults, fulfilledCount, rejectedCount };
}
