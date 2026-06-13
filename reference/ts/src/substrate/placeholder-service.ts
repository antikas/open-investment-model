/**
 * agentINVEST substrate-proof placeholder service.
 *
 * This is the single placeholder Restate handler the substrate floor registers.
 * It exists only to prove the substrate end-to-end: that the shared Restate
 * instance can register an agentINVEST handler, route an invocation to it, and
 * journal a step. It does NO business logic.
 *
 * Topology note: this is a model-free Restate *service* — a
 * namespace + dispatch boundary — NOT an "agent". It carries no reasoning loop.
 * The orchestrating loop (the single `InvestmentOperation.plan()` reasoning
 * step) lives elsewhere; the per-Business-Domain layer (also a model-free
 * service, never an agent) is later still. Nothing here pre-judges either.
 *
 * The journaled step: `ctx.run('substrate-proof-step', ...)` records a single
 * durable step into the Restate journal. On a replay (a crash + retry within
 * the same invocation) the recorded value is read back from the journal rather
 * than re-executed — that is the journal-as-source-of-truth property the floor
 * proves. The substrate smoke exercises both the baseline path and the
 * crash-and-replay path.
 */
import { service, type Context } from '@restatedev/restate-sdk';

export const PLACEHOLDER_SERVICE_NAME = 'agentinvestPlaceholder';

export interface PingInput {
  /** When true, the handler crashes once before the journaled step, forcing a
   *  Restate retry of the whole invocation. The journaled step must then
   *  replay (same value), not re-execute. */
  crashOnFirstAttempt?: boolean;
}

export interface PingResult {
  /** A UUID generated once via ctx.run and journaled — stable across replays. */
  stepId: string;
  /** How many times the handler body ran for this invocation (1 = no replay; 2 = one crash + one retry). */
  attempts: number;
  /** Fixed marker so a consumer can confirm which surface answered. */
  service: typeof PLACEHOLDER_SERVICE_NAME;
}

export interface HealthResult {
  ok: true;
  service: typeof PLACEHOLDER_SERVICE_NAME;
}

// Process-local attempt counter. Restate retries re-run the handler body in the
// SAME process here (single-node dev), so this increments on each (re)run of a
// given invocation. It is reset by the smoke between its two phases.
let attemptCounter = 0;

/** Test-only hook: reset the attempt counter between smoke phases. */
export function __resetAttemptCounterForSmoke(): void {
  attemptCounter = 0;
}

export const placeholderService = service({
  name: PLACEHOLDER_SERVICE_NAME,
  handlers: {
    /**
     * Journal one step and return its journaled value.
     *
     * `ctx.run` wraps the side-effecting work (here: generating a UUID) so
     * Restate records its result in the journal. If `crashOnFirstAttempt` is
     * set, the handler throws AFTER the step is journaled but on the first
     * body run, forcing Restate to retry; on retry the step is read back from
     * the journal (same UUID) rather than regenerated.
     */
    async ping(ctx: Context, input: PingInput = {}): Promise<PingResult> {
      attemptCounter += 1;
      const myAttempt = attemptCounter;

      const stepId = await ctx.run('substrate-proof-step', () => {
        return crypto.randomUUID();
      });
      ctx.console.log(`[agentinvest-placeholder] attempt #${myAttempt} journaled step-id=${stepId}`);

      if (input.crashOnFirstAttempt && myAttempt === 1) {
        ctx.console.log(`[agentinvest-placeholder] attempt #${myAttempt} forced crash (will retry + replay)`);
        // A non-terminal error: Restate retries the whole invocation. The
        // journaled step above replays with the same stepId on the next run.
        throw new Error('forced crash to exercise journal replay');
      }

      return { stepId, attempts: myAttempt, service: PLACEHOLDER_SERVICE_NAME };
    },

    /** Liveness probe over the Restate ingress — confirms the service registered. */
    async health(_ctx: Context): Promise<HealthResult> {
      return { ok: true, service: PLACEHOLDER_SERVICE_NAME };
    },
  },
});
