/**
 * Full-chain proof endpoint — hosts the REAL `investmentOperation` virtual object (the
 * production orchestrator bound into `endpoint.ts`), NOT a probe. This is the endpoint the
 * full-chain demo + the full-chain crash-replay run against, so the whole
 * plan → resolve → dispatch → approve → aggregate → close chain is exercised on the PRODUCTION VO
 * — never a substituted probe.
 *
 * NO fixture plan (NO `AGENTINVEST_DISPATCH_FIXTURE_PLAN`): seam 1 calls the REAL Sonnet planner,
 * which selects the tools; the RESOLVE step resolves the abstract args against the marts; dispatch
 * runs the resolved args for REAL results; aggregate combines them; close writes the audit record.
 *
 * The crash-replay arms the env-gated `AGENTINVEST_DISPATCH_CRASH_DELAY_MS` durable pause (already
 * in `investment-operation.ts`, between the journaled dispatch and the terminal write) so the
 * controller can SIGKILL the production VO in the fiduciary window: the planner is journaled (one
 * LLM call), the tools are journaled (dispatched once), but the terminal state + the close audit
 * record have not yet written. On resume the journaled plan + step results are READ BACK — the
 * planner is NOT re-called, the tools are NOT re-run, and the audit record is written ONCE.
 *
 * The controller (`scripts/full-chain-demo.mjs`) starts this endpoint, invokes the real
 * `investmentOperation/<id>/execute` for the attribution task, and (for the crash flow) SIGKILLs
 * this process tree mid-pause, restarts a FRESH process, and confirms Restate resumes the SAME
 * `inv_` id to `completed` with the side-effects not duplicated.
 */
import { createServer } from 'node:http2';
import { endpoint as restateEndpoint } from '@restatedev/restate-sdk';
import { investmentOperation } from './investment-operation.js';
import {
  awaitAdminReady,
  isWindowsWsl2Host,
  registerDeployment,
  resolveDeployUrl,
} from '../substrate/restate-reach.js';
import { writeFileSync } from 'node:fs';

const PORT = Number(process.env.AGENTINVEST_FULL_CHAIN_PORT ?? 9098);
const READY_FILE = process.env.FULL_CHAIN_READY_FILE;

async function main(): Promise<void> {
  // Bind the REAL production virtual object — the same `investmentOperation` bound into
  // endpoint.ts, not a probe. No fixture plan: the real planner runs at seam 1.
  const e = restateEndpoint().bind(investmentOperation);
  const bind = isWindowsWsl2Host() ? '0.0.0.0' : '127.0.0.1';
  const server = createServer(e.http2Handler());
  await new Promise<void>((resolve, reject) => {
    const onError = (err: Error): void => {
      server.off('error', onError);
      reject(err);
    };
    server.once('error', onError);
    server.listen({ port: PORT, host: bind }, () => {
      server.off('error', onError);
      resolve();
    });
  });
  process.stderr.write(
    `[full-chain-proof-endpoint] listening on ${bind}:${PORT} (pid ${process.pid}); ` +
      `dispatchCrashDelay=${process.env.AGENTINVEST_DISPATCH_CRASH_DELAY_MS ?? '(unset)'}\n`,
  );

  await awaitAdminReady();
  const id = await registerDeployment(resolveDeployUrl(PORT));
  process.stderr.write(`[full-chain-proof-endpoint] registered deployment ${id}\n`);

  if (READY_FILE) {
    writeFileSync(READY_FILE, `${process.pid}\n`);
    process.stderr.write(`[full-chain-proof-endpoint] ready (wrote ${READY_FILE})\n`);
  }

  // Hold the process open; the controller drives it (and, for the crash flow, SIGKILLs it).
  await new Promise(() => {});
}

main().catch((err: unknown) => {
  const msg = err instanceof Error ? err.message : String(err);
  process.stderr.write(`[full-chain-proof-endpoint] ${msg}\n`);
  process.exit(1);
});
