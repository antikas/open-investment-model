/**
 * Unit proof of the ADDITIVE pending-approvals registry — the read index
 * the gate ALSO records each notice in, so a surface can enumerate the approvals
 * awaiting a decision. Isolated from the substrate with a fake ObjectContext that
 * holds the keyed state; asserts register → pending, resolve → resolved, and that
 * the registry NEVER decides anything (the awakeable is the decision path).
 *
 * The LIVE proof (the gate's fire-and-forget send populating a real registry, read
 * by the Operator UI, the awakeable resolved on the ingress) is the UI proof.
 */
import { describe, expect, it } from 'vitest';
import { type Context, type ObjectContext } from '@restatedev/restate-sdk';
import {
  approvalRegistry,
  approvalRegistryReader,
  APPROVAL_INDEX_KEY,
  type ApprovalListItem,
  type PendingApproval,
  type RegisterApprovalInput,
} from './approval-registry.js';

type RegisterFn = (ctx: ObjectContext, input: RegisterApprovalInput) => Promise<void>;
type ResolveFn = (ctx: ObjectContext, input: { decision: 'approved' | 'rejected' | 'aborted'; at?: string }) => Promise<void>;
type GetFn = (ctx: ObjectContext) => Promise<PendingApproval | null>;

const handlers = (approvalRegistry as unknown as {
  object: { register: RegisterFn; resolve: ResolveFn; get: GetFn };
}).object;

type ListFn = (ctx: Context) => Promise<{ pending: ApprovalListItem[]; resolved: ApprovalListItem[] }>;
const readerHandlers = (approvalRegistryReader as unknown as { service: { list: ListFn } }).service;

/**
 * A fake keyed ObjectContext over an in-memory store; the send-client is a no-op (index
 * maintenance is out of scope here). `logs` captures every `console.log` line so a test can
 * assert the reconciliation line the first-/terminal-writer-wins rule emits.
 */
function fakeCtx(): ObjectContext & { logs: string[] } {
  const store = new Map<string, unknown>();
  const logs: string[] = [];
  return {
    logs,
    set: <T>(k: string, v: T) => store.set(k, v),
    get: async <T>(k: string) => (store.get(k) as T) ?? null,
    objectSendClient: () => ({ addToIndex: () => {} }),
    date: { now: async () => 1_700_000_000_000 },
    console: { log: (m: string) => logs.push(m), warn: () => {}, error: () => {} },
  } as unknown as ObjectContext & { logs: string[] };
}

const notice: RegisterApprovalInput = {
  operationId: 'op-test-1',
  awakeableId: 'prom_1ABC_fake',
  riskScore: 0.9,
  threshold: 0.7,
  summary: 'Publish NAV — irreversible, regulated.',
  stepCount: 4,
  selectedSoIds: ['nav-publish'],
  origin: 'navCalculation',
  raisedAt: '2026-06-02T00:00:00.000Z',
};

describe('approvalRegistry — the additive pending-approvals index', () => {
  it('register records the notice as PENDING with no decision', async () => {
    const ctx = fakeCtx();
    await handlers.register(ctx, notice);
    const entry = await handlers.get(ctx);
    expect(entry).not.toBeNull();
    expect(entry?.status).toBe('pending');
    expect(entry?.decision).toBeNull();
    expect(entry?.operationId).toBe('op-test-1');
    expect(entry?.awakeableId).toBe('prom_1ABC_fake');
    expect(entry?.riskScore).toBe(0.9);
  });

  it('resolve marks the entry RESOLVED with the recorded decision (the awakeable is still the decision path)', async () => {
    const ctx = fakeCtx();
    await handlers.register(ctx, notice);
    await handlers.resolve(ctx, { decision: 'rejected', at: '2026-06-02T01:00:00.000Z' });
    const entry = await handlers.get(ctx);
    expect(entry?.status).toBe('resolved');
    expect(entry?.decision).toBe('rejected');
    expect(entry?.resolvedAt).toBe('2026-06-02T01:00:00.000Z');
  });

  it('resolve on an absent entry is a no-op (never fabricates a decision)', async () => {
    const ctx = fakeCtx();
    await handlers.resolve(ctx, { decision: 'approved' });
    const entry = await handlers.get(ctx);
    expect(entry).toBeNull();
  });
});

/**
 * TERMINAL-TRUTH-WINS. Two writers race on the
 * same entry for a gated operation — the gate's terminal-path mark and the UI's post-resolve
 * mark — serialised by the single-writer-per-key VO. The recorded label must be the operation's
 * TERMINAL TRUTH regardless of ARRIVAL ORDER (a plain first-writer-wins rule is order-based and
 * leaves the reverse interleaving open). The gate's `'aborted'` (durable-timeout path, the sole
 * producer of an `aborted` mark) DOMINATES: it overrides a recorded non-`aborted` whenever it
 * arrives (BOTH orderings → `aborted`); a non-`aborted` late write never overrides a recorded
 * `aborted`; a same decision is an idempotent no-op; a first write on a pending entry applies.
 */
