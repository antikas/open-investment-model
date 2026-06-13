/**
 * agentINVEST orchestrator — the `InvestmentOperation` virtual object.
 *
 * This is the HOME of agentINVEST's single reasoning loop. An inbound task ("compute
 * NAV for fund X as of date Y") becomes one `InvestmentOperation`, keyed by its
 * `operationId`. Restate's virtual-object guarantee gives the orchestrator its
 * two load-bearing properties:
 *
 *  - **Single-writer-per-key.** Concurrent invocations against the SAME
 *    `operationId` are serialised by Restate — one operation never races itself.
 *    Invocations against DIFFERENT `operationId`s run in parallel — independent
 *    operations do not block each other. This is the concurrency contract the
 *    parallel-dispatch step relies on.
 *  - **Durable execution.** Every step the handler journals via `ctx.run(...)` is
 *    recorded. If the process crashes mid-operation, Restate resumes the
 *    operation from its journal on restart — a journaled step is replayed (read
 *    back), not re-executed. Replay-grade reproducibility is the fiduciary
 *    property the whole substrate exists to provide.
 *
 * SCOPE — ALL FIVE SEAMS ARE BUILT HERE. The `execute`
 * handler runs the version-skew gate, then: SEAM 1 PLAN — a real LLM-driven `.plan()`
 * call via the Python `agentinvestPlanner.planTask` handler, decomposing the task into
 * a schema-validated plan; then the RESOLVE step — the abstract-arg → concrete-input
 * resolution layer: it calls the Python `argResolver.resolveStepArgs` handler to derive
 * each step's CONCRETE tool inputs from the marts (REUSING the marts→tool-input
 * derivation), so the planner's abstract args become the tools' real inputs (an
 * unresolvable step surfaces as a clean failure, never fabricated); then SEAM 2 DISPATCH
 * — it dispatches the RESOLVED steps' concrete args to `bd09` in parallel and collects
 * `stepResults`; then SEAM 3 the reusable high-stakes approval gate — a no-op for this
 * read-only analytics task (riskScore below threshold); then SEAM 4 AGGREGATE — it
 * combines the step results into a coherent attribution answer (the total return + the
 * per-sector contributions, with the coherence invariant — the contributions
 * reconcile to the total return — as the correctness check; a partial failure is
 * surfaced, not fabricated); then SEAM 5 CLOSE — it writes a journaled, well-formed,
 * structured audit record of the whole operation (task, plan, resolved args, step
 * results, aggregate, gate decision). The chain now runs the full
 * plan → resolve → dispatch → approve → aggregate → close loop autonomously to a real,
 * audited attribution. The gate is the MECHANISM + a forced-fire proof — for BD-09's
 * read-only tools it does NOT fire by default (the riskScore stays below the threshold);
 * the first REAL high-stakes wiring is the NAV-publish workflow.
 *
 * SEAM 1 uses the LEGAL journaling shape A — a DIRECT
 * `ctx.serviceClient(PLANNER_SERVICE).planTask(...)` call. Restate journals the RPC
 * RESULT by its call semantics, so the model's NON-DETERMINISTIC plan is journaled
 * EXACTLY ONCE: on a crash/replay Restate reads the recorded plan back rather than
 * re-invoking the model. There is NO enclosing `ctx.run` — a `ctx.serviceClient`
 * (a context action) nested inside a `ctx.run` closure is the Restate determinism
 * anti-pattern (an earlier architecture sketch got this wrong). The version-skew gate stays in
 * front; the VO key + the journal-one-durable-step discipline are preserved.
 *
 * VOCABULARY. `InvestmentOperation` is a model-free orchestration boundary — the
 * ONE loop's home. `agentinvestPlanner` (the planner) and `bd09` (the tool surface) are
 * model-free Restate *services*, never "agents". The SOs are *tools*. There is
 * exactly one reasoning loop — the `.plan()` step here.
 *
 * HONEST BOUNDARY (v0.1). Frontier-only (Sonnet 4.6, no fine-tuning /
 * fleet / office-split); the plan is generated, not executed (dispatch is later);
 * the model is non-deterministic, so a "valid plan" is a structural claim
 * (PlanSchema-valid, journaled once) — the quantified tool-selection claim is the
 * record-then-score eval number; supervised-autonomous on synthetic data.
 */
