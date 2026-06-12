#!/usr/bin/env node
/**
 * DEV-STATE CLEAR for the pending-approvals registry (OIM-142 cycle-2, deliverable #5).
 *
 * The cycle-1 registry accumulated phantom `pending` entries (a decided/timed-out/CLI-
 * resolved approval left a permanent `pending` row, because only the UI's own resolve ever
 * marked the registry — P-MAJOR-1). The cycle-2 fold makes the gate mark the registry on
 * EVERY terminal path and the reader reconcile liveness, so NEW entries leave the queue
 * correctly. This script clears the PRE-FOLD dev-state debris already persisted in the
 * shared engine — the ~10 phantom `pending` VO entries P read live — so the queue starts
 * clean (and the reader's reconcile loop is not weighed down by a long-stale index).
 *
 * MECHANISM (read-only-then-clear, no app code): the Restate admin modify-state endpoint
 * `POST {admin}/services/approvalRegistry/state` with `{object_key, new_state:{}}` replaces
 * a virtual-object's state with empty. We clear the shared `__index__` membership object
 * (so the reader enumerates nothing stale) AND each per-operation `entry` it referenced.
 * The awakeable is NOT touched — it is the decision of record and is already terminal for
 * every stale entry (these are dead ops). Other local projects sharing the dev substrate
 * and the Python `:9091` endpoint are not touched. NEVER `wsl --shutdown`.
 *
 * Idempotent + safe to re-run. Run (substrate up):
 *   node scripts/clear-approval-registry-state.mjs   (or: pnpm approval-registry:clear)
 */
const ADMIN_URL = process.env.RESTATE_ADMIN_URL ?? 'http://127.0.0.1:9070';
const INGRESS_URL = process.env.RESTATE_INGRESS_URL ?? 'http://127.0.0.1:8080';

function log(line) {
  process.stderr.write(`[clear-approval-registry] ${line}\n`);
}

async function adminHealthy() {
  try {
    const r = await fetch(`${ADMIN_URL}/health`, { signal: AbortSignal.timeout(3000) });
    return r.ok;
  } catch {
    return false;
  }
}

/** Read the shared pending index via the ingress reader (the operationIds the gate has notified about). */
async function readIndex() {
  try {
    const r = await fetch(`${INGRESS_URL}/approvalRegistry/__index__/readIndex`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
      signal: AbortSignal.timeout(15_000),
    });
    if (!r.ok) return [];
    return (await r.json()) ?? [];
  } catch {
    return [];
  }
}

/** Replace a virtual-object's state with empty via the admin modify-state endpoint. */
async function clearObjectState(objectKey) {
  const r = await fetch(`${ADMIN_URL}/services/approvalRegistry/state`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ object_key: objectKey, new_state: {} }),
    signal: AbortSignal.timeout(10_000),
  });
  if (!r.ok) {
    throw new Error(`clear ${objectKey} failed ${r.status}: ${await r.text()}`);
  }
}

async function main() {
  if (!(await adminHealthy())) {
    log(`shared Restate admin not reachable at ${ADMIN_URL}. Boot it: pnpm dev:restate.`);
    process.exit(1);
  }
  const index = await readIndex();
  log(`index holds ${index.length} operationId(s): clearing each per-op entry + the shared __index__.`);

  let cleared = 0;
  for (const operationId of index) {
    try {
      await clearObjectState(operationId);
      cleared += 1;
    } catch (e) {
      log(`  WARN: could not clear ${operationId}: ${e.message}`);
    }
  }
  // Clear the shared membership index last so the reader enumerates nothing stale.
  try {
    await clearObjectState('__index__');
    log(`cleared ${cleared}/${index.length} per-op entries + the shared __index__. The pending queue is now clean.`);
  } catch (e) {
    log(`ERROR clearing __index__: ${e.message}`);
    process.exit(1);
  }

  // Verify.
  const after = await readIndex();
  log(`verify: index now holds ${after.length} operationId(s).`);
  process.exit(after.length === 0 ? 0 : 1);
}

main().catch((err) => {
  log(`ERROR: ${err.message}`);
  process.exit(1);
});