describe('approvalRegistry.resolve — terminal-truth-wins (decided-trail label honesty, BOTH orderings)', () => {
  it('FORWARD (gate-marks-first): aborted recorded, late UI approved IGNORED — label stays aborted + reconciliation line logged', async () => {
    const ctx = fakeCtx();
    await handlers.register(ctx, notice);
    // First (terminal) writer: the gate's timeout marks it aborted.
    await handlers.resolve(ctx, { decision: 'aborted', at: '2026-06-02T01:00:00.000Z' });
    // Late, stale writer: the UI's post-timeout approve. Must NOT overwrite the terminal aborted.
    await handlers.resolve(ctx, { decision: 'approved', at: '2026-06-02T01:00:01.000Z' });
    const entry = await handlers.get(ctx);
    expect(entry?.status).toBe('resolved');
    expect(entry?.decision).toBe('aborted'); // the gate's terminal truth wins
    expect(entry?.resolvedAt).toBe('2026-06-02T01:00:00.000Z'); // unchanged by the late write
    expect(
      ctx.logs.some(
        (l) => l.includes('recorded=aborted') && l.includes('ignored-late=approved') && l.includes('op-test-1'),
      ),
    ).toBe(true);
  });

  it('REVERSE (UI-marks-first): approved recorded on a pending row, the gate aborted arrives LATE and OVERRIDES — label becomes aborted + override line logged', async () => {
    const ctx = fakeCtx();
    await handlers.register(ctx, notice);
    // UI's mark wins the race onto the still-pending entry FIRST: resolved=approved.
    await handlers.resolve(ctx, { decision: 'approved', at: '2026-06-02T01:00:00.000Z' });
    let entry = await handlers.get(ctx);
    expect(entry?.decision).toBe('approved'); // the UI mark landed first
    // The gate's durable-timeout `aborted` (the operation's terminal truth) arrives LATE and must OVERRIDE.
    await handlers.resolve(ctx, { decision: 'aborted', at: '2026-06-02T01:00:01.000Z' });
    entry = await handlers.get(ctx);
    expect(entry?.status).toBe('resolved');
    expect(entry?.decision).toBe('aborted'); // terminal truth overrides the stale approved
    expect(entry?.resolvedAt).toBe('2026-06-02T01:00:01.000Z'); // the override carries the gate-mark timestamp
    expect(
      ctx.logs.some(
        (l) => l.includes('overrode-with-terminal') && l.includes('recorded-was=approved') && l.includes('now=aborted') && l.includes('op-test-1'),
      ),
    ).toBe(true);
  });

  it('a non-aborted late write never overrides a recorded aborted (a late UI rejected after the gate aborted stays ignored)', async () => {
    const ctx = fakeCtx();
    await handlers.register(ctx, notice);
    await handlers.resolve(ctx, { decision: 'aborted', at: '2026-06-02T01:00:00.000Z' });
    await handlers.resolve(ctx, { decision: 'rejected', at: '2026-06-02T01:00:02.000Z' });
    const entry = await handlers.get(ctx);
    expect(entry?.decision).toBe('aborted'); // the terminal aborted is never demoted
    expect(
      ctx.logs.some(
        (l) => l.includes('recorded=aborted') && l.includes('ignored-late=rejected') && l.includes('op-test-1'),
      ),
    ).toBe(true);
  });

  it('a SAME-decision late write on an already-resolved entry is an idempotent no-op (no reconciliation log)', async () => {
    const ctx = fakeCtx();
    await handlers.register(ctx, notice);
    await handlers.resolve(ctx, { decision: 'approved', at: '2026-06-02T01:00:00.000Z' });
    const logsBefore = ctx.logs.length;
    await handlers.resolve(ctx, { decision: 'approved', at: '2026-06-02T02:00:00.000Z' });
    const entry = await handlers.get(ctx);
    expect(entry?.decision).toBe('approved');
    expect(entry?.resolvedAt).toBe('2026-06-02T01:00:00.000Z'); // first write's timestamp preserved
    expect(ctx.logs.some((l) => l.includes('reconciled conflicting'))).toBe(false);
    expect(ctx.logs.length).toBe(logsBefore); // a same-decision no-op logs nothing new
  });

  it('a resolve of a still-PENDING entry applies normally (the first terminal write)', async () => {
    const ctx = fakeCtx();
    await handlers.register(ctx, notice);
    await handlers.resolve(ctx, { decision: 'approved', at: '2026-06-02T01:00:00.000Z' });
    const entry = await handlers.get(ctx);
    expect(entry?.status).toBe('resolved');
    expect(entry?.decision).toBe('approved');
    expect(entry?.resolvedAt).toBe('2026-06-02T01:00:00.000Z');
  });

  it('a genuine APPROVE with NO competing aborted-mark stands (the gate issues an aborted mark ONLY on timeout — a genuine decision never races one)', async () => {
    const ctx = fakeCtx();
    await handlers.register(ctx, notice);
    // Genuine approve: the operator approved while genuinely live and the gate proceeded —
    // no `aborted` mark is ever issued for this op (the gate produces `aborted` only on timeout).
    await handlers.resolve(ctx, { decision: 'approved', at: '2026-06-02T01:00:00.000Z' });
    // A same-decision late mark (a duplicate fire-and-forget) is the only thing that can follow — a no-op.
    await handlers.resolve(ctx, { decision: 'approved', at: '2026-06-02T01:00:02.000Z' });
    const entry = await handlers.get(ctx);
    expect(entry?.decision).toBe('approved'); // genuine decision stands; no aborted is ever produced to override it
    expect(entry?.resolvedAt).toBe('2026-06-02T01:00:00.000Z'); // unchanged by the duplicate
  });
});

