/**
 * Dispatch-proof endpoint — hosts the REAL `investmentOperation` virtual object
 * (the production orchestrator, bound into `endpoint.ts`), NOT a probe. This is the
 * endpoint the seam-2 DISPATCH proofs run against, so the parallel fan-out, the
 * latency-vs-serial, the clean partial-failure and the journaled-replay are all
 * proven on the PRODUCTION VO (the OIM-104 P9 bar — never a substituted probe).
 *
 * The proofs feed a DETERMINISTIC fixture plan via AGENTINVEST_DISPATCH_FIXTURE_PLAN
 * (the env-gated proof seam in `investment-operation.ts`), so seam 1 bypasses the
 * model call and the dispatch path runs against a fixed plan with NO LLM API call.
 * The fixture only removes the model's non-determinism; the dispatch step (seam 2)
 * — the parallel `Promise.allSettled` fan-out of `execute_so` over `bd09` — is the
 * real production path.
 *
 * It binds ONLY the orchestrator (the `bd09` service is hosted by the Python
 * endpoint, registered separately by the proof controller). On a Windows/WSL2 host
 * the bind widens to 0.0.0.0 so Restate-in-WSL2 can reach this Windows-host
 * listener; otherwise loopback. The controller writes a ready-file with this pid so
 * the crash proof can SIGKILL the exact process and confirm a real restart.
 */
import { createServer } from 'node:http2';
import { endpoint as restateEndpoint } from '@restatedev/restate-sdk';
import { investmentOperation } from './investment-operation.js';
import { approvalRegistry, approvalRegistryReader } from './approval-registry.js';
import {
  awaitAdminReady,
  isWindowsWsl2Host,
  registerDeployment,
  resolveDeployUrl,
} from '../substrate/restate-reach.js';
import { writeFileSync } from 'node:fs';

const PORT = Number(process.env.AGENTINVEST_DISPATCH_PROOF_PORT ?? 9097);
const READY_FILE = process.env.DISPATCH_PROOF_READY_FILE;

async function main(): Promise<void> {
  // Bind the additive pending-approvals registry beside the orchestrator so the
  // gate's fire-and-forget registry send (OIM-142) is deliverable in the proof too
  // (the gate's own pause/resolve/timeout behaviour is unchanged either way).
  const e = restateEndpoint().bind(investmentOperation).bind(approvalRegistry).bind(approvalRegistryReader);
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
    `[dispatch-proof-endpoint] listening on ${bind}:${PORT} (pid ${process.pid}); ` +
      `fixture=${process.env.AGENTINVEST_DISPATCH_FIXTURE_PLAN ? 'set' : '(unset)'} ` +
      `delay=${process.env.AGENTINVEST_CRASH_PROOF_DELAY_MS ?? '(unset)'}\n`,
  );

  await awaitAdminReady();
  const id = await registerDeployment(resolveDeployUrl(PORT));
  process.stderr.write(`[dispatch-proof-endpoint] registered deployment ${id}\n`);

  if (READY_FILE) {
    writeFileSync(READY_FILE, `${process.pid}\n`);
    process.stderr.write(`[dispatch-proof-endpoint] ready (wrote ${READY_FILE})\n`);
  }

  // Hold the process open; the controller drives it (and, for the crash proof,
  // SIGKILLs it).
  await new Promise(() => {});
}

main().catch((err: unknown) => {
  const msg = err instanceof Error ? err.message : String(err);
  process.stderr.write(`[dispatch-proof-endpoint] ${msg}\n`);
  process.exit(1);
});
