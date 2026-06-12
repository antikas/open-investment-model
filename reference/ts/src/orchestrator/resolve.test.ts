/**
 * Unit proof of the RESOLVE step's collection logic (OIM-134) — the abstract-arg → concrete-input
 * resolution against `argResolver`, isolated from the substrate with a fake service client.
 *
 * The live, production-VO proof of the full resolve→dispatch→aggregate→close chain (a real Sonnet
 * plan, the real marts, real numbers) is `scripts/full-chain-demo.mjs`. THIS test pins the
 * in-handler resolution behaviour deterministically: a resolved step carries the marts-derived
 * concrete args; an unresolvable step (the v0.1 bound, or a missing fund) is captured as a CLEAN
 * FAILURE (`status: 'unresolved'`) — NEVER fabricated inputs — and the siblings still resolve.
 */
import { describe, expect, it } from 'vitest';
import type { ObjectContext } from '@restatedev/restate-sdk';
import { resolvePlan, type ResolutionWindow } from './resolve.js';
import type { ResolveStepArgsResult } from './arg-resolver-contract.js';
import type { Plan } from './llm-service-contract.js';

/**
 * A fake ObjectContext whose `serviceClient(ARG_RESOLVER_SERVICE)` returns a client whose
 * `resolveStepArgs` is driven by a per-soId script: a function returning the resolved result, or
 * throwing to simulate an argResolver TerminalError (an unresolvable tool / missing fund).
 */
function fakeCtx(
  script: Record<string, (req: { fundId: string }) => ResolveStepArgsResult | Promise<ResolveStepArgsResult>>,
): ObjectContext {
  const client = {
    resolveStepArgs: async (req: { soId: string; fundId: string }): Promise<ResolveStepArgsResult> => {
      const fn = script[req.soId];
      if (!fn) throw new Error(`argResolver cannot resolve args for '${req.soId}': v0.1 bounded to SO-09-01/05`);
      return fn(req);
    },
  };
  return {
    serviceClient: () => client,
    console: { log: () => {}, warn: () => {}, error: () => {} },
  } as unknown as ObjectContext;
}

function resolved(soId: string, args: Record<string, unknown>): ResolveStepArgsResult {
  return {
    soId,
    fundId: 'PF-0003',
    fundName: 'Polaris Multi-Asset',
    beginDate: '2025-03-31',
    endDate: '2026-03-31',
    periodDays: 365,
    beginNav: '1000000.00',
    endNav: '1100000.00',
    args,
    computedBy: 'python:argResolver',
  };
}

function plan(...soIds: string[]): Plan {
  return {
    steps: soIds.map((soId) => ({ soId, args: { fund: 'PF-0003' }, rationale: null })),
    riskScore: 0.05,
    summary: 'attribution plan',
  };
}

const WINDOW: ResolutionWindow = { fundId: 'PF-0003', beginDate: null, endDate: null };

describe('resolvePlan — the resolve-step collection contract', () => {
  it('resolves every step to its marts-derived concrete args (the happy path)', async () => {
    const ctx = fakeCtx({
      'SO-09-01': () => resolved('SO-09-01', { beginning_value: '1000000.00', ending_value: '1100000.00', period_days: 365, cash_flows: [] }),
      'SO-09-05': () => resolved('SO-09-05', { segments: [{ segment: 'Equity', weight: '1', segment_return: '0.1' }] }),
    });
    const res = await resolvePlan(ctx, plan('SO-09-01', 'SO-09-05'), WINDOW);
    expect(res.resolvedSteps).toHaveLength(2);
    expect(res.resolvedCount).toBe(2);
    expect(res.unresolvedCount).toBe(0);
    expect(res.resolvedSteps.every((r) => r.status === 'resolved')).toBe(true);
    const step0 = res.resolvedSteps[0];
    if (step0.status === 'resolved') {
      // The resolved args are the marts-derived concrete inputs (NOT the plan's abstract args).
      expect(step0.args).toMatchObject({ beginning_value: '1000000.00', ending_value: '1100000.00' });
      expect(step0.resolution.computedBy).toBe('python:argResolver');
    }
  });

  it('CLEAN FAILURE: an unresolvable tool (the v0.1 bound) is surfaced, NEVER fabricated', async () => {
    // SO-09-02 is not in the v0.1 resolvable set → the resolver rejects it. The step must surface as
    // `unresolved` (a clean failure carrying the resolver error), the siblings still resolve, and NO
    // fabricated args appear — the honest v0.1 boundary, not a guessed input.
    const ctx = fakeCtx({
      'SO-09-01': () => resolved('SO-09-01', { beginning_value: '1000000.00', ending_value: '1100000.00', period_days: 365, cash_flows: [] }),
      // SO-09-02 absent from the script → the fake throws the "cannot resolve" terminal error.
    });
    const res = await resolvePlan(ctx, plan('SO-09-01', 'SO-09-02'), WINDOW);
    expect(res.resolvedCount).toBe(1);
    expect(res.unresolvedCount).toBe(1);
    expect(res.resolvedSteps[0]).toMatchObject({ soId: 'SO-09-01', status: 'resolved' });
    const failed = res.resolvedSteps[1];
    expect(failed.status).toBe('unresolved');
    if (failed.status === 'unresolved') {
      expect(failed.soId).toBe('SO-09-02');
      expect(failed.error).toContain('cannot resolve');
      // The unresolved step carries NO args field (it is not the resolved variant) — nothing to
      // fabricate-dispatch on.
      expect('args' in failed).toBe(false);
    }
  });

  it('a missing fund surfaces as a clean failure on every step (no fabricated marts read)', async () => {
    // The resolver rejects when the fund cannot be read; the resolve step surfaces it cleanly.
    const ctx = fakeCtx({
      'SO-09-01': () => {
        throw new Error('the canonical store does not exist — build it first (pnpm dbt:build)');
      },
    });
    const res = await resolvePlan(ctx, plan('SO-09-01'), { fundId: 'PF-9999', beginDate: null, endDate: null });
    expect(res.resolvedCount).toBe(0);
    expect(res.unresolvedCount).toBe(1);
    expect(res.resolvedSteps[0].status).toBe('unresolved');
  });

  it('preserves stable plan order even when later steps resolve first (index-keyed)', async () => {
    const ctx = fakeCtx({
      'SO-09-01': async () => {
        await new Promise((r) => setTimeout(r, 20));
        return resolved('SO-09-01', { beginning_value: '1', ending_value: '2', period_days: 1, cash_flows: [] });
      },
      'SO-09-05': () => resolved('SO-09-05', { segments: [{ segment: 'Equity', weight: '1', segment_return: '0.1' }] }),
    });
    const res = await resolvePlan(ctx, plan('SO-09-01', 'SO-09-05'), WINDOW);
    expect(res.resolvedSteps.map((r) => r.soId)).toEqual(['SO-09-01', 'SO-09-05']);
    expect(res.resolvedSteps.map((r) => r.index)).toEqual([0, 1]);
  });
});
