/**
 * Unit proof of the DISPATCH step's collection logic (seam 2) — the
 * `Promise.allSettled` partial-failure contract, isolated from the substrate.
 *
 * The live, production-VO proofs (real RPCs, latency vs serial, journaled replay)
 * are `scripts/dispatch-fanout-proof.mjs`, `scripts/dispatch-crash-proof.mjs`, and
 * `scripts/dispatch-live-e2e.mjs`. THIS test pins the in-handler collection
 * behaviour deterministically with a fake `bd09` service client: a rejected step is
 * captured cleanly, the siblings still resolve, the failure is surfaced, and the
 * batch is NOT aborted (the `allSettled`-not-`all` property — the headline gate).
 */
import { describe, expect, it } from 'vitest';
import type { ObjectContext } from '@restatedev/restate-sdk';
import { dispatchPlan, dispatchResolvedPlan } from './dispatch.js';
import type { ExecuteSoOutput } from './bd09-service-contract.js';
import type { Plan } from './llm-service-contract.js';
import type { ResolvedStep } from './resolve.js';

/**
 * A fake ObjectContext whose `serviceClient(BD09_SERVICE)` returns a client whose
 * `execute_so` is driven by a per-soId script: a function returning the result, or
 * throwing to simulate a bd09 TerminalError. Only the surface `dispatchPlan` uses
 * is implemented.
 */
function fakeCtx(
  script: Record<string, (args: Record<string, unknown>) => ExecuteSoOutput | Promise<ExecuteSoOutput>>,
): ObjectContext {
  const client = {
    execute_so: async (input: { soId: string; args: Record<string, unknown> }): Promise<ExecuteSoOutput> => {
      const fn = script[input.soId];
      if (!fn) throw new Error(`unknown Service Operation '${input.soId}'`);
      return fn(input.args);
    },
  };
  return {
    serviceClient: () => client,
    console: { log: () => {}, warn: () => {}, error: () => {} },
  } as unknown as ObjectContext;
}

function ok(soId: string): ExecuteSoOutput {
  return {
    result: { value: 1 },
    provenance: { soId, tool: `tool-${soId}`, methodology: 'm' },
    computedBy: 'python:bd09',
  };
}

function plan(...soIds: string[]): Plan {
  return {
    steps: soIds.map((soId) => ({ soId, args: { k: soId }, rationale: null })),
    riskScore: 0.1,
    summary: 'fixture plan',
  };
}

describe('dispatchPlan — the seam-2 collection contract', () => {
  it('fans every step out and collects one fulfilled result per step (the happy path)', async () => {
    const ctx = fakeCtx({
      'SO-09-01': () => ok('SO-09-01'),
      'SO-09-02': () => ok('SO-09-02'),
      'SO-09-05': () => ok('SO-09-05'),
    });
    const res = await dispatchPlan(ctx, plan('SO-09-01', 'SO-09-02', 'SO-09-05'));
    expect(res.stepResults).toHaveLength(3);
    expect(res.fulfilledCount).toBe(3);
    expect(res.rejectedCount).toBe(0);
    expect(res.stepResults.every((r) => r.status === 'fulfilled')).toBe(true);
    expect(res.stepResults.map((r) => r.soId)).toEqual(['SO-09-01', 'SO-09-02', 'SO-09-05']);
  });

  it('CLEAN PARTIAL-FAILURE: one step rejects → siblings still fulfilled → failure surfaced (allSettled)', async () => {
    // The headline audit gate. The middle step throws a (deterministic) bd09-style
    // error; the siblings must STILL complete and the failure must be SURFACED in
    // stepResults — never swallowed, never a whole-operation abort. With
    // `Promise.all` the first rejection would fail-fast and the siblings would be
    // abandoned; this asserts that does NOT happen.
    const ctx = fakeCtx({
      'SO-09-01': () => ok('SO-09-01'),
      'SO-09-99': () => {
        throw new Error("SO-09-99 (compute_bad): invalid arguments — 1 error(s): missing 'fund'");
      },
      'SO-09-05': () => ok('SO-09-05'),
    });
    const res = await dispatchPlan(ctx, plan('SO-09-01', 'SO-09-99', 'SO-09-05'));

    expect(res.stepResults).toHaveLength(3);
    expect(res.fulfilledCount).toBe(2);
    expect(res.rejectedCount).toBe(1);

    // The siblings completed — NOT aborted by the failing step.
    expect(res.stepResults[0]).toMatchObject({ soId: 'SO-09-01', status: 'fulfilled' });
    expect(res.stepResults[2]).toMatchObject({ soId: 'SO-09-05', status: 'fulfilled' });

    // The failure is surfaced cleanly, carrying the bd09 error text.
    const rejected = res.stepResults[1];
    expect(rejected.status).toBe('rejected');
    if (rejected.status === 'rejected') {
      expect(rejected.soId).toBe('SO-09-99');
      expect(rejected.error).toContain('invalid arguments');
    }
  });

  it('preserves stable plan order even when later steps settle first (index-keyed)', async () => {
    // The first step resolves slowly, the second fast — the collected order must
    // still be plan order (index-keyed), not completion order.
    const ctx = fakeCtx({
      'SO-09-01': async () => {
        await new Promise((r) => setTimeout(r, 20));
        return ok('SO-09-01');
      },
      'SO-09-02': () => ok('SO-09-02'),
    });
    const res = await dispatchPlan(ctx, plan('SO-09-01', 'SO-09-02'));
    expect(res.stepResults.map((r) => r.soId)).toEqual(['SO-09-01', 'SO-09-02']);
    expect(res.stepResults.map((r) => r.index)).toEqual([0, 1]);
  });

  it('surfaces EVERY failure when multiple steps reject (no silent drop)', async () => {
    const ctx = fakeCtx({
      'SO-09-01': () => ok('SO-09-01'),
      'SO-09-98': () => {
        throw new Error('SO-09-98: terminal A');
      },
      'SO-09-99': () => {
        throw new Error('SO-09-99: terminal B');
      },
    });
    const res = await dispatchPlan(ctx, plan('SO-09-01', 'SO-09-98', 'SO-09-99'));
    expect(res.fulfilledCount).toBe(1);
    expect(res.rejectedCount).toBe(2);
    const errors = res.stepResults.filter((r) => r.status === 'rejected').map((r) => (r as { error: string }).error);
    expect(errors).toEqual(['SO-09-98: terminal A', 'SO-09-99: terminal B']);
  });
});

