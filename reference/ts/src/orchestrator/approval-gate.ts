/**
 * The HIGH-STAKES APPROVAL GATE (seam 3) — a reusable component.
 *
 * The human-in-the-loop fiduciary control. When a plan is high-stakes
 * (`plan.riskScore >= HIGH_STAKES_THRESHOLD`) the orchestrator must PAUSE for an
 * operator decision before it proceeds to an irreversible action. This module is
 * that gate, built as a REUSABLE COMPONENT (not a second reasoning loop): the
 * `InvestmentOperation` orchestrator calls it at seam 3 today, and the NAV-publish
 * workflow (the first REAL high-stakes wiring, a forward item) will call the same
 * component at its irreversible step.
 *
 * THE MECHANISM (Restate `ctx.awakeable`):
 *
 *  - Below the threshold → NO-OP. The gate returns immediately and the operation
 *    proceeds straight through. For BD-09's READ-ONLY tool surface the planner's
 *    read-only-analytics riskScores stay below a sensible high-stakes threshold, so
 *    the gate is a CONFIGURABLE THRESHOLD NOT EXERCISED BY DEFAULT — it is the
 *    mechanism that is the deliverable here, proven by a FORCED-FIRE proof.
 *
 *  - At/above the threshold → PAUSE. The gate creates a `ctx.awakeable<ApprovalDecision>()`
 *    — a DURABLE suspension point. Restate journals the awakeable and SUSPENDS the
 *    invocation until the awakeable is resolved (or the operation is rejected, or
 *    the durable timeout fires). The suspension SURVIVES A CRASH: on replay the
 *    awakeable id is stable and the operation resumes STILL-AWAITING — it does NOT
 *    re-prompt. Once a decision is resolved it is journaled, so a crash AFTER the
 *    decision reads the recorded decision back (NOT a second prompt).
 *
 *  - The operator is NOTIFIED via a JOURNALED `ctx.run` record (the operationId +
 *    the awakeable id + the plan summary + the riskScore). There is NO Operator UI
 *    (a forward item) — "notify" is this record the operator reads plus the
 *    awakeable id they resolve via the Restate CLI/admin ingress
 *    (`POST {ingress}/restate/awakeables/{id}/resolve|reject`).
 *
 *  - The await is BOUNDED by a DURABLE timeout — `awakeable.promise.orTimeout(
 *    APPROVAL_TIMEOUT)`. The timer is Restate's durable timer (NOT a wall-clock
 *    `setTimeout`): it survives a crash and is replay-safe. On timeout the gate
 *    aborts cleanly.
 *
 * THE OUTCOMES:
 *
 *  - APPROVE (`{approved: true}`) → the gate returns; the operation proceeds.
 *  - REJECT (`{approved: false, reason}`) → the gate writes a journaled
 *    `"aborted-by-operator"` abort-trace and throws `OperationAbortedError` — a
 *    Restate `TerminalError` (NO retry-storm; the operation ends aborted, surfaced
 *    cleanly via `status`).
 *  - TIMEOUT → the gate writes a journaled `"aborted-by-timeout"` abort-trace and
 *    throws `OperationAbortedError` (terminal, same clean abort).
 *
 * THE LEGAL RESTATE SHAPE. The awakeable creation, the
 * operator-notify `ctx.run`, the abort-trace `ctx.run` and the durable timeout are
 * ALL top-level context actions — none is nested inside another `ctx.run` closure
 * (a context action inside a `ctx.run` body is the Restate determinism
 * anti-pattern). The `ctx.run` closures here do plain side effects (build + log a
 * record) whose RESULT is journaled; they never make further journaled calls.
 *
 * HONEST BOUNDARY (v0.1). This is the MECHANISM + a forced-fire proof — it is NOT
 * wired to fire for the read-only BD-09 tools by default (the first REAL wiring is
 * the NAV-publish gate, a forward item). There is NO Operator UI (a forward item) —
 * notify is a journaled record + the awakeable id, resolved via the CLI/admin.
 * `HIGH_STAKES_THRESHOLD` and `APPROVAL_TIMEOUT` are PROVISIONAL configurable
 * defaults, OWNER-TO-RATIFY (the substrate decision deferred the numerics — they
 * are declared, NOT validated). Synthetic data; supervised-autonomous; frontier-only.
 */
