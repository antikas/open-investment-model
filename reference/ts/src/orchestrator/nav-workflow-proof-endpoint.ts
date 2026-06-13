/**
 * NAV-workflow-proof endpoint — hosts the REAL `navCalculation` workflow (the production
 * workflow, also bound into `endpoint.ts`), NOT a probe. This is the endpoint the NAV-strike
 * proofs run against, so the multi-step journaled strike, the gate-at-publish, the §A1
 * reconciliation and the crash-mid-step recovery (incl. publish-exactly-once) are all proven
 * on the PRODUCTION workflow — never a substituted probe.
 *
 * It binds ONLY the workflow (the `navData` marts-read service is hosted by the Python
 * endpoint, registered separately by the proof controller). On a Windows/WSL2 host the bind
 * widens to 0.0.0.0 so Restate-in-WSL2 can reach this Windows-host listener; otherwise
 * loopback. The controller writes a ready-file with this pid so the crash proof can SIGKILL
 * the exact process and confirm a real restart.
 *
 * The crash windows are env-gated INSIDE the workflow code (`AGENTINVEST_NAV_PREPUBLISH_
 * CRASH_DELAY_MS` — the between-approval-and-publish pause for the publish-exactly-once proof),
 * NO-OP when unset, so this endpoint is byte-identical to the production binding.
 */
import { createServer } from 'node:http2';
import { endpoint as restateEndpoint } from '@restatedev/restate-sdk';
import { navCalculation } from './nav-calculation-workflow.js';
import { approvalRegistry, approvalRegistryReader } from './approval-registry.js';
import {
  awaitAdminReady,
  isWindowsWsl2Host,
  registerDeployment,
  resolveDeployUrl,
} from '../substrate/restate-reach.js';
import { writeFileSync } from 'node:fs';

const PORT = Number(process.env.AGENTINVEST_NAV_PROOF_PORT ?? 9099);
const READY_FILE = process.env.NAV_PROOF_READY_FILE;

async function main(): Promise<void> {
  // Bind the additive pending-approvals registry beside the workflow so the gate's
  // fire-and-forget registry send is deliverable in the proof too (the
  // gate's own pause/resolve/timeout behaviour is unchanged either way).
  const e = restateEndpoint().bind(navCalculation).bind(approvalRegistry).bind(approvalRegistryReader);
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
    `[nav-workflow-proof-endpoint] listening on ${bind}:${PORT} (pid ${process.pid}); ` +
      `prepublishCrashDelay=${process.env.AGENTINVEST_NAV_PREPUBLISH_CRASH_DELAY_MS ?? '(unset)'}\n`,
  );

  await awaitAdminReady();
  const id = await registerDeployment(resolveDeployUrl(PORT));
  process.stderr.write(`[nav-workflow-proof-endpoint] registered deployment ${id}\n`);

  if (READY_FILE) {
    writeFileSync(READY_FILE, `${process.pid}\n`);
    process.stderr.write(`[nav-workflow-proof-endpoint] ready (wrote ${READY_FILE})\n`);
  }

  // Hold the process open; the controller drives it (and, for the crash proof, SIGKILLs it).
  await new Promise(() => {});
}

main().catch((err: unknown) => {
  const msg = err instanceof Error ? err.message : String(err);
  process.stderr.write(`[nav-workflow-proof-endpoint] ${msg}\n`);
  process.exit(1);
});
