#!/usr/bin/env node
/**
 * OIM-151 LIVE audit-export proof — gather REAL audit records → chain → write JSON-L → verify green.
 *
 * Brings up the FULL production agentINVEST TS endpoint (the REAL investmentOperation VO +
 * auditJournalExport), runs ONE real operation on the production VO to produce a real
 * `operation-closed` audit record (a DETERMINISTIC fixture plan via AGENTINVEST_DISPATCH_FIXTURE_PLAN
 * — no LLM call; the audit record is REAL VO state, only the planner's non-determinism removed),
 * then runs `audit-export` (gather→chain→write) + `audit-verify` over the REAL record and asserts the
 * export verifies GREEN.
 *
 * REUSE-SAFE (OIM-184). The shared Python :9091 endpoint (bd09/argResolver/navData/agentinvestPlanner)
 * is REUSED if already registered — NEVER torn down (other local projects sharing the dev substrate
 * + concurrent OpenIM work depend on it). Only the TS endpoint THIS run spawns is pruned on exit.
 * NEVER `wsl --shutdown`.
 *
 * Run (from reference/, substrate up via `pnpm dev:restate`, marts built via `pnpm dbt:build`):
 *   node scripts/audit-export-live-proof.mjs   (or: pnpm audit-export-live)
 */
import { spawn, execFileSync, spawnSync } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { tmpdir } from 'node:os';
import path from 'node:path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REFERENCE_ROOT = path.resolve(__dirname, '..');
const TS_DIR = path.join(REFERENCE_ROOT, 'ts');
const ADMIN_URL = process.env.RESTATE_ADMIN_URL ?? 'http://localhost:9070';
const INGRESS_URL = process.env.RESTATE_INGRESS_URL ?? 'http://localhost:8080';
const isWin = process.platform === 'win32';
const TS_PORT = process.env.AUDIT_PROOF_PORT ?? '9096';

const work = mkdtempSync(path.join(tmpdir(), 'agentinvest-audit-export-'));
const EXPORT_DIR = path.join(work, 'export');
const READY_FILE = path.join(work, 'ts-ready.pid');

function log(line) {
  process.stderr.write(`[audit-export-live] ${line}\n`);
}

/** A deterministic fixture plan — ONE valid SO-09-01 step (no LLM). Produces a real audit record. */
const FIXTURE_PLAN = {
  steps: [
    {
      soId: 'SO-09-01',
      args: { beginning_value: '1000000', ending_value: '1050000', period_days: 90, cash_flows: [] },
      rationale: 'audit-export live-proof fixture step',
    },
  ],
  riskScore: 0.05,
  summary: 'audit-export live-proof — one total-return step (fixture, no LLM)',
};

function startTsEndpoint() {
  const entry = path.join(TS_DIR, 'src', 'audit', 'audit-export-proof-endpoint.ts');
  const env = {
    ...process.env,
    AGENTINVEST_AUDIT_PROOF_PORT: String(TS_PORT),
    AUDIT_PROOF_READY_FILE: READY_FILE,
    AGENTINVEST_DISPATCH_FIXTURE_PLAN: JSON.stringify(FIXTURE_PLAN),
  };
  log(`starting the FULL production TS endpoint on :${TS_PORT} (investmentOperation + auditJournalExport)...`);
  return spawn(process.execPath, ['--import', 'tsx', entry], {
    cwd: TS_DIR,
    stdio: ['ignore', 'inherit', 'inherit'],
    env,
  });
}

function killTree(child) {
  if (!child) return;
  if (isWin) {
    try {
      execFileSync('taskkill', ['/PID', String(child.pid), '/T', '/F'], { stdio: 'ignore' });
    } catch {
      child.kill('SIGKILL');
    }
  } else {
    child.kill('SIGKILL');
  }
}

async function adminHealthy() {
  try {
    const r = await fetch(`${ADMIN_URL}/health`, { signal: AbortSignal.timeout(2000) });
    return r.ok;
  } catch {
    return false;
  }
}

async function serviceRegistered(service) {
  try {
    const r = await fetch(`${ADMIN_URL}/services/${service}/openapi`, { signal: AbortSignal.timeout(3000) });
    return r.ok;
  } catch {
    return false;
  }
}

async function waitFor(predicate, timeoutMs, label) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await predicate()) return true;
    await new Promise((res) => setTimeout(res, 500));
  }
  throw new Error(`timed out waiting for: ${label}`);
}