function resolvedStep(soId: string, index: number): ResolvedStep {
  return {
    index,
    soId,
    status: 'resolved',
    args: { k: soId },
    resolution: {
      soId,
      fundId: 'PF-0003',
      fundName: 'Polaris',
      beginDate: '2025-03-31',
      endDate: '2026-03-31',
      periodDays: 365,
      beginNav: '1',
      endNav: '2',
      args: { k: soId },
      computedBy: 'python:argResolver',
    },
  };
}

describe('dispatchResolvedPlan — dispatching the RESOLVED steps (OIM-134)', () => {
  it('dispatches resolved steps over bd09 and collects one fulfilled result per step', async () => {
    const ctx = fakeCtx({
      'SO-09-01': () => ok('SO-09-01'),
      'SO-09-05': () => ok('SO-09-05'),
    });
    const res = await dispatchResolvedPlan(ctx, [resolvedStep('SO-09-01', 0), resolvedStep('SO-09-05', 1)]);
    expect(res.fulfilledCount).toBe(2);
    expect(res.rejectedCount).toBe(0);
    expect(res.stepResults.map((r) => r.soId)).toEqual(['SO-09-01', 'SO-09-05']);
  });

  it('SURFACES an unresolved step as a clean failure WITHOUT dispatching it (never fabricated inputs)', async () => {
    // The unresolved step must NOT reach bd09 (no fabricated args); it surfaces directly as a clean
    // rejected step carrying the resolution error. The resolved sibling still dispatches.
    let bd09Calls = 0;
    const ctx = fakeCtx({
      'SO-09-01': () => {
        bd09Calls += 1;
        return ok('SO-09-01');
      },
    });
    const steps: ResolvedStep[] = [
      resolvedStep('SO-09-01', 0),
      { index: 1, soId: 'SO-09-02', status: 'unresolved', error: 'argResolver cannot resolve SO-09-02 (v0.1 bound)' },
    ];
    const res = await dispatchResolvedPlan(ctx, steps);
    expect(bd09Calls).toBe(1); // ONLY the resolved step hit bd09 — the unresolved step never did
    expect(res.fulfilledCount).toBe(1);
    expect(res.rejectedCount).toBe(1);
    expect(res.stepResults[0]).toMatchObject({ soId: 'SO-09-01', status: 'fulfilled' });
    const failed = res.stepResults[1];
    expect(failed.status).toBe('rejected');
    if (failed.status === 'rejected') {
      expect(failed.error).toContain('cannot resolve');
    }
  });
});
