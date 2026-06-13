/**
 * Audit-export proof endpoint — hosts the FULL production agentINVEST surface (`runEndpoint`,
 * including the REAL `investmentOperation` VO + the `auditJournalExport` handler) for the
 * live export proof. NOT a probe: the proof runs a real operation on the production VO to produce a
 * real `operation-closed` audit record, then the export gathers + chains + writes that REAL record.
 *
 * It feeds a DETERMINISTIC fixture plan via AGENTINVEST_DISPATCH_FIXTURE_PLAN (the env-gated proof
 * seam in `investment-operation.ts`) so seam-1 bypasses the LLM call — the audit record produced is
 * REAL VO state (not a fixture record), only the planner's non-determinism is removed. The shared
 * Python `:9091` endpoint (bd09/argResolver/…) is reused; this TS endpoint is the one the controller
 * spawns + tears down (reuse-safe).
 */
import { runEndpoint } from '../substrate/endpoint.js';
import { awaitAdminReady, registerDeployment, resolveDeployUrl } from '../substrate/restate-reach.js';
import { writeFileSync } from 'node:fs';

const PORT = Number(process.env.AGENTINVEST_AUDIT_PROOF_PORT ?? 9096);
const READY_FILE = process.env.AUDIT_PROOF_READY_FILE;

async function main(): Promise<void> {
  const server = await runEndpoint(PORT);
  process.stderr.write(
    `[audit-export-proof-endpoint] listening on :${PORT} (pid ${process.pid}); ` +
      `fixture=${process.env.AGENTINVEST_DISPATCH_FIXTURE_PLAN ? 'set' : '(unset)'}\n`,
  );

  await awaitAdminReady();
  const id = await registerDeployment(resolveDeployUrl(PORT));
  process.stderr.write(`[audit-export-proof-endpoint] registered deployment ${id}\n`);

  if (READY_FILE) {
    writeFileSync(READY_FILE, `${process.pid}\n`);
    process.stderr.write(`[audit-export-proof-endpoint] ready (wrote ${READY_FILE})\n`);
  }
  // Hold open; the controller drives + tears down this exact process.
  await new Promise(() => {});
  void server;
}

main().catch((err: unknown) => {
  const msg = err instanceof Error ? err.message : String(err);
  process.stderr.write(`[audit-export-proof-endpoint] ${msg}\n`);
  process.exit(1);
});
