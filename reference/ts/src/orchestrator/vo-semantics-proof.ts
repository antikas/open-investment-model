/**
 * Virtual-object-semantics proof (live, over the real shared Restate).
 *
 * Proves the two concurrency properties the orchestrator's `InvestmentOperation`
 * relies on, on the real substrate — not in a unit mock:
 *
 *  1. SAME key serialises. Concurrent invocations against the SAME object key are
 *     executed one-at-a-time by Restate's single-writer-per-key guarantee. We
 *     prove it with a read-modify-write under an artificial in-handler delay: if
 *     the invocations interleaved, the read-modify-write would lose updates and
 *     the observed enter/exit windows would overlap. Serialised, the final
 *     counter equals the number of invocations and no two windows overlap.
 *  2. DIFFERENT keys parallelise. Concurrent invocations against DIFFERENT keys
 *     run at the same time — their enter/exit windows DO overlap, and the total
 *     wall-clock is far below the serial sum.
 *
 * This harness defines its OWN instrumented virtual object (`voSemanticsProbe`)
 * so the production `InvestmentOperation` shell stays free of test-only timing
 * logic — the same separation the cross-language smoke uses for its own service.
 * The probe exercises the identical Restate primitive (a keyed `object`), so the
 * guarantee it proves is exactly the one the orchestrator inherits.
 *
 * Run (from reference/ts/, substrate up via `pnpm dev:restate`):
 *   npx tsx src/orchestrator/vo-semantics-proof.ts
 */
import { createServer } from 'node:http2';
import { endpoint as restateEndpoint, object, type ObjectContext } from '@restatedev/restate-sdk';
import {
  INGRESS_URL,
  awaitAdminReady,
  deregisterDeployment,
  isWindowsWsl2Host,
  registerDeployment,
  resolveDeployUrl,
} from '../substrate/restate-reach.js';

const PROBE_NAME = 'voSemanticsProbe';
const PROBE_PORT = Number(process.env.AGENTINVEST_VO_PROBE_PORT ?? 9093);
const HOLD_MS = Number(process.env.AGENTINVEST_VO_PROBE_HOLD_MS ?? 600);

interface BumpResult {
  key: string;
  /** The counter value AFTER this invocation's read-modify-write. */
  counter: number;
  /** Wall-clock ms (epoch) the handler body entered. */
  enteredAt: number;
  /** Wall-clock ms (epoch) the handler body is about to return. */
  exitedAt: number;
}

/**
 * The instrumented probe object. `bump` reads the per-key counter, holds for
 * HOLD_MS (the window in which an interleave WOULD be observable), then writes
 * counter+1 back. Restate serialises same-key invocations, so concurrent bumps
 * on one key produce 1,2,3,... with non-overlapping windows; on distinct keys
 * they each see counter 1 and their windows overlap.
 */
const voSemanticsProbe = object({
  name: PROBE_NAME,
  handlers: {
    async bump(ctx: ObjectContext): Promise<BumpResult> {
      const enteredAt = Date.now();
      const current = (await ctx.get<number>('counter')) ?? 0;
      // The hold is a plain timer, not ctx.sleep, so it occupies the handler
      // body for real wall-clock time — the window an interleave would show in.
      await new Promise((res) => setTimeout(res, HOLD_MS));
      const next = current + 1;
      ctx.set<number>('counter', next);
      const exitedAt = Date.now();
      return { key: ctx.key, counter: next, enteredAt, exitedAt };
    },
  },
});

async function startEndpoint(port: number): Promise<() => void> {
  const e = restateEndpoint().bind(voSemanticsProbe);
  const bind = isWindowsWsl2Host() ? '0.0.0.0' : '127.0.0.1';
  const server = createServer(e.http2Handler());
  await new Promise<void>((resolve, reject) => {
    const onError = (err: Error): void => {
      server.off('error', onError);
      reject(err);
    };
    server.once('error', onError);
    server.listen({ port, host: bind }, () => {
      server.off('error', onError);
      resolve();
    });
  });
  out(`[vo-semantics] probe endpoint on ${bind}:${port}`);
  return () => server.close();
}

async function bump(key: string): Promise<BumpResult> {
  const res = await fetch(`${INGRESS_URL}/${PROBE_NAME}/${encodeURIComponent(key)}/bump`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: '{}',
    signal: AbortSignal.timeout(60_000),
  });
  if (!res.ok) throw new Error(`bump ${key} failed ${res.status}: ${await res.text()}`);
  return (await res.json()) as BumpResult;
}

/** True iff two [enter,exit] windows overlap in wall-clock time. */
function overlaps(a: BumpResult, b: BumpResult): boolean {
  return a.enteredAt < b.exitedAt && b.enteredAt < a.exitedAt;
}