import { object, TerminalError, type ObjectContext } from '@restatedev/restate-sdk';
import {
  checkRuntimeVersionSkew,
  OPENIM_PINNED_RESTATE_VERSION,
  type VersionSkewStatus,
} from '../substrate/restate-reach.js';
import { PLANNER_SERVICE, type Plan } from './llm-service-contract.js';
import { parsePlan } from './plan-parse.js';
import { dispatchResolvedPlan, type StepResult } from './dispatch.js';
import { resolvePlan, type ResolvedStep, type ResolutionWindow } from './resolve.js';
import {
  aggregateResults,
  buildAuditRecord,
  type AttributionAggregate,
  type GateDecisionRecord,
  type OperationAuditRecord,
} from './aggregate-close.js';
import { highStakesApprovalGate, OperationAbortedError } from './approval-gate.js';

export const INVESTMENT_OPERATION_NAME = 'investmentOperation';

/**
 * The inbound task the orchestrator is asked to carry out. At the shell this is
 * an opaque descriptor; the planning step will read its fields to decompose it.
 */
export interface OperationTask {
  /** A short label for the kind of operation (e.g. "nav-strike"). Opaque here. */
  kind?: string;
  /** Free-form task parameters. Opaque at the shell; the planner reads them. */
  params?: Record<string, unknown>;
}

/** The result of running an `InvestmentOperation`. */
export interface OperationResult {
  /** The virtual-object key this operation ran under. */
  operationId: string;
  /**
   * The plan the `.plan()` step produced (journaled exactly once). The plan is
   * GENERATED, not executed: dispatch (running its steps) is a separate, later
   * step. A returned plan is a structure + tool-selection claim, not an outcome.
   */
  plan: Plan;
  /**
   * The ordered tool `soId`s the plan selected — a convenience projection of
   * `plan.steps[].soId`, stable across replays (the journaled plan is replayed,
   * never re-planned).
   */
  selectedSoIds: string[];
  /**
   * The RESOLVE step's per-step outcomes — one entry per `plan.steps[]`, each resolved
   * (the marts-derived concrete inputs) or unresolved (a clean, surfaced resolution
   * failure). The abstract-arg → concrete-input resolution (REUSING the marts→tool-input
   * derivation), journaled by the resolver RPCs.
   */
  resolvedSteps: ResolvedStep[];
  /**
   * The per-step DISPATCH outcomes (seam 2) — one entry per `plan.steps[]`, each
   * fulfilled (the tool ran on its RESOLVED concrete args, carrying its result) or
   * rejected (a clean, surfaced failure — a bd09 TerminalError, or an unresolved step
   * never dispatched on fabricated inputs). Journaled by the dispatched RPCs, so a
   * replay reads these back rather than re-running the tools.
   */
  stepResults: StepResult[];
  /** How many dispatched steps the tools ran successfully. */
  fulfilledCount: number;
  /** How many dispatched steps surfaced a clean failure (a deterministic bd09 TerminalError). */
  rejectedCount: number;
  /**
   * The AGGREGATE (seam 4) — the coherent attribution answer (the total return + the
   * per-sector contributions, reconciling per the coherence invariant), or a surfaced
   * partial failure (never fabricated).
   */
  aggregated: AttributionAggregate;
  /**
   * The CLOSE (seam 5) — the journaled, well-formed audit record of the whole operation
   * (task, plan, resolved args, step results, aggregate, gate decision).
   */
  auditRecord: OperationAuditRecord;
  /** Terminal status of the run. */
  status: 'completed';
  /** The task kind echoed back (opaque pass-through). */
  kind: string | null;
  /** Fixed marker identifying which surface answered. */
  orchestrator: typeof INVESTMENT_OPERATION_NAME;
}

/** The HTTP-ish status the version-skew refusal surfaces as on the ingress. */
export const VERSION_SKEW_BLOCKED_CODE = 409;

/**
 * Raised when a NEW operation is refused because the live server version no
 * longer matches the pinned version. Cross-version replay determinism is not
 * guaranteed, so the orchestrator blocks new operations on a definite mismatch
 * rather than journal a fiduciary operation it may not be able to replay.
 *
 * It extends Restate's TerminalError: the refusal is the orchestrator's
 * deliberate, final decision — NOT a transient fault — so Restate must NOT retry
 * it, and the ingress surfaces it as a 4xx rather than hanging on retries.
 */
