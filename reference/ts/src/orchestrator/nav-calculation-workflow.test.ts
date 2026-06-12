/**
 * Unit proof of the `NavCalculationWorkflow` (the NAV strike) — the multi-step journaled
 * control flow, the §A1 RECONCILIATION (the struck NAV equals `mart_fund_nav.nav_usd` to the
 * penny), the gate-at-publish (approve → publishes / reject → terminal abort, NO publish),
 * and the publish-record shape, isolated from the substrate with a fake `WorkflowContext`.
 *
 * The LIVE, real-substrate proof (the durable steps, a real crash mid-strike resuming from
 * the journal, publish exactly-once, the gate resolved via the ingress, the reconciliation
 * over the actual `mart_fund_nav`) is `scripts/nav-workflow-proof.mjs`. THIS test pins the
 * workflow's in-handler control flow deterministically: a fake marts-read serviceClient
 * returning fixed components, a fake awakeable driven by the test, a fake `ctx.run` that runs
 * its closure and records the journaled value, and assertions on the checkpoints + the
 * publish record + the thrown `NavAbortedError`.
 */
import { describe, expect, it, vi } from 'vitest';
import { TerminalError, TimeoutError, type WorkflowContext } from '@restatedev/restate-sdk';
import {
  navCalculation,
  NavAbortedError,
  type NavStepCheckpoint,
  type NavPublishRecord,
} from './nav-calculation-workflow.js';
import type { FundNavComponents, FundHoldingsGross } from './nav-data-contract.js';

// The workflow's `run` handler — the SDK wraps it under `.workflow`, so reach the underlying
// fn for the test and invoke it with our fake context (the SDK exposes the bound handlers as
// `{run, status}` on the definition's `.workflow`).
type RunFn = (ctx: WorkflowContext, input: { fundId: string; navKnowledgeDate?: string | null }) => Promise<unknown>;
const runHandler = (navCalculation as unknown as { workflow: { run: RunFn } }).workflow.run;

type OrTimeoutPromise<T> = Promise<T> & { orTimeout(ms: number): OrTimeoutPromise<T> };
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
  components: FundNavComponents;
  /** The independent holdings-mart roll-up the load-positions step reads (cross-mart reconcile). */
  holdings: FundHoldingsGross;
  /** How the gate's awakeable settles: approve, reject, or never (→ timeout). */
  gate: { mode: 'approve' } | { mode: 'reject'; reason: string } | { mode: 'never' };
}

interface FakeCtxCapture {
  ctx: WorkflowContext;
  runNames: string[];
  runRecords: Array<{ name: string; value: unknown }>;
  state: () => Record<string, unknown> | undefined;
}

/**
 * A fake WorkflowContext implementing only the surface the workflow uses: `key`, `set`/`get`
 * (state), `serviceClient` (the marts read), `awakeable` (the gate), `run` (executes + records
 * the journaled value), `console`, `date`, `sleep`.
 */
function fakeCtx(opts: FakeCtxOptions): FakeCtxCapture {
  const runNames: string[] = [];
  const runRecords: Array<{ name: string; value: unknown }> = [];
  let stateValue: Record<string, unknown> | undefined;
  const awakeableId = 'prom_NAV_fake_awakeable';

  let gatePromise: Promise<{ approved: boolean; reason?: string }>;
  if (opts.gate.mode === 'approve') gatePromise = Promise.resolve({ approved: true });
  else if (opts.gate.mode === 'reject') gatePromise = Promise.resolve({ approved: false, reason: opts.gate.reason });
  else gatePromise = new Promise(() => {}); // never settles → orTimeout fires

  const ctx = {
    key: 'navwf-test-1',
    set: <T>(_k: string, v: T) => {
      stateValue = v as unknown as Record<string, unknown>;
    },
    get: async <T>(_k: string) => stateValue as unknown as T,
    serviceClient: () => ({
      getFundNavComponents: async () => opts.components,
      getFundHoldingsGross: async () => opts.holdings,
    }),
    awakeable: <T>() => ({ id: awakeableId, promise: withOrTimeout(gatePromise) as unknown as Promise<T> }),
    run: async (name: string, action: () => unknown) => {
      const value = await action();
      runNames.push(name);
      runRecords.push({ name, value });
      return value;
    },
    sleep: async () => {},
    // The additive OIM-142 pending-approvals registry sends (made by the reused gate)
    // are FIRE-AND-FORGET — no-op stubs keep the workflow's control flow unchanged. The
    // cycle-2 terminal-path `resolve` mark is the same additive pattern (it leaves the
    // pending queue on every resolution path; it does not gate the workflow).
    objectSendClient: () => ({ register: () => {}, resolve: () => {} }),
    date: { now: async () => 1_700_000_000_000 },
    console: { log: () => {}, warn: () => {}, error: () => {} },
  } as unknown as WorkflowContext;

  return { ctx, runNames, runRecords, state: () => stateValue };
}