async function main(): Promise<number> {
  out('[vo-semantics] virtual-object semantics proof (live, real Restate)');
  await awaitAdminReady();
  const close = await startEndpoint(PROBE_PORT);
  let deploymentId: string | undefined;
  try {
    deploymentId = await registerDeployment(resolveDeployUrl(PROBE_PORT));
    out(`[vo-semantics] registered deployment ${deploymentId}`);
    await new Promise((res) => setTimeout(res, 1500));

    const N = 4;

    // ── SAME KEY → must serialise ────────────────────────────────────────
    const sameKey = `same-${Date.now()}`;
    out(`\n[vo-semantics] SAME-KEY: firing ${N} concurrent invocations at key '${sameKey}' (hold ${HOLD_MS}ms each)`);
    const sameStart = Date.now();
    const sameResults = await Promise.all(Array.from({ length: N }, () => bump(sameKey)));
    const sameWall = Date.now() - sameStart;
    sameResults.sort((a, b) => a.enteredAt - b.enteredAt);
    for (const r of sameResults) {
      out(`  counter=${r.counter}  window=[${r.enteredAt - sameStart}..${r.exitedAt - sameStart}]ms`);
    }
    const counters = sameResults.map((r) => r.counter).sort((a, b) => a - b);
    const serialised = JSON.stringify(counters) === JSON.stringify([1, 2, 3, 4]);
    let anyOverlap = false;
    for (let i = 0; i < sameResults.length; i += 1) {
      for (let j = i + 1; j < sameResults.length; j += 1) {
        if (overlaps(sameResults[i], sameResults[j])) anyOverlap = true;
      }
    }
    out(`  -> counters=${JSON.stringify(counters)} (expect [1,2,3,4]); windows overlap=${anyOverlap} (expect false)`);
    out(`  -> wall-clock ${sameWall}ms (serial expectation ~${N * HOLD_MS}ms)`);
    const sameKeyPass = serialised && !anyOverlap && sameWall >= (N - 1) * HOLD_MS;

    // ── DIFFERENT KEYS → must parallelise ────────────────────────────────
    out(`\n[vo-semantics] DIFFERENT-KEYS: firing ${N} concurrent invocations at ${N} distinct keys`);
    const diffStart = Date.now();
    const diffResults = await Promise.all(
      Array.from({ length: N }, (_unused, i) => bump(`diff-${Date.now()}-${i}`)),
    );
    const diffWall = Date.now() - diffStart;
    for (const r of diffResults) {
      out(`  key=${r.key} counter=${r.counter} window=[${r.enteredAt - diffStart}..${r.exitedAt - diffStart}]ms`);
    }
    // Each distinct key is fresh, so each sees counter 1.
    const allFresh = diffResults.every((r) => r.counter === 1);
    // Their windows should overlap (parallel) — check at least one overlapping pair.
    let diffOverlap = false;
    for (let i = 0; i < diffResults.length; i += 1) {
      for (let j = i + 1; j < diffResults.length; j += 1) {
        if (overlaps(diffResults[i], diffResults[j])) diffOverlap = true;
      }
    }
    out(`  -> all counters=1 (fresh per key)=${allFresh}; windows overlap=${diffOverlap} (expect true)`);
    out(`  -> wall-clock ${diffWall}ms (parallel expectation ~${HOLD_MS}ms, well below serial ~${N * HOLD_MS}ms)`);
    const diffKeyPass = allFresh && diffOverlap && diffWall < N * HOLD_MS;

    out('');
    if (sameKeyPass && diffKeyPass) {
      out('[vo-semantics] VIRTUAL-OBJECT SEMANTICS PROVEN:');
      out('  - SAME key serialised: counters 1..4, no overlapping windows, wall-clock ~ serial sum');
      out('  - DIFFERENT keys parallelised: each fresh (counter=1), windows overlap, wall-clock ~ one hold');
      return 0;
    }
    out(`[vo-semantics] FAILED: sameKeyPass=${sameKeyPass} diffKeyPass=${diffKeyPass}`);
    return 1;
  } finally {
    if (deploymentId) {
      out(`[vo-semantics] deregistering deployment ${deploymentId}`);
      await deregisterDeployment(deploymentId);
    }
    close();
  }
}

function out(line = ''): void {
  process.stdout.write(`${line}\n`);
}

main()
  .then((code) => process.exit(code))
  .catch((err: unknown) => {
    const msg = err instanceof Error ? err.message : String(err);
    process.stderr.write(`[vo-semantics] ${msg}\n`);
    process.exit(1);
  });