async function executeOperation(key) {
  const res = await fetch(`${INGRESS_URL}/investmentOperation/${encodeURIComponent(key)}/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'idempotency-key': key },
    body: JSON.stringify({ kind: 'audit-export-live-proof', params: { task: FIXTURE_PLAN.summary } }),
    signal: AbortSignal.timeout(120_000),
  });
  if (!res.ok) throw new Error(`execute failed ${res.status}: ${await res.text()}`);
  return res.json();
}

/** Prune ONLY the TS deployment we registered (scoped to our port) — never the shared :9091. */
async function pruneOurTsDeployment() {
  try {
    const r = await fetch(`${ADMIN_URL}/deployments`, { signal: AbortSignal.timeout(4000) });
    if (!r.ok) return;
    const body = await r.json();
    for (const dep of body.deployments ?? []) {
      const isOurs = typeof dep.uri === 'string' && dep.uri.includes(`:${TS_PORT}`);
      if (isOurs && dep.id) {
        await fetch(`${ADMIN_URL}/deployments/${encodeURIComponent(dep.id)}?force=true`, {
          method: 'DELETE',
          signal: AbortSignal.timeout(4000),
        }).catch(() => undefined);
        log(`pruned OUR TS deployment ${dep.id} (${dep.uri})`);
      }
    }
  } catch {
    /* best-effort */
  }
}

/**
 * Run a ts-package CLI (audit-export / audit-verify) and capture stdout + exit code.
 * Invokes tsx DIRECTLY via process.execPath (the same way startTsEndpoint launches the
 * endpoint) rather than through `pnpm.cmd exec` — Node's CVE-2024-27980 patch refuses to
 * spawn a `.cmd`/`.bat` without `shell:true`, so the previous `spawnSync('pnpm.cmd', …)`
 * returned `status:null` (no exit code, empty stderr) on a patched Windows Node. scriptArgs
 * is `[<ts-relative-entry>, ...cliArgs]`, e.g. `['src/audit/audit-export-cli.ts', '--dir', dir]`.
 */
function runTsCli(scriptArgs) {
  const [entryRel, ...cliArgs] = scriptArgs;
  const entry = path.join(TS_DIR, entryRel);
  const r = spawnSync(
    process.execPath,
    ['--import', 'tsx', entry, ...cliArgs],
    {
      cwd: TS_DIR,
      encoding: 'utf8',
      env: { ...process.env, AGENTINVEST_AUDIT_EXPORT_DIR: EXPORT_DIR },
    },
  );
  return { code: r.status, stdout: r.stdout ?? '', stderr: r.stderr ?? '' };
}

let tsChild = null;

async function main() {
  if (!(await adminHealthy())) {
    throw new Error(`Restate admin not reachable at ${ADMIN_URL}. Bring it up: (cd ${REFERENCE_ROOT} && pnpm dev:restate)`);
  }

  // Reuse-safe: the shared Python :9091 must already be up (we NEVER spawn/teardown it here).
  const pyUp = await serviceRegistered('bd09');
  log(`shared Python bd09 registered (reused, never torn down): ${pyUp}`);
  if (!pyUp) {
    throw new Error('shared Python endpoint (:9091, bd09) not registered — bring it up first; this proof reuses it, it does not spawn it.');
  }

  tsChild = startTsEndpoint();
  await waitFor(() => serviceRegistered('auditJournalExport'), 60_000, 'TS endpoint (auditJournalExport) registered');
  log('TS endpoint registered (investmentOperation + auditJournalExport).');

  // 1. Run a REAL operation on the production VO → a real operation-closed audit record.
  const key = `audit-export-proof-${Date.now()}`;
  log(`executing a real operation (key=${key}) to produce an operation-closed audit record...`);
  const result = await executeOperation(key);
  log(`operation completed: status=${result.status}, auditRecord.kind=${result.auditRecord?.kind}`);
  if (result.auditRecord?.kind !== 'operation-closed') {
    throw new Error(`expected an operation-closed audit record; got ${JSON.stringify(result.auditRecord)}`);
  }

  // 2. Export — gather the REAL records (admin + ingress) → chain → write JSON-L + manifest.
  log('running audit-export (gather REAL records → chain → write)...');
  const exp = runTsCli(['src/audit/audit-export-cli.ts', '--dir', EXPORT_DIR]);
  process.stderr.write(exp.stdout);
  if (exp.code !== 0) throw new Error(`audit-export failed (exit ${exp.code}): ${exp.stderr}`);
  const dataMatch = exp.stdout.match(/data:\s+(\S+\.jsonl)/);
  if (!dataMatch) throw new Error(`could not find the written data file in audit-export output:\n${exp.stdout}`);
  const dataPath = dataMatch[1];
  const recMatch = exp.stdout.match(/records:\s+(\d+)/);
  const recordCount = recMatch ? Number(recMatch[1]) : -1;
  log(`export wrote ${recordCount} record(s) → ${dataPath}`);
  if (recordCount < 1) throw new Error(`expected at least 1 real record in the export; got ${recordCount}`);

  // 3. Verify — recompute the chain over the REAL record(s); assert GREEN.
  log('running audit-verify over the REAL export...');
  const ver = runTsCli(['src/audit/audit-verify-cli.ts', dataPath]);
  process.stderr.write(ver.stdout);
  process.stderr.write(ver.stderr);
  if (ver.code !== 0) throw new Error(`audit-verify did NOT pass the real export (exit ${ver.code})`);
  if (!/CHAIN VERIFIED/.test(ver.stdout)) throw new Error(`audit-verify output did not confirm a verified chain:\n${ver.stdout}`);

  log('');
  log('LIVE EXPORT PROVEN:');
  log(`  - a REAL operation-closed audit record was produced on the production VO`);
  log(`  - audit-export gathered ${recordCount} real record(s) via the admin+ingress read path`);
  log(`  - the JSON-L export + manifest were written (chain well-formed)`);
  log(`  - audit-verify confirmed the REAL export GREEN (exit 0)`);
  log('');
}

let exitCode = 0;
main()
  .catch((err) => {
    log(`FAILED: ${err.message}`);
    exitCode = 1;
  })
  .finally(async () => {
    killTree(tsChild);
    await pruneOurTsDeployment();
    try {
      rmSync(work, { recursive: true, force: true });
    } catch {
      /* best-effort */
    }
    // Sanity: confirm the shared :9091 survived (we never touched it).
    const pyStill = await serviceRegistered('bd09');
    log(`shared Python :9091 (bd09) still registered after teardown: ${pyStill} (reuse-safe, never torn down)`);
    process.exit(exitCode);
  });