export class VersionSkewBlockedError extends TerminalError {
  readonly skew: VersionSkewStatus;
  constructor(skew: VersionSkewStatus) {
    super(
      `InvestmentOperation blocked: the running Restate server reports v${skew.running} ` +
        `but this orchestrator is pinned to v${skew.pinned}. Cross-version replay determinism ` +
        `is not guaranteed, so new operations are blocked until the version is reconciled. ` +
        `In-flight operations are unaffected (they stay pinned to their starting deployment).`,
      { errorCode: VERSION_SKEW_BLOCKED_CODE },
    );
    this.name = 'VersionSkewBlockedError';
    this.skew = skew;
  }
}

/**
 * State held per `operationId` in the virtual object's key-value store. At the
 * shell this records only the lifecycle status + the journaled step id; the
 * planning step will grow it (the plan, the step results, the audit record).
 */
interface OperationState {
  status: 'running' | 'completed' | 'aborted';
  /** The plan the `.plan()` step journaled (replayed, never re-planned). */
  plan: Plan | null;
  /**
   * The resolve step's per-step outcomes (the marts-derived concrete inputs), journaled
   * by the resolver RPCs. Null until resolve has run.
   */
  resolvedSteps: ResolvedStep[] | null;
  /**
   * The dispatch step's per-step outcomes (seam 2), journaled by the dispatched
   * RPCs and read back on replay. Null until dispatch has run.
   */
  stepResults: StepResult[] | null;
  /** The aggregate (seam 4) — the coherent attribution answer. Null until aggregate has run. */
  aggregated: AttributionAggregate | null;
  /** The audit record (seam 5) — the journaled close record. Null until close has run. */
  auditRecord: OperationAuditRecord | null;
  /**
   * Set when the high-stakes approval gate (seam 3) aborted the operation — an
   * operator reject or a decision timeout. Null on a normal (approved / not-gated)
   * run. Journaled before the terminal abort so `status` surfaces an aborted
   * operation cleanly (replay reads it back).
   */
  abort?: { kind: 'aborted-by-operator' | 'aborted-by-timeout'; reason: string | null } | null;
}

/**
 * The orchestrator's runtime version-skew gate. Called at the START of every new
 * operation (per-op cadence): re-check the live server version against the pin,
 * and refuse a NEW operation on a definite mismatch (block-new-ops). An
 * indeterminate reading (version unreadable) does not block — it is logged and
 * the operation proceeds, because refusing on an unknown would make the
 * orchestrator hostage to a missing admin field.
 *
 * The check itself is a non-deterministic read of external state, so it runs
 * inside `ctx.run(...)` — its boolean outcome is journaled. On replay the gate
 * does NOT re-probe the server; it reads the recorded decision, so a replay of
 * an operation that was admitted stays admitted (it does not re-block on a
 * version that changed after the operation started).
 */
async function assertVersionAdmissible(ctx: ObjectContext): Promise<void> {
  const skew = await ctx.run('version-skew-gate', async () => {
    return checkRuntimeVersionSkew(OPENIM_PINNED_RESTATE_VERSION);
  });
  if (skew.indeterminate) {
    ctx.console.warn(
      `[investment-operation] version-skew gate: running version indeterminate ` +
        `(admin /version unreadable); proceeding (pin v${skew.pinned}).`,
    );
    return;
  }
  if (skew.mismatch) {
    ctx.console.error(
      `[investment-operation] version-skew gate BLOCKED a new operation: ` +
        `running v${skew.running} != pinned v${skew.pinned}.`,
    );
    // A deliberate, final refusal — a TerminalError so Restate does NOT retry it
    // (a plain Error would be retried as a transient fault) and the ingress
    // returns a 4xx. The planning step will refine this into a structured
    // aborted-operation audit record.
    throw new VersionSkewBlockedError(skew);
  }
  ctx.console.log(
    `[investment-operation] version-skew gate OK — running v${skew.running} == pinned v${skew.pinned}.`,
  );
}

/**
 * Derive the natural-language planning task from the inbound `OperationTask`.
 * Prefers an explicit `params.task` string; otherwise composes a task from the
 * `kind` + the remaining params so the planner always receives a usable request.
 */