import { TerminalError, TimeoutError, type ObjectContext } from '@restatedev/restate-sdk';
import { approvalRegistry, APPROVAL_REGISTRY_OBJECT } from './approval-registry.js';

/**
 * The operator's decision on a high-stakes plan, returned by resolving the gate's
 * awakeable. Resolved by an operator via the Restate CLI/admin ingress (no Operator
 * UI yet); deserialised by the SDK from the resolve payload.
 */
export interface ApprovalDecision {
  /** True → proceed; false → abort the operation cleanly (terminal). */
  approved: boolean;
  /** Optional operator-supplied reason (recorded in the abort-trace on a reject). */
  reason?: string;
}

/**
 * The HTTP-ish status the clean operator/timeout abort surfaces as on the ingress.
 * A 4xx (not 5xx) so it reads as a deliberate, final decision — never a transient
 * fault to retry.
 */
export const OPERATION_ABORTED_CODE = 403;

/**
 * Raised when a high-stakes operation is ABORTED — either rejected by the operator
 * or timed out awaiting a decision. It extends Restate's `TerminalError`: the abort
 * is the gate's deliberate, FINAL decision (NOT a transient fault), so Restate must
 * NOT retry it (a plain `Error` would retry-storm), and the ingress surfaces it as a
 * 4xx. This is the terminal-abort discipline applied to the gate.
 */
export class OperationAbortedError extends TerminalError {
  /** Which abort path produced this — an operator reject or a decision timeout. */
  readonly abortKind: 'aborted-by-operator' | 'aborted-by-timeout';
  constructor(abortKind: 'aborted-by-operator' | 'aborted-by-timeout', detail?: string) {
    super(
      abortKind === 'aborted-by-operator'
        ? `InvestmentOperation aborted by the operator${detail ? `: ${detail}` : '.'}`
        : `InvestmentOperation aborted: no operator decision within the approval timeout${
            detail ? ` (${detail})` : '.'
          }`,
      { errorCode: OPERATION_ABORTED_CODE },
    );
    this.name = 'OperationAbortedError';
    this.abortKind = abortKind;
  }
}

/**
 * PROVISIONAL configurable defaults — OWNER-TO-RATIFY. The substrate decision
 * deferred the numerics ("indicative default, owner-to-ratify"); these are sensible
 * starting values, NOT validated thresholds. They are configurable via env so a
 * proof can force the gate (a low threshold) or shorten the timeout (a fast
 * timeout-abort proof) without code changes. Production runs with the env unset →
 * these defaults.
 *
 *  - `HIGH_STAKES_THRESHOLD` (default 0.7): a plan with `riskScore >= 0.7` is
 *    high-stakes and gated. The planner's observed read-only-analytics
 *    riskScores (~0.05–0.6) stay below it, so BD-09's read-only surface does NOT
 *    fire by default — the honest "configurable threshold not exercised" property.
 *  - `APPROVAL_TIMEOUT` (default 86_400_000 ms = 24h): how long the gate awaits an
 *    operator decision before a clean timeout-abort. A day is a sensible operator
 *    SLA for a fiduciary approval; the proof shortens it to seconds.
 */
export const HIGH_STAKES_THRESHOLD = Number(process.env.AGENTINVEST_HIGH_STAKES_THRESHOLD ?? 0.7);
export const APPROVAL_TIMEOUT_MS = Number(process.env.AGENTINVEST_APPROVAL_TIMEOUT_MS ?? 86_400_000);