/** Fixed marts components — PF-0003-shaped: non-zero accruals, zero fees, reconciling. */
function components(over: Partial<FundNavComponents> = {}): FundNavComponents {
  return {
    fundId: 'PF-0003',
    fundName: 'Polaris Multi-Asset Fund',
    shareClass: null,
    nPositions: 21,
    grossMarketValue: '104834424.11',
    accruedIncome: '101172.00',
    fees: '0.00',
    navUsd: '104935596.11', // = gross + accruals − fees
    computedBy: 'python:navData',
    ...over,
  };
}

/**
 * Fixed HOLDINGS-mart roll-up — PF-0003-shaped. Its `holdingsGrossMarketValue` ties to the
 * NAV mart's `grossMarketValue` (the genuine cross-mart reconcile passes). Override it to
 * simulate a real cross-mart divergence (the two marts disagreeing on the fund's gross).
 */
function holdings(over: Partial<FundHoldingsGross> = {}): FundHoldingsGross {
  return {
    fundId: 'PF-0003',
    fundName: 'Polaris Multi-Asset Fund',
    nPositions: 21,
    holdingsGrossMarketValue: '104834424.11', // == mart_fund_nav.gross_market_value
    computedBy: 'python:navData',
    ...over,
  };
}

describe('navCalculation — the NAV-strike workflow', () => {
  it('APPROVE → strikes all four steps, reconciles to mart_fund_nav.nav_usd, publishes', async () => {
    const { ctx, runNames, runRecords, state } = fakeCtx({
      components: components(),
      holdings: holdings(),
      gate: { mode: 'approve' },
    });
    const result = (await runHandler(ctx, { fundId: 'PF-0003' })) as {
      status: string;
      navUsd: string;
      martNavUsd: string;
      publishRecord: NavPublishRecord;
    };

    // The four journaled steps ran in §6.1 order, then publish (the gate's notify is between).
    expect(runNames).toEqual([
      'load-positions',
      'price-positions',
      'apply-fees',
      'roll-up',
      'approval-notify', // the gate fired (publish is high-stakes by declaration)
      'publish',
    ]);

    // The struck NAV equals the components' identity AND the mart's published nav_usd.
    expect(result.status).toBe('published');
    expect(result.navUsd).toBe('104935596.11');
    expect(result.martNavUsd).toBe('104935596.11');

    // The publish record carries the reconciliation + the approval link.
    expect(result.publishRecord).toMatchObject({
      kind: 'nav-published',
      fundId: 'PF-0003',
      navUsd: '104935596.11',
      martNavUsd: '104935596.11',
      approvedAwakeableId: 'prom_NAV_fake_awakeable',
      shareClass: null,
    });

    // Exactly ONE publish record was journaled (publish exactly-once at the unit level).
    expect(runRecords.filter((r) => r.name === 'publish')).toHaveLength(1);

    // The terminal state is published with the record.
    expect(state()).toMatchObject({ status: 'published', publishRecord: { kind: 'nav-published' } });
  });

  it('CROSS-MART gross divergence (holdings mart != NAV mart) → terminal abort, NO publish', async () => {
    // The GENUINE, FALSIFIABLE cross-mart check: the load-positions holdings roll-up
    // (mart_portfolio_holdings) must tie to mart_fund_nav.gross_market_value. Here the holdings
    // mart reports a gross $1.00 higher than the NAV mart's gross — the two marts DISAGREE on
    // the fund's holdings (a real divergence: a dropped/double-counted position). The roll-up
    // must surface it and abort, NOT publish. This is the check that could not fail on the old
    // within-row X==X reconciliation — it CAN fail now (two marts, two SQL paths).
    const { ctx, runNames } = fakeCtx({
      components: components(), // NAV mart gross 104834424.11
      holdings: holdings({ holdingsGrossMarketValue: '104834425.11' }), // holdings mart $1 higher → must FAIL
      gate: { mode: 'approve' },
    });
    await expect(runHandler(ctx, { fundId: 'PF-0003' })).rejects.toMatchObject({ name: 'TerminalError' });
    // The roll-up step threw on the cross-mart divergence — no gate, no publish ran.
    expect(runNames).not.toContain('publish');
    expect(runNames).not.toContain('approval-notify');
  });

  it('§A1 IDENTITY breaks (gross + accruals − fees != nav_usd) → terminal abort, NO publish', async () => {
    // The §A1 read-consistency check: the mart's published nav_usd must equal gross + accruals
    // − fees on the row read. Here the NAV mart's nav_usd is 1 cent off its own components → a
    // corrupted/inconsistent read; the workflow must NOT publish a row that fails its own
    // identity. (The genuine independent §A1 NAV re-derivation is dbt-enforced upstream by
    // assert_mart_fund_nav_invariant; this guards the read before the irreversible publish.)
    const { ctx, runNames } = fakeCtx({
      components: components({ navUsd: '104935597.11' }), // 1 cent off its own gross+accruals → must FAIL
      holdings: holdings(), // cross-mart gross still ties (so the §A1 identity check is the one that fires)
      gate: { mode: 'approve' },
    });
    await expect(runHandler(ctx, { fundId: 'PF-0003' })).rejects.toMatchObject({ name: 'TerminalError' });
    expect(runNames).not.toContain('publish');
    expect(runNames).not.toContain('approval-notify');
  });

  it('REJECT at the gate → terminal NavAbortedError, NO publish (gate precedes publish)', async () => {
    const { ctx, runNames, state } = fakeCtx({
      components: components(),
      holdings: holdings(),
      gate: { mode: 'reject', reason: 'operator rejects the high-stakes NAV publish' },
    });
    await expect(runHandler(ctx, { fundId: 'PF-0003' })).rejects.toMatchObject({
      name: 'NavAbortedError',
      abortKind: 'aborted-by-operator',
    });
    // NO publish ran (the reject path never reaches publish — no half-published NAV).
    expect(runNames).not.toContain('publish');
    // The state is aborted with NO publish record.
    expect(state()).toMatchObject({ status: 'aborted', publishRecord: null, abort: { kind: 'aborted-by-operator' } });
  });

  it('TIMEOUT at the gate → terminal NavAbortedError (aborted-by-timeout), NO publish', async () => {
    // `APPROVAL_TIMEOUT_MS` is read at module load in approval-gate.ts, so set the env + load
    // the workflow module fresh (after resetting modules) to pick up a tiny timeout — the
    // approval-gate.test.ts pattern. The never-settling gate then aborts by timeout.
    const prev = process.env.AGENTINVEST_APPROVAL_TIMEOUT_MS;
    process.env.AGENTINVEST_APPROVAL_TIMEOUT_MS = '20';
    vi.resetModules();
    const mod = (await import('./nav-calculation-workflow.js')) as unknown as {
      navCalculation: { workflow: { run: RunFn } };
    };
    const freshRun = mod.navCalculation.workflow.run;
    try {
      const { ctx, runNames } = fakeCtx({ components: components(), holdings: holdings(), gate: { mode: 'never' } });
      await expect(freshRun(ctx, { fundId: 'PF-0003' })).rejects.toMatchObject({
        abortKind: 'aborted-by-timeout',
      });
      expect(runNames).not.toContain('publish');
    } finally {
      if (prev === undefined) delete process.env.AGENTINVEST_APPROVAL_TIMEOUT_MS;
      else process.env.AGENTINVEST_APPROVAL_TIMEOUT_MS = prev;
      vi.resetModules();
    }
  });

  it('NavAbortedError is a Restate TerminalError (no retry-storm)', async () => {
    const { ctx } = fakeCtx({ components: components(), holdings: holdings(), gate: { mode: 'reject', reason: 'x' } });
    const err = await runHandler(ctx, { fundId: 'PF-0003' }).catch((e) => e);
    expect(err).toBeInstanceOf(NavAbortedError);
    expect(err).toBeInstanceOf(TerminalError);
  });

  it('the four step checkpoints capture the §A1 components (load/price/fees/roll-up)', async () => {
    const { ctx, runRecords } = fakeCtx({ components: components(), holdings: holdings(), gate: { mode: 'approve' } });
    await runHandler(ctx, { fundId: 'PF-0003' });
    const steps = runRecords
      .filter((r) => ['load-positions', 'price-positions', 'apply-fees', 'roll-up'].includes(r.name))
      .map((r) => r.value as NavStepCheckpoint | { navUsd: string; holdingsGross: string; navMartGross: string });
    // load/price/fees journal a NavStepCheckpoint; roll-up journals the recon
    // {navUsd, martNavUsd, holdingsGross, navMartGross}.
    expect((steps[0] as NavStepCheckpoint).step).toBe('load-positions');
    expect((steps[1] as NavStepCheckpoint).step).toBe('price-positions');
    expect((steps[2] as NavStepCheckpoint).step).toBe('apply-fees');
    expect((steps[3] as { navUsd: string }).navUsd).toBe('104935596.11');
    // The roll-up records the genuine cross-mart figures: holdings gross == NAV mart gross.
    expect((steps[3] as { holdingsGross: string }).holdingsGross).toBe('104834424.11');
    expect((steps[3] as { navMartGross: string }).navMartGross).toBe('104834424.11');
  });
});
