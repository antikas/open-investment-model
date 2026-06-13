/**
 * Production-shell crash endpoint — hosts the REAL `investmentOperation` virtual
 * object (the production orchestrator shell bound into `endpoint.ts`), NOT a
 * probe. This endpoint lets the crash proof SIGKILL the production
 * `investmentOperation.execute` itself, in the fiduciary-relevant window between
 * its journaled `ctx.run('orchestrator-stub-step')` and its terminal
 * `ctx.set('state','completed')`.
 *
 * HOW THE WINDOW IS REACHED (proof-only, no production behaviour change). The
 * production handler runs straight through — there is no natural await point
 * between the journaled stub step and the terminal state write, so the window is
 * sub-millisecond and not reliably hittable. The handler therefore reads an
 * env-gated, proof-only durable pause (`AGENTINVEST_CRASH_PROOF_DELAY_MS`) in
 * exactly that window: a guarded `ctx.sleep` that is NEVER reached when the env
 * is unset (its journal shape is then byte-for-byte identical to production).
 * THIS endpoint process sets that env; production never does. So the SIGKILL
 * lands after the stub step is journaled and after the proof-pause's `ctx.sleep`
 * entry is journaled, but BEFORE the terminal `ctx.set('state','completed')` —
 * the realistic fiduciary crash window the pre-mortem named.
 *
 * The controller (`scripts/shell-crash-proof.mjs`) starts this endpoint, invokes
 * the real `investmentOperation/<id>/execute`, waits for the journaled step,
 * SIGKILLs this process tree, restarts a FRESH process, and confirms Restate
 * resumes the SAME `inv_` id from the journal to `completed` — the stub step
 * replayed (stable stepId), not re-run, on a new pid.
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

const PORT = Number(process.env.AGENTINVEST_SHELL_CRASH_PORT ?? 9096);
const READY_FILE = required('SHELL_CRASH_READY_FILE');

function required(name: string): string {
  const v = process.env[name];
  if (!v) throw new Error(`shell-crash-endpoint: missing required env ${name}`);
  return v;
}

async function main(): Promise<void> {
  // Bind the REAL production virtual object — the same `investmentOperation`
  // bound into endpoint.ts, not a probe object.
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
    `[shell-crash-endpoint] listening on ${bind}:${PORT} (pid ${process.pid}); ` +
      `AGENTINVEST_CRASH_PROOF_DELAY_MS=${process.env.AGENTINVEST_CRASH_PROOF_DELAY_MS ?? '(unset)'}\n`,
  );

  await awaitAdminReady();
  const id = await registerDeployment(resolveDeployUrl(PORT));
  process.stderr.write(`[shell-crash-endpoint] registered deployment ${id}\n`);

  writeFileSync(READY_FILE, `${process.pid}\n`);
  process.stderr.write(`[shell-crash-endpoint] ready (wrote ${READY_FILE})\n`);

  // Hold the process open; the controller SIGKILLs it.
  await new Promise(() => {});
}

main().catch((err: unknown) => {
  const msg = err instanceof Error ? err.message : String(err);
  process.stderr.write(`[shell-crash-endpoint] ${msg}\n`);
  process.exit(1);
});