/** The minimal plan view the gate needs — its riskScore + a human summary. */
export interface GatedPlanSummary {
  /** How high-stakes the plan is, in [0,1] — the value that drives the gate. */
  riskScore: number;
  /** A one-line description of the plan, surfaced to the operator. */
  summary?: string | null;
  /** How many steps the plan has (surfaced in the notify record). */
  stepCount: number;
  /** The selected tool soIds (surfaced in the notify record). */
  selectedSoIds: string[];
}

/** The journaled operator-notify record — what the operator reads to make the call. */
export interface ApprovalNotice {
  kind: 'approval-required';
  operationId: string;
  /** The awakeable id the operator resolves via the Restate CLI/admin ingress. */
  awakeableId: string;
  riskScore: number;
  threshold: number;
  summary: string | null;
  stepCount: number;
  selectedSoIds: string[];
}

/** The journaled abort-trace record (operator-reject or timeout). */
export interface AbortTrace {
  kind: 'aborted-by-operator' | 'aborted-by-timeout';
  operationId: string;
  awakeableId: string;
  riskScore: number;
  reason: string | null;
}

/** The gate's outcome when it does NOT throw — fired+approved, or not fired. */
export type ApprovalOutcome =
  | { gated: false }
  | { gated: true; decision: ApprovalDecision; awakeableId: string };

/**
 * ADDITIVE registry resolve-mark — mark this operation's
 * pending-approvals entry RESOLVED on the terminal path the gate just processed, so the
 * entry LEAVES the pending queue for EVERY resolution path (approve / reject / timeout /
 * any out-of-band resolve the awakeable absorbs), not only the UI's own resolve.
 *
 * GENUINELY ADDITIVE — the gate's pause/resolve/timeout BEHAVIOUR is UNCHANGED. This is
 * the SAME top-level FIRE-AND-FORGET send pattern as the `register` mirror above: a
 * journaled one-way `objectSendClient(...).resolve(...)` the gate does NOT await and does
 * NOT depend on, issued AFTER the outcome is already known (after the awakeable settled /
 * the timeout fired / the reject decision is in hand). The awakeable remains the SOLE
 * decision-of-record; this mark is a passive update of the read mirror. A lost/failed/
 * duplicated send cannot affect the gate (the `resolve` handler is idempotent). Issuing a
 * top-level journaled send on every terminal path keeps the legal Restate shape (no
 * context action nested in a `ctx.run`; deterministic on replay).
 */
function markRegistryResolved(
  ctx: ObjectContext,
  operationId: string,
  decision: 'approved' | 'rejected' | 'aborted',
): void {
  ctx
    .objectSendClient<typeof approvalRegistry>({ name: APPROVAL_REGISTRY_OBJECT }, operationId)
    .resolve({ decision });
}

/**
 * Run the high-stakes approval gate over a plan summary. Below the threshold this
 * is a no-op (returns `{gated: false}`); at/above it PAUSES on a durable awakeable,
 * notifies the operator (a journaled record), awaits the decision with a durable
 * timeout, and either returns the approval or throws `OperationAbortedError`
 * (terminal) on a reject or a timeout.
 *
 * @param ctx  the orchestrator's object context (the production VO's context).
 * @param operationId the VO key — recorded in the notify + abort-trace records.
 * @param plan a minimal plan view (riskScore + summary + step shape).
 * @returns `{gated: false}` below threshold, or `{gated: true, decision, awakeableId}`
 *          on an approve. Throws `OperationAbortedError` on a reject or a timeout.
 */