function buildPlanTask(task: OperationTask): string {
  const params = task.params ?? {};
  const explicit = params.task;
  if (typeof explicit === 'string' && explicit.trim().length > 0) {
    return explicit;
  }
  const kind = task.kind ?? 'investment-operation';
  const rest = Object.entries(params)
    .filter(([k]) => k !== 'task')
    .map(([k, v]) => `${k}=${JSON.stringify(v)}`)
    .join(', ');
  return rest.length > 0 ? `Perform a ${kind} operation with parameters: ${rest}.` : `Perform a ${kind} operation.`;
}

/**
 * Derive the operation's declared resolution window (the fund + period the attribution is over)
 * from the inbound task params. These are the ABSTRACT args the analyst task names; the resolve
 * step resolves them against the canonical marts into the tools' concrete inputs.
 *
 * The fund is read from `params.fund` / `params.fundId`; the window from `params.begin`/`beginDate`
 * + `params.end`/`endDate`. A missing window is null (the resolver defaults it to the canonical
 * window); a missing fund is null (the resolve step then surfaces a clean failure — it never
 * fabricates a fund). The orchestrator does not parse the natural-language task for the fund — the
 * structured params carry it (the planner reads the prose; the resolver needs the structured fund).
 */
function buildResolutionWindow(task: OperationTask): ResolutionWindow {
  const params = task.params ?? {};
  const asStr = (v: unknown): string | null =>
    typeof v === 'string' && v.trim().length > 0 ? v.trim() : null;
  return {
    fundId: asStr(params.fund) ?? asStr(params.fundId),
    beginDate: asStr(params.begin) ?? asStr(params.beginDate),
    endDate: asStr(params.end) ?? asStr(params.endDate),
  };
}

