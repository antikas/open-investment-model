/**
 * Unit proof of the HIGH-STAKES APPROVAL GATE (seam 3) — the threshold no-op /
 * fires boundary, the three outcomes (approve / reject / timeout), the journaled
 * notify + abort-trace records, and the terminal-abort shape, isolated from the
 * substrate with a fake `ObjectContext`.
 *
 * The LIVE, production-VO proof (the durable pause, a crash mid-pause resuming
 * still-awaiting, resolving via the CLI/admin ingress, and replay-safety) is
 * `scripts/approval-gate-proof.mjs`. THIS test pins the gate's in-handler control
 * flow deterministically: a fake awakeable whose promise is resolved/rejected on
 * demand (or times out via `orTimeout`), a fake `ctx.run` that runs its closure and
 * records the journaled value, and assertions on the records + the thrown
 * `OperationAbortedError`.
 */
import { describe, expect, it, vi } from 'vitest';
import { TerminalError, TimeoutError, type ObjectContext } from '@restatedev/restate-sdk';
import {
  highStakesApprovalGate,
  OperationAbortedError,
  HIGH_STAKES_THRESHOLD,
  type ApprovalDecision,
  type GatedPlanSummary,
} from './approval-gate.js';

type OrTimeoutPromise<T> = Promise<T> & { orTimeout(ms: number): OrTimeoutPromise<T> };

/** A RestatePromise-like wrapper exposing `orTimeout` over a plain promise. */
function withOrTimeout<T>(p: Promise<T>): OrTimeoutPromise<T> {
  const wrapped = p as OrTimeoutPromise<T>;
  wrapped.orTimeout = (ms: number): OrTimeoutPromise<T> =>
    withOrTimeout(
      Promise.race([
        p,
        new Promise<T>((_, reject) => setTimeout(() => reject(new TimeoutError()), ms)),
      ]),
    );
  return wrapped;
}

interface FakeCtxOptions {
  /** How the awakeable promise settles: 'resolve' a decision, 'reject' terminally, or 'never' (→ timeout). */
  awakeable:
    | { mode: 'resolve'; decision: ApprovalDecision }
    | { mode: 'reject'; reason: string }
    | { mode: 'never' };
}

interface FakeCtxCapture {
  ctx: ObjectContext;
  runRecords: Array<{ name: string; value: unknown }>;
  /** The OIM-142 cycle-2 additive registry resolve-marks the gate fired (by decision). */
  resolveMarks: Array<{ decision: 'approved' | 'rejected' | 'aborted' }>;
  awakeableId: string;
}

/**
 * A fake ObjectContext implementing only the surface the gate uses: `awakeable`,
 * `run` (executes the closure, records its journaled return), `console`. The
 * awakeable's promise is driven by the options.
 */
function fakeCtx(opts: FakeCtxOptions): FakeCtxCapture {
  const runRecords: Array<{ name: string; value: unknown }> = [];
  const resolveMarks: Array<{ decision: 'approved' | 'rejected' | 'aborted' }> = [];
  const awakeableId = `prom_1ABC_fake_awakeable_id`;

  let promise: Promise<ApprovalDecision>;
  if (opts.awakeable.mode === 'resolve') {
    promise = Promise.resolve(opts.awakeable.decision);
  } else if (opts.awakeable.mode === 'reject') {
    const reason = opts.awakeable.reason;
    promise = Promise.reject(new TerminalError(reason, { errorCode: 403 }));
  } else {
    // never settles → orTimeout fires the TimeoutError.
    promise = new Promise<ApprovalDecision>(() => {});
  }

  const ctx = {
    awakeable: <T>() => ({ id: awakeableId, promise: withOrTimeout(promise) as unknown as Promise<T> }),
    run: async (name: string, action: () => unknown) => {
      const value = await action();
      runRecords.push({ name, value });
      return value;
    },
    // The additive OIM-142 pending-approvals registry sends are FIRE-AND-FORGET — the
    // gate does not await them and does not depend on them; the fake provides a no-op
    // send-client (capturing the cycle-2 terminal-path `resolve` marks so the test can
    // assert the entry leaves the queue on every path) + a fixed clock so the gate's
    // control flow under test is unchanged.
    objectSendClient: () => ({
      register: () => {},
      resolve: (input: { decision: 'approved' | 'rejected' | 'aborted' }) => {
        resolveMarks.push(input);
      },
    }),
    date: { now: async () => 1_700_000_000_000 },
    console: { log: () => {}, warn: () => {}, error: () => {} },
  } as unknown as ObjectContext;

  return { ctx, runRecords, resolveMarks, awakeableId };
}

function gatedPlan(riskScore: number): GatedPlanSummary {
  return {
    riskScore,
    summary: 'forced-fire fixture plan',
    stepCount: 2,
    selectedSoIds: ['SO-09-01', 'SO-09-05'],
  };
}