export async function highStakesApprovalGate(
  ctx: ObjectContext,
  operationId: string,
  plan: GatedPlanSummary,
  origin = 'investmentOperation',
): Promise<ApprovalOutcome> {
  // ── THRESHOLD CHECK — below → no-op (proceed) ─────────────────────────────
  // A pure comparison of the journaled plan's riskScore against the (provisional)
  // threshold. No context action — the riskScore is already journaled (it came
  // from the journaled plan), so this is deterministic on replay.
  if (plan.riskScore < HIGH_STAKES_THRESHOLD) {
    ctx.console.log(
      `[approval-gate] riskScore=${plan.riskScore} < threshold=${HIGH_STAKES_THRESHOLD} — ` +
        `NOT high-stakes; gate is a no-op, operation proceeds.`,
    );
    return { gated: false };
  }

  // ── PAUSE — create the durable awakeable (a top-level context action) ─────
  // This is the DURABLE suspension point. Restate journals the awakeable; the
  // invocation suspends here until the awakeable is resolved (approve/reject) or
  // the durable timeout fires. The id is stable across a crash/replay — a crash
  // mid-pause resumes STILL-AWAITING on the same awakeable, never re-prompting.
  const awakeable = ctx.awakeable<ApprovalDecision>();
  ctx.console.warn(
    `[approval-gate] riskScore=${plan.riskScore} >= threshold=${HIGH_STAKES_THRESHOLD} — ` +
      `HIGH-STAKES: PAUSING for operator approval. awakeableId=${awakeable.id}`,
  );

  // ── NOTIFY — a journaled ctx.run record the operator reads ────────────────
  // No Operator UI: the "notify" is this journaled record (operationId + awakeable
  // id + plan summary + riskScore) plus the awakeable id the operator resolves via
  // the Restate CLI/admin ingress. The closure is a PLAIN side effect (build + log
  // the record); its RESULT is journaled — it makes NO further context action (the
  // legal shape). On replay the recorded notice is read back, not re-emitted.
  await ctx.run('approval-notify', () => {
    const notice: ApprovalNotice = {
      kind: 'approval-required',
      operationId,
      awakeableId: awakeable.id,
      riskScore: plan.riskScore,
      threshold: HIGH_STAKES_THRESHOLD,
      summary: plan.summary ?? null,
      stepCount: plan.stepCount,
      selectedSoIds: plan.selectedSoIds,
    };
    ctx.console.warn(
      `[approval-gate] OPERATOR APPROVAL REQUIRED — ${JSON.stringify(notice)}. ` +
        `Resolve via: POST {ingress}/restate/awakeables/${awakeable.id}/resolve ` +
        `(body {"approved":true}) or /reject.`,
    );
    return notice;
  });

  // ── ADDITIVE PENDING-APPROVALS INDEX ──────────────────────────────────────
  // ALSO record this notice in the pending-approvals registry so a human surface
  // (the Operator UI's Approvals queue) can ENUMERATE the approvals awaiting a
  // decision WITHOUT tailing the handler log or the raw CLI. This is a top-level
  // FIRE-AND-FORGET send — the gate does NOT await it and does NOT depend on its
  // outcome, so the gate's pause/resolve/timeout behaviour is UNCHANGED (the
  // frozen-semantics constraint). The awakeable above is still the SOLE
  // decision path; this registry is a passive READ MIRROR of the already-journaled
  // notice, never a second control path. A lost/undelivered send leaves the gate
  // wholly unaffected (the awakeable id in the notice is the resolve path of record).
  const raisedAtMs = await ctx.date.now();
  ctx
    .objectSendClient<typeof approvalRegistry>({ name: APPROVAL_REGISTRY_OBJECT }, operationId)
    .register({
      operationId,
      awakeableId: awakeable.id,
      riskScore: plan.riskScore,
      threshold: HIGH_STAKES_THRESHOLD,
      summary: plan.summary ?? null,
      stepCount: plan.stepCount,
      selectedSoIds: plan.selectedSoIds,
      origin,
      raisedAt: new Date(raisedAtMs).toISOString(),
    });

  // ── AWAIT (with a DURABLE timeout) ────────────────────────────────────────
  // Bound the await on the awakeable with Restate's durable timer (orTimeout) —
  // NOT a wall-clock setTimeout. If the operator does not decide within
  // APPROVAL_TIMEOUT_MS the promise rejects with a Restate `TimeoutError` and the
  // gate aborts by timeout. The timer is durable + replay-safe: it survives a
  // crash and resumes counting from the journaled deadline.
  let decision: ApprovalDecision;
  try {
    decision = await awakeable.promise.orTimeout(APPROVAL_TIMEOUT_MS);
  } catch (err) {
    if (err instanceof TimeoutError) {
      // TIMEOUT → a journaled abort-trace + a terminal abort.
      ctx.console.error(
        `[approval-gate] no operator decision within ${APPROVAL_TIMEOUT_MS}ms — ABORTING BY TIMEOUT.`,
      );
      await ctx.run('abort-trace', () => {
        const trace: AbortTrace = {
          kind: 'aborted-by-timeout',
          operationId,
          awakeableId: awakeable.id,
          riskScore: plan.riskScore,
          reason: `no operator decision within ${APPROVAL_TIMEOUT_MS}ms`,
        };
        ctx.console.warn(`[approval-gate] abort-trace: ${JSON.stringify(trace)}`);
        return trace;
      });
      // Mark the pending-approvals entry resolved (aborted-by-timeout) so it LEAVES the
      // pending queue — additive fire-and-forget; the abort is the awakeable/timeout's.
      markRegistryResolved(ctx, operationId, 'aborted');
      throw new OperationAbortedError('aborted-by-timeout', `timeout ${APPROVAL_TIMEOUT_MS}ms`);
    }
    // Any non-timeout terminal rejection of the awakeable (e.g. an operator
    // `reject` via the ingress, which surfaces as a TerminalError) is also a
    // clean operator-driven abort.
    if (err instanceof TerminalError) {
      ctx.console.error(`[approval-gate] awakeable rejected by the operator — ABORTING. ${err.message}`);
      await ctx.run('abort-trace', () => {
        const trace: AbortTrace = {
          kind: 'aborted-by-operator',
          operationId,
          awakeableId: awakeable.id,
          riskScore: plan.riskScore,
          reason: err.message,
        };
        ctx.console.warn(`[approval-gate] abort-trace: ${JSON.stringify(trace)}`);
        return trace;
      });
      // Mark the pending-approvals entry resolved (rejected via the ingress) — additive
      // fire-and-forget; the awakeable's terminal rejection is the decision of record.
      markRegistryResolved(ctx, operationId, 'rejected');
      throw new OperationAbortedError('aborted-by-operator', err.message);
    }
    throw err;
  }

  // The decision is now journaled (the awakeable's resolved payload). A crash
  // AFTER this point reads the decision back from the journal — it does NOT
  // re-create the awakeable or re-prompt (replay-safety).
  if (!decision.approved) {
    // REJECT → a journaled abort-trace + a terminal abort.
    ctx.console.warn(
      `[approval-gate] operator REJECTED (reason=${decision.reason ?? '(none)'}) — ABORTING BY OPERATOR.`,
    );
    await ctx.run('abort-trace', () => {
      const trace: AbortTrace = {
        kind: 'aborted-by-operator',
        operationId,
        awakeableId: awakeable.id,
        riskScore: plan.riskScore,
        reason: decision.reason ?? null,
      };
      ctx.console.warn(`[approval-gate] abort-trace: ${JSON.stringify(trace)}`);
      return trace;
    });
    // Mark the pending-approvals entry resolved (rejected) so it LEAVES the pending
    // queue — additive fire-and-forget; the awakeable decision is of record.
    markRegistryResolved(ctx, operationId, 'rejected');
    throw new OperationAbortedError('aborted-by-operator', decision.reason);
  }

  // APPROVE → return the decision; the operation proceeds.
  ctx.console.log(`[approval-gate] operator APPROVED — operation proceeds.`);
  // Mark the pending-approvals entry resolved (approved) so it LEAVES the pending queue
  // for EVERY resolution path (incl. a UI/CLI approve the awakeable absorbed) — additive
  // fire-and-forget; the awakeable's approve is the decision of record.
  markRegistryResolved(ctx, operationId, 'approved');
  return { gated: true, decision, awakeableId: awakeable.id };
}