export const investmentOperation = object({
  name: INVESTMENT_OPERATION_NAME,
  handlers: {
    /**
     * Run one `InvestmentOperation`. THE SHELL: it gates on the runtime version
     * check, journals a single stub step, records its status, and returns. The
     * reasoning loop is not built here — the numbered seams mark where it lands.
     */
    async execute(ctx: ObjectContext, task: OperationTask = {}): Promise<OperationResult> {
      const operationId = ctx.key;
      ctx.console.log(`[investment-operation] execute operationId=${operationId} kind=${task.kind ?? '(none)'}`);

      // GATE — runtime version-skew: refuse a NEW operation if the live server
      // drifted from the pin (block-new-ops). Journaled, so a replay keeps the
      // admission decision it was started under.
      await assertVersionAdmissible(ctx);

      ctx.set<OperationState>('state', {
        status: 'running',
        plan: null,
        resolvedSteps: null,
        stepResults: null,
        aggregated: null,
        auditRecord: null,
        abort: null,
      });

      // ── SEAM 1 — PLAN (the one reasoning loop) ───────────────────────────
      // The single reasoning step: a real LLM-driven decomposition of the task
      // into a plan, via the Python `agentinvestPlanner.planTask` handler. This is
      // the LEGAL journaling shape A — a DIRECT `ctx.serviceClient(PLANNER_SERVICE)
      // .planTask(...)` call. Restate journals the RPC RESULT by its call
      // semantics, so the model's NON-DETERMINISTIC plan is journaled EXACTLY
      // ONCE: on a crash/replay Restate reads the recorded plan back and does NOT
      // re-invoke the model. There is NO enclosing `ctx.run` — a context action
      // (`ctx.serviceClient(...)`) nested inside a `ctx.run` closure is the
      // Restate determinism anti-pattern (an earlier architecture sketch got this wrong). The
      // returned plan is then defensively parsed (`parsePlan`) — the Python
      // `PlanSchema` is the schema SSOT; this is the orchestrator's structural
      // guard before it trusts the plan. A malformed plan is a TerminalError (no
      // retry storm). The plan is GENERATED, not executed: dispatch is SEAM 2.
      // PROOF-ONLY SEAM — an env-gated deterministic fixture plan that BYPASSES the
      // model call at seam 1, so the dispatch proofs (fan-out latency, crash-replay)
      // exercise the REAL `investmentOperation.execute` dispatch path with a fixed
      // plan and NO LLM API call. It is a NO-OP in production: when
      // AGENTINVEST_DISPATCH_FIXTURE_PLAN is unset (everywhere except a dispatch
      // proof harness), this branch is never taken and seam 1 calls the planner
      // exactly as before — the journal shape is byte-for-byte identical. The
      // fixture is read via a plain `ctx.run` so its result is journaled-once just
      // as the planTask RPC result is (replay reads it back, no re-read); it is then
      // parsed through the SAME `parsePlan` guard the live plan goes through. This
      // ONLY removes the model's non-determinism from the proofs (the mechanism
      // proofs (b)(c)(d) must be deterministic — the live plan→dispatch chain is
      // proven separately by scripts/dispatch-live-e2e.mjs with a real Sonnet plan).
      const planTask = buildPlanTask(task);
      const fixturePlanJson = process.env.AGENTINVEST_DISPATCH_FIXTURE_PLAN;
      const plan = fixturePlanJson
        ? parsePlan(await ctx.run('dispatch-proof-fixture-plan', () => JSON.parse(fixturePlanJson)))
        : parsePlan(
            await ctx.serviceClient(PLANNER_SERVICE).planTask({ task: planTask, catalogue: [] }),
          );
      ctx.console.log(
        `[investment-operation] journaled plan: ${plan.steps.length} step(s), ` +
          `soIds=[${plan.steps.map((s) => s.soId).join(', ')}], riskScore=${plan.riskScore}`,
      );

      // PROOF-ONLY SEAM — env-gated durable pause in the between-plan-and-terminal
      // -write window. This exists SOLELY so the real-process-crash proof can
      // SIGKILL the production VO in the fiduciary-relevant window: the plan is
      // journaled (by the planTask RPC above), but the terminal
      // `ctx.set('state','completed')` below has NOT yet run. It is a NO-OP in
      // production: AGENTINVEST_CRASH_PROOF_DELAY_MS is unset (or 0) everywhere
      // except the crash-proof harness, so the `ctx.sleep` is NEVER reached and NO
      // journal entry is added — the handler's journal shape (gate → set(running)
      // → planTask(journaled) → set(completed)) is byte-for-byte identical to a
      // run with the env absent. It is read ONLY when the crash-proof harness sets
      // the env on its endpoint process. NOT a production behaviour change; a proof
      // seam whose production effect is nil. The crash here proves journaled-
      // exactly-once on the PLAN: replay reads the journaled plan, the model is NOT
      // re-called (the LLM-call-count instrument stays at 1 across the crash).
      const crashProofDelayMs = Number(process.env.AGENTINVEST_CRASH_PROOF_DELAY_MS ?? 0);
      if (crashProofDelayMs > 0) {
        ctx.console.warn(
          `[investment-operation] PROOF-ONLY durable pause ${crashProofDelayMs}ms ` +
            `(AGENTINVEST_CRASH_PROOF_DELAY_MS set) — crash-proof window between the ` +
            `journaled plan and the terminal state write. Never set in production.`,
        );
        await ctx.sleep(crashProofDelayMs);
      }

      // ── RESOLVE — abstract-arg → concrete-tool-input resolution (between plan and dispatch) ──
      // THE MISSING LINK. The planner emits ABSTRACT args (it knows the fund +
      // period + a sector axis, but not the concrete begin/end NAV or per-segment weights — those
      // live in the marts), so a dispatch on the as-given args surfaces clean failures. THIS
      // step bridges that: for each plan step it calls the Python `argResolver.resolveStepArgs`
      // handler (a journaled RPC — the LEGAL shape, no enclosing ctx.run) which READS the marts and
      // DERIVES the concrete inputs by REUSING the marts→tool-input derivation (read_fund_window +
      // _total_return_args / _breakdown_args) — folded into the orchestrator's flow so the chain runs
      // AUTONOMOUSLY instead of by-hand glue. The resolver is DETERMINISTIC (no
      // LLM — mechanism, not a second loop). Honestly bounded to the BD-09 return tools (SO-09-01/05):
      // a step the resolver cannot resolve (an unknown tool, a missing fund, an unbuilt store)
      // surfaces as a CLEAN FAILURE — NEVER a fabricated input (no fake data driving a real-looking
      // attribution). The operation's declared fund/window (the abstract args the analyst task names)
      // drive the marts read.
      // PROOF-ONLY SEAM — when the dispatch-proof fixture plan is active the plan's args are ALREADY
      // CONCRETE (the dispatch proofs feed ready-to-dispatch args to exercise the dispatch/
      // journal mechanics WITHOUT the resolution), so the resolve step is a PASS-THROUGH: it carries
      // the plan's concrete args straight to dispatch unchanged. NO-OP in production:
      // AGENTINVEST_DISPATCH_FIXTURE_PLAN is unset everywhere except those proofs, so the real
      // `resolvePlan` (the marts-in-the-loop) runs and a step's abstract args are resolved against
      // the marts. This keeps the frozen dispatch proofs green (their fixture args are
      // pre-resolved) while the full-chain demo runs the real resolution.
      const resolutionWindow = buildResolutionWindow(task);
      const resolve = process.env.AGENTINVEST_DISPATCH_FIXTURE_PLAN
        ? {
            resolvedSteps: plan.steps.map((s, index): ResolvedStep => ({
              index,
              soId: s.soId,
              status: 'resolved' as const,
              args: s.args,
              resolution: {
                soId: s.soId,
                fundId: '(fixture)',
                fundName: '(fixture — args pre-resolved by the dispatch proof)',
                beginDate: '',
                endDate: '',
                periodDays: 0,
                beginNav: '0',
                endNav: '0',
                args: s.args,
                computedBy: 'fixture:dispatch-proof',
              },
            })),
            resolvedCount: plan.steps.length,
            unresolvedCount: 0,
          }
        : await resolvePlan(ctx, plan, resolutionWindow);
      ctx.console.log(
        `[investment-operation] resolved ${resolve.resolvedSteps.length} step(s) against the marts ` +
          `(fund=${resolutionWindow.fundId ?? '(none)'}): ${resolve.resolvedCount} resolved, ` +
          `${resolve.unresolvedCount} surfaced clean failure(s); outcomes=[${resolve.resolvedSteps
            .map((r) => `${r.soId}:${r.status}`)
            .join(', ')}]`,
      );

      // ── SEAM 2 — DISPATCH ────────────────────────────────────────────────
      // RUN the plan: dispatch each RESOLVED step's CONCRETE args to the `bd09` service via
      // `ctx.serviceClient(BD09_SERVICE).execute_so({ soId, args })`, IN PARALLEL
      // (`Promise.allSettled` over the steps), and collect the per-step outcomes. Now dispatching
      // the marts-derived RESOLVED args (the resolve step above), so the planner's plan is actually
      // executed to REAL results. Three properties, all proven on THIS production VO (see
      // scripts/dispatch-fanout-proof.mjs + scripts/dispatch-crash-proof.mjs):
      //   - PARALLEL: N RPCs from one handler complete in ~max(step) not ~sum —
      //     intra-handler outbound fan-out.
      //   - CLEAN PARTIAL-FAILURE: a deterministic bd09 TerminalError, or an UNRESOLVED
      //     step (never dispatched on fabricated inputs), is captured as a clean {status:'rejected'}
      //     step-failure, the siblings still complete, the failure is SURFACED in stepResults
      //     (allSettled, NOT Promise.all which would fail-fast; NOT a whole-operation abort).
      //   - JOURNALED: each execute_so is the LEGAL Restate shape — a journaled RPC
      //     at the handler top level, NO context-action nested in a ctx.run closure
      //     — so a crash/replay reads the dispatched results back, tools not re-run.
      const dispatch = await dispatchResolvedPlan(ctx, resolve.resolvedSteps);
      ctx.console.log(
        `[investment-operation] dispatched ${dispatch.stepResults.length} step(s): ` +
          `${dispatch.fulfilledCount} fulfilled, ${dispatch.rejectedCount} surfaced clean failure(s); ` +
          `outcomes=[${dispatch.stepResults
            .map((r) => `${r.soId}:${r.status}`)
            .join(', ')}]`,
      );

      // PROOF-ONLY SEAM — env-gated durable pause in the between-DISPATCH-and-
      // terminal-write window, the dispatch-crash-replay counterpart of the
      // between-plan pause above. It exists SOLELY so the dispatch journaled-replay
      // proof can SIGKILL the production VO AFTER the dispatched execute_so RPCs are
      // journaled but BEFORE the terminal `ctx.set('state','completed')`. NO-OP in
      // production (AGENTINVEST_DISPATCH_CRASH_DELAY_MS unset everywhere except the
      // dispatch-crash harness → the `ctx.sleep` is never reached, no journal entry
      // added, the journal shape identical to production). The crash here proves the
      // dispatched stepResults are JOURNALED: replay reads them back, the tools
      // (bd09.execute_so) are NOT re-executed (the resumed stepResults equal the
      // pre-crash ones).
      const dispatchCrashDelayMs = Number(process.env.AGENTINVEST_DISPATCH_CRASH_DELAY_MS ?? 0);
      if (dispatchCrashDelayMs > 0) {
        ctx.console.warn(
          `[investment-operation] PROOF-ONLY durable pause ${dispatchCrashDelayMs}ms ` +
            `(AGENTINVEST_DISPATCH_CRASH_DELAY_MS set) — crash-proof window between the ` +
            `journaled dispatch and the terminal state write. Never set in production.`,
        );
        await ctx.sleep(dispatchCrashDelayMs);
      }

      // ── SEAM 3 — HIGH-STAKES APPROVAL GATE ───────────────────────────────
      // The awaitable approval gate: if the journaled plan is high-stakes
      // (plan.riskScore >= HIGH_STAKES_THRESHOLD) the operation PAUSES on a durable
      // `ctx.awakeable` for an operator decision, notifies the operator (a journaled
      // record + the awakeable id — no Operator UI, resolved via the Restate
      // CLI/admin), and awaits with a durable timeout. APPROVE → proceed; REJECT →
      // a journaled "aborted-by-operator" abort-trace + a terminal OperationAbortedError;
      // TIMEOUT → a journaled "aborted-by-timeout" abort-trace + a terminal abort.
      // Below the threshold the gate is a NO-OP (the operation proceeds straight
      // through) — for BD-09's READ-ONLY tools the riskScore stays below a sensible
      // high-stakes threshold, so the gate is a CONFIGURABLE THRESHOLD NOT EXERCISED
      // BY DEFAULT; the mechanism is the deliverable, proven by a forced-fire proof.
      // The gate is a REUSABLE COMPONENT (not a second reasoning loop) — the NAV
      // -publish workflow (the first REAL wiring) reuses it at its irreversible step.
      // The abort is wrapped to journal an aborted state BEFORE re-throwing the
      // terminal error, so `status` surfaces the aborted operation cleanly (replay
      // reads it back; the terminal error does not retry-storm).
      let gateOutcome: { gated: boolean; awakeableId: string | null };
      try {
        const outcome = await highStakesApprovalGate(ctx, operationId, {
          riskScore: plan.riskScore,
          summary: plan.summary,
          stepCount: plan.steps.length,
          selectedSoIds: plan.steps.map((s) => s.soId),
        });
        // Capture the gate decision for the audit record. For BD-09's read-only analytics the gate
        // is a no-op (gated:false) — the riskScore stays below the threshold; the audit record
        // states it honestly (the gate is the mechanism; the real high-stakes use is the
        // NAV publish).
        gateOutcome = outcome.gated
          ? { gated: true, awakeableId: outcome.awakeableId }
          : { gated: false, awakeableId: null };
      } catch (err) {
        if (err instanceof OperationAbortedError) {
          ctx.set<OperationState>('state', {
            status: 'aborted',
            plan,
            resolvedSteps: resolve.resolvedSteps,
            stepResults: dispatch.stepResults,
            aggregated: null,
            auditRecord: null,
            abort: { kind: err.abortKind, reason: err.message },
          });
          // Re-throw the TERMINAL error — Restate ends the invocation aborted (a
          // 4xx on the ingress), with NO retry-storm. The aborted state above is
          // journaled first so a `status` read shows the clean aborted outcome.
          throw err;
        }
        throw err;
      }

      // PROOF-ONLY SEAM — env-gated durable pause in the between-APPROVAL-DECISION-and
      // -terminal-write window. It exists SOLELY so the approval-gate replay-safety
      // proof can SIGKILL the production VO AFTER the operator's decision has journaled
      // (the awakeable resolved) but BEFORE the terminal `ctx.set('state','completed')`.
      // On resume the journaled decision is READ BACK — the gate does NOT re-create the
      // awakeable or re-prompt. NO-OP in production: AGENTINVEST_APPROVAL_CRASH_DELAY_MS
      // is unset everywhere except the approval-proof harness → the `ctx.sleep` is never
      // reached, no journal entry added, the journal shape identical to production.
      const approvalCrashDelayMs = Number(process.env.AGENTINVEST_APPROVAL_CRASH_DELAY_MS ?? 0);
      if (approvalCrashDelayMs > 0) {
        ctx.console.warn(
          `[investment-operation] PROOF-ONLY durable pause ${approvalCrashDelayMs}ms ` +
            `(AGENTINVEST_APPROVAL_CRASH_DELAY_MS set) — crash-proof window between the ` +
            `journaled approval decision and the terminal state write. Never set in production.`,
        );
        await ctx.sleep(approvalCrashDelayMs);
      }

      // ── SEAM 4 — AGGREGATE ───────────────────────────────────────────────
      // Combine the dispatched step results into a coherent attribution answer: the fund's total
      // return (SO-09-01) + the per-sector contribution breakdown (SO-09-05), with the
      // COHERENCE INVARIANT as the correctness check — the per-sector contributions RECONCILE to
      // the total return (both draw on one underlying per-segment NAV-delta derivation, so they tie
      // by construction; a divergence catches a wrong tool compute / misrouted dispatch / pluck
      // bug). HONEST PARTIAL-FAILURE: if a step FAILED, the aggregate
      // SURFACES it (coherent:false + incoherenceReason) — it does NOT fabricate a number. Pure
      // logic; no context action.
      const aggregated = aggregateResults(dispatch.stepResults, plan);
      ctx.console.log(
        `[investment-operation] aggregated: coherent=${aggregated.coherent} ` +
          `totalReturn=${aggregated.totalReturn ?? '(missing)'} ` +
          `contributionSum=${aggregated.contributionSum ?? '(missing)'} ` +
          `reconciles=${aggregated.reconciles}` +
          (aggregated.incoherenceReason ? ` — ${aggregated.incoherenceReason}` : ''),
      );

      const gateDecision: GateDecisionRecord = {
        gated: gateOutcome.gated,
        riskScore: plan.riskScore,
        approvedAwakeableId: gateOutcome.awakeableId,
      };

      // ── SEAM 5 — CLOSE (the journaled audit record) ──────────────────────
      // Build the structured audit record of the whole operation (task, plan, resolved args, step
      // results, aggregate, gate decision) and write it via a journaled `ctx.run` so it is recorded
      // EXACTLY-ONCE: a crash AFTER the close reads the journaled record back, it is NOT re-emitted.
      // A PLAIN journaled record — the hash-chained, tamper-evident S3 export (7-year fiduciary
      // retention) is NOT built here. The `ctx.run` closure is a plain side effect
      // (build + log the record); it makes no further context action (the legal shape).
      const auditRecord = await ctx.run('operation-closed', (): OperationAuditRecord => {
        const record = buildAuditRecord({
          operationId,
          task: planTask,
          plan,
          resolvedSteps: resolve.resolvedSteps,
          stepResults: dispatch.stepResults,
          aggregated,
          gateDecision,
        });
        ctx.console.log(
          `[investment-operation] CLOSE (journaled audit record): operation-closed ` +
            `operationId=${operationId} steps=${record.plan.steps.length} ` +
            `coherent=${record.aggregated.coherent} gated=${record.gateDecision.gated}.`,
        );
        return record;
      });

      ctx.set<OperationState>('state', {
        status: 'completed',
        plan,
        resolvedSteps: resolve.resolvedSteps,
        stepResults: dispatch.stepResults,
        aggregated,
        auditRecord,
        abort: null,
      });

      return {
        operationId,
        plan,
        selectedSoIds: plan.steps.map((s) => s.soId),
        resolvedSteps: resolve.resolvedSteps,
        stepResults: dispatch.stepResults,
        fulfilledCount: dispatch.fulfilledCount,
        rejectedCount: dispatch.rejectedCount,
        aggregated,
        auditRecord,
        status: 'completed',
        kind: task.kind ?? null,
        orchestrator: INVESTMENT_OPERATION_NAME,
      };
    },

    /**
     * Read the recorded state for this operationId from the virtual object's
     * key-value store. A shared (read-only) handler — it does not mutate state.
     * Returns null if no operation has run under this key.
     */
    async status(ctx: ObjectContext): Promise<OperationState | null> {
      return (await ctx.get<OperationState>('state')) ?? null;
    },
  },
});