/**
 * The READER's liveness reconcile. The reader fans out a
 * read of the shared index + each entry, THEN cross-checks each registry-pending entry
 * against its operation's actual recorded status, and DROPS (ages out) any whose op is
 * terminal or gone. This fakes the reader's `Context` so `objectClient`/`workflowClient`
 * serve the index, the entries, and the per-op status — asserting a genuinely-live entry
 * stays, while a terminal-op and a gone-op entry are aged out of `pending` even though
 * the registry still marks them `pending` (the crash-after-resolve-before-mark edge).
 */
function pending(operationId: string, origin: string): PendingApproval {
  return {
    operationId,
    awakeableId: `prom_${operationId}`,
    riskScore: 0.9,
    threshold: 0.7,
    summary: `gated ${operationId}`,
    stepCount: 4,
    selectedSoIds: ['nav-publish'],
    origin,
    raisedAt: `2026-06-02T0${operationId.length % 9}:00:00.000Z`,
    status: 'pending',
    decision: null,
    resolvedAt: null,
  };
}

/**
 * A fake reader Context. The index returns the seeded operationIds; `get` on a registry
 * key returns its (pending) entry; the per-op `status` client returns the seeded live
 * status (`running`/`striking` = live; `aborted`/`published`/`completed` = terminal;
 * null = gone). Mirrors the SDK's `objectClient`/`workflowClient` enough for the reconcile.
 */
function fakeReaderCtx(
  entries: Record<string, PendingApproval>,
  opStatus: Record<string, { status: string } | null>,
): Context {
  const index = Object.keys(entries);
  return {
    objectClient: (def: { name: string }, key: string) => {
      if (def.name === 'approvalRegistry') {
        if (key === APPROVAL_INDEX_KEY) return { readIndex: async () => index };
        return { get: async () => entries[key] ?? null };
      }
      // investmentOperation status client
      return { status: async () => opStatus[key] ?? null };
    },
    workflowClient: (_def: { name: string }, key: string) => ({
      status: async () => opStatus[key] ?? null,
    }),
  } as unknown as Context;
}

describe('approvalRegistryReader.list — the liveness reconcile', () => {
  it('keeps a genuinely-live (running/striking) pending entry', async () => {
    const ctx = fakeReaderCtx(
      { 'op-live': pending('op-live', 'investmentOperation'), 'wf-live': pending('wf-live', 'navCalculation') },
      { 'op-live': { status: 'running' }, 'wf-live': { status: 'striking' } },
    );
    const { pending: p } = await readerHandlers.list(ctx);
    expect(p.map((e) => e.operationId).sort()).toEqual(['op-live', 'wf-live']);
  });

  it('ages out a pending entry whose operation is TERMINAL (resolved out-of-band)', async () => {
    const ctx = fakeReaderCtx(
      { 'op-aborted': pending('op-aborted', 'investmentOperation'), 'wf-published': pending('wf-published', 'navCalculation') },
      { 'op-aborted': { status: 'aborted' }, 'wf-published': { status: 'published' } },
    );
    const { pending: p } = await readerHandlers.list(ctx);
    expect(p).toHaveLength(0); // both terminal → dropped from pending
  });

  it('ages out a pending entry whose operation is GONE (null status)', async () => {
    const ctx = fakeReaderCtx(
      { 'op-gone': pending('op-gone', 'investmentOperation') },
      { 'op-gone': null },
    );
    const { pending: p } = await readerHandlers.list(ctx);
    expect(p).toHaveLength(0);
  });

  it('keeps live, drops terminal — a mixed queue is reconciled to only the live rows', async () => {
    const ctx = fakeReaderCtx(
      {
        'op-live': pending('op-live', 'investmentOperation'),
        'op-dead': pending('op-dead', 'investmentOperation'),
        'wf-live': pending('wf-live', 'navCalculation'),
      },
      { 'op-live': { status: 'running' }, 'op-dead': { status: 'aborted' }, 'wf-live': { status: 'striking' } },
    );
    const { pending: p } = await readerHandlers.list(ctx);
    expect(p.map((e) => e.operationId).sort()).toEqual(['op-live', 'wf-live']);
  });
});