describe('highStakesApprovalGate — the seam-3 control flow', () => {
  it('NO-OP below the threshold: riskScore < threshold → gated:false, no awakeable, no records', async () => {
    const { ctx, runRecords } = fakeCtx({ awakeable: { mode: 'never' } });
    const awakeableSpy = vi.spyOn(ctx, 'awakeable');
    const below = HIGH_STAKES_THRESHOLD - 0.1;
    const outcome = await highStakesApprovalGate(ctx, 'op-below', gatedPlan(below));
    expect(outcome).toEqual({ gated: false });
    expect(awakeableSpy).not.toHaveBeenCalled();
    expect(runRecords).toHaveLength(0);
  });

  it('FIRES at/above the threshold + APPROVE: pauses, notifies, returns the approval', async () => {
    const { ctx, runRecords, resolveMarks, awakeableId } = fakeCtx({
      awakeable: { mode: 'resolve', decision: { approved: true } },
    });
    const outcome = await highStakesApprovalGate(ctx, 'op-approve', gatedPlan(HIGH_STAKES_THRESHOLD));
    expect(outcome).toMatchObject({ gated: true, decision: { approved: true }, awakeableId });

    // The operator-notify record was journaled (the gate fired) — carrying the
    // awakeable id + the riskScore the operator reads.
    const notify = runRecords.find((r) => r.name === 'approval-notify');
    expect(notify).toBeDefined();
    expect(notify?.value).toMatchObject({
      kind: 'approval-required',
      operationId: 'op-approve',
      awakeableId,
      riskScore: HIGH_STAKES_THRESHOLD,
    });
    // No abort-trace on an approve.
    expect(runRecords.find((r) => r.name === 'abort-trace')).toBeUndefined();
    // OIM-142 cycle-2: the additive registry resolve-mark fired `approved` so the entry
    // LEAVES the pending queue (additive — it did not change the approve outcome above).
    expect(resolveMarks).toEqual([{ decision: 'approved' }]);
  });

  it('REJECT (decision.approved=false): journaled "aborted-by-operator" + terminal OperationAbortedError', async () => {
    const { ctx, runRecords, resolveMarks } = fakeCtx({
      awakeable: { mode: 'resolve', decision: { approved: false, reason: 'fails the mandate check' } },
    });
    await expect(highStakesApprovalGate(ctx, 'op-reject', gatedPlan(0.9))).rejects.toMatchObject({
      name: 'OperationAbortedError',
      abortKind: 'aborted-by-operator',
    });
    const abort = runRecords.find((r) => r.name === 'abort-trace');
    expect(abort?.value).toMatchObject({
      kind: 'aborted-by-operator',
      operationId: 'op-reject',
      reason: 'fails the mandate check',
    });
    // OIM-142 cycle-2: the reject path marks the entry resolved `rejected` (it leaves the queue).
    expect(resolveMarks).toEqual([{ decision: 'rejected' }]);
  });

  it('REJECT via a terminal awakeable rejection (operator /reject on the ingress): aborted-by-operator', async () => {
    const { ctx, runRecords, resolveMarks } = fakeCtx({ awakeable: { mode: 'reject', reason: 'operator rejected via CLI' } });
    await expect(highStakesApprovalGate(ctx, 'op-reject-ingress', gatedPlan(0.95))).rejects.toMatchObject({
      name: 'OperationAbortedError',
      abortKind: 'aborted-by-operator',
    });
    const abort = runRecords.find((r) => r.name === 'abort-trace');
    expect(abort?.value).toMatchObject({ kind: 'aborted-by-operator' });
    // OIM-142 cycle-2: an out-of-band (CLI/ingress) reject the awakeable absorbed also
    // marks the entry resolved `rejected` — it leaves the queue, not only a UI decision.
    expect(resolveMarks).toEqual([{ decision: 'rejected' }]);
  });

  it('TIMEOUT (no decision within APPROVAL_TIMEOUT): journaled "aborted-by-timeout" + terminal abort', async () => {
    // A tiny env-set timeout so orTimeout fires fast; the gate must abort by timeout.
    const prev = process.env.AGENTINVEST_APPROVAL_TIMEOUT_MS;
    process.env.AGENTINVEST_APPROVAL_TIMEOUT_MS = '20';
    // Re-import to pick up the env-driven default (the module reads it at load).
    vi.resetModules();
    const mod = await import('./approval-gate.js');
    try {
      const { ctx, runRecords, resolveMarks } = fakeCtx({ awakeable: { mode: 'never' } });
      await expect(mod.highStakesApprovalGate(ctx, 'op-timeout', gatedPlan(0.99))).rejects.toMatchObject({
        name: 'OperationAbortedError',
        abortKind: 'aborted-by-timeout',
      });
      const abort = runRecords.find((r) => r.name === 'abort-trace');
      expect(abort?.value).toMatchObject({ kind: 'aborted-by-timeout', operationId: 'op-timeout' });
      // OIM-142 cycle-2: the timeout path marks the entry resolved `aborted` (it leaves the queue).
      expect(resolveMarks).toEqual([{ decision: 'aborted' }]);
    } finally {
      if (prev === undefined) delete process.env.AGENTINVEST_APPROVAL_TIMEOUT_MS;
      else process.env.AGENTINVEST_APPROVAL_TIMEOUT_MS = prev;
      vi.resetModules();
    }
  });

  it('OperationAbortedError is a Restate TerminalError (no retry-storm)', async () => {
    const { ctx } = fakeCtx({ awakeable: { mode: 'resolve', decision: { approved: false } } });
    const err = await highStakesApprovalGate(ctx, 'op', gatedPlan(0.8)).catch((e) => e);
    expect(err).toBeInstanceOf(OperationAbortedError);
    expect(err).toBeInstanceOf(TerminalError);
  });
});
