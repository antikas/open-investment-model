#!/usr/bin/env node
/**
 * LIVE plan→dispatch END-TO-END proof for the DISPATCH step (seam 2, OIM-131).
 *
 * The seam-1→seam-2 chain, end to end, with the REAL planner: a real Sonnet 4.6
 * `.plan()` call (key in reference/.env) → a journaled plan → the dispatch step
 * EXECUTES it over bd09 → stepResults collected. The first time the planner's plan
 * is actually run, on the REAL `investmentOperation` VO.
 *
 * HONEST BOUNDARY (the whole point of the live run): a real plan may carry steps
 * whose args the planner could NOT fully resolve (the abstract-arg → concrete-input
 * resolution / marts-in-the-loop is FORWARD — what the OIM-115 demo did by hand).
 * Dispatch passes the args AS GIVEN; bd09 validates them; a step with unresolved
 * args surfaces as a CLEAN FAILURE (honest v0.1, not a bug). This proof reports
 * which steps FULFILLED vs surfaced-as-clean-failure — it does NOT require all
 * fulfilled. The PASS condition is the CHAIN works: a real plan was produced AND
 * every step was dispatched AND every outcome was collected (fulfilled or clean
 * rejection) AND the operation completed (no abort, no retry-storm).
 *
 * This is the ONE live-API proof; the mechanism proofs (fan-out latency, clean
 * partial-failure, journaled replay) use deterministic fixture plans, no API.
 *
 * Run (from reference/, substrate up, reference/.env with the Sonnet key):
 *   node scripts/dispatch-live-e2e.mjs   (or: pnpm dispatch-live-e2e)
 */
import { spawn } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { tmpdir } from 'node:os';
import path from 'node:path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REFERENCE_ROOT = path.resolve(__dirname, '..');
const TS_DIR = path.join(REFERENCE_ROOT, 'ts');

const ADMIN_URL = process.env.RESTATE_ADMIN_URL ?? 'http://localhost:9070';
const INGRESS_URL = process.env.RESTATE_INGRESS_URL ?? 'http://localhost:8080';
const isWin = process.platform === 'win32';
const WSL_DISTRO = process.env.RESTATE_WSL_DISTRO ?? 'Ubuntu-24.04';

const PROOF_PORT = process.env.DISPATCH_LIVE_PORT ?? '9097';
const LIVE_TASK =
  process.env.DISPATCH_LIVE_TASK ??
  'Compute the total return for fund X over Q1: beginning value 1000000, ending value 1050000, 90-day period, no external cash flows.';

const work = mkdtempSync(path.join(tmpdir(), 'agentinvest-dispatch-live-'));

function log(line) {
  process.stderr.write(`[dispatch-live] ${line}\n`);
}

function toWsl(p) {
  return '/mnt/' + p[0].toLowerCase() + p.slice(2).replace(/\\/g, '/');
}

function wslPrelude() {
  const wslRef = toWsl(REFERENCE_ROOT);
  const repo = toWsl(path.resolve(REFERENCE_ROOT, '..'));
  return (
    `export PATH="$HOME/.local/bin:$PATH"; ` +
    `tr -d '\\r' < ${wslRef}/scripts/lib/agentinvest-venv-path.sh > /tmp/agentinvest-venv-path.sh; ` +
    `. /tmp/agentinvest-venv-path.sh; ` +
    `agentinvest_set_venv_env '${repo}'; ` +
    `cd ${wslRef}/python`
  );
}

function startPyEndpoint() {
  const env = { ...process.env, WSL_UTF8: '1' };
  let cmd;
  let args;
  if (isWin) {
    cmd = 'wsl';
    args = ['-d', WSL_DISTRO, '--', 'bash', '-lc', `${wslPrelude()} && uv run python -m agentinvest_tools.endpoint`];
  } else {
    cmd = 'bash';
    args = ['-lc', `export PATH="$HOME/.local/bin:$PATH" && cd ${REFERENCE_ROOT}/python && uv run python -m agentinvest_tools.endpoint`];
  }
  log('starting the PYTHON endpoint (agentinvestPlanner + bd09 — the live planner + the dispatch target)...');
  return spawn(cmd, args, { stdio: 'inherit', env });
}

async function awaitServiceRegistered(service, timeoutSeconds = 90) {
  const deadline = Date.now() + timeoutSeconds * 1000;
  while (Date.now() < deadline) {
    try {
      const r = await fetch(`${ADMIN_URL}/services/${service}/openapi`, { signal: AbortSignal.timeout(3000) });
      if (r.ok) return true;
    } catch {
      /* retry */
    }
    await new Promise((res) => setTimeout(res, 1500));
  }
  return false;
}

function startTsEndpoint(readyFile) {
  const entry = path.join(TS_DIR, 'src', 'orchestrator', 'dispatch-proof-endpoint.ts');
  // NO AGENTINVEST_DISPATCH_FIXTURE_PLAN — the REAL planner runs at seam 1.
  const child = spawn(process.execPath, ['--import', 'tsx', entry], {
    cwd: TS_DIR,
    stdio: ['ignore', 'inherit', 'inherit'],
    env: {
      ...process.env,
      AGENTINVEST_DISPATCH_PROOF_PORT: String(PROOF_PORT),
      DISPATCH_PROOF_READY_FILE: readyFile,
    },
  });
  return child;
}

async function waitFor(predicate, timeoutMs, label) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await predicate()) return true;
    await new Promise((res) => setTimeout(res, 200));
  }
  throw new Error(`timed out waiting for: ${label}`);
}

async function timedExecute(key) {
  const started = Date.now();
  const res = await fetch(`${INGRESS_URL}/investmentOperation/${encodeURIComponent(key)}/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ kind: 'dispatch-live-e2e', params: { task: LIVE_TASK } }),
    signal: AbortSignal.timeout(120_000),
  });
  const elapsedMs = Date.now() - started;
  if (!res.ok) throw new Error(`execute failed ${res.status}: ${await res.text()}`);
  return { result: await res.json(), elapsedMs };
}

async function adminHealthy() {
  try {
    const r = await fetch(`${ADMIN_URL}/health`, { signal: AbortSignal.timeout(2000) });
    return r.ok;
  } catch {
    return false;
  }
}

async function pruneDeployments(serviceName, port) {
  try {
    const r = await fetch(`${ADMIN_URL}/deployments`, { signal: AbortSignal.timeout(4000) });
    if (!r.ok) return;
    const body = await r.json();
    for (const dep of body.deployments ?? []) {
      const isOurs =
        (dep.services ?? []).some((s) => s.name === serviceName) &&
        typeof dep.uri === 'string' &&
        dep.uri.includes(`:${port}`);
      if (isOurs && dep.id) {
        await fetch(`${ADMIN_URL}/deployments/${encodeURIComponent(dep.id)}?force=true`, {
          method: 'DELETE',
          signal: AbortSignal.timeout(4000),
        }).catch(() => undefined);
        log(`pruned dispatch-proof ${serviceName} deployment ${dep.id} (${dep.uri})`);
      }
    }
  } catch {
    /* best-effort */
  }
}

let pyChild = null;
// Did THIS run spawn the shared Python endpoint (agentinvestPlanner/bd09/pyTools on
// :9091)? Only true if we started it; false if we REUSED an already-running shared
// endpoint. The TS proof endpoint is always this-run-spawned (always killed); the
// shared Python endpoint is killed ONLY if we spawned it — reusing then killing it
// would strip the shared deployment that other local projects sharing the dev
// substrate + concurrent OpenIM work depend on (OIM-131 cycle-2 fold).
let pySpawnedByUs = false;
let tsChild = null;

function killAll() {
  try {
    if (tsChild) tsChild.kill('SIGKILL');
  } catch {
    /* best-effort */
  }
  // Kill the Python endpoint ONLY if THIS run spawned it; never a reused shared one.
  if (pySpawnedByUs) {
    try {
      if (pyChild) pyChild.kill('SIGKILL');
    } catch {
      /* best-effort */
    }
  }
}

async function main() {
  log(`work dir ${work}; live task: "${LIVE_TASK}"`);
  if (!(await adminHealthy())) {
    log(`shared Restate admin not reachable at ${ADMIN_URL}. Boot it: (cd ${REFERENCE_ROOT} && pnpm dev:restate).`);
    process.exit(1);
  }

  // Reuse the running planner + bd09 if already registered (shared :9091); only
  // spawn if not. The live planner needs the Sonnet key, loaded by the running
  // Python endpoint from reference/.env — reusing it keeps the key handling there.
  const plannerUp = await awaitServiceRegistered('agentinvestPlanner', 2);
  const bd09Up = await awaitServiceRegistered('bd09', 2);
  if (plannerUp && bd09Up) {
    log('agentinvestPlanner + bd09 already registered — reusing the running Python endpoint (no spawn). It will be LEFT INTACT on exit.');
  } else {
    pyChild = startPyEndpoint();
    pySpawnedByUs = true;
    if (!(await awaitServiceRegistered('agentinvestPlanner'))) {
      log('agentinvestPlanner did not register within the timeout. Aborting.');
      killAll();
      process.exit(1);
    }
    if (!(await awaitServiceRegistered('bd09'))) {
      log('bd09 did not register within the timeout. Aborting.');
      killAll();
      process.exit(1);
    }
    log('agentinvestPlanner + bd09 registered (live planner + dispatch target reachable).');
  }

  const ready = path.join(work, 'ready');
  log('starting the dispatch-proof endpoint (the REAL investmentOperation; NO fixture — the live planner runs)...');
  tsChild = startTsEndpoint(ready);
  await waitFor(() => existsSync(ready), 60_000, 'dispatch-proof endpoint ready');
  const pid = readFileSync(ready, 'utf8').trim();
  log(`endpoint ready (pid ${pid}); registered on :${PROOF_PORT}.`);
  await new Promise((res) => setTimeout(res, 1000));

  const key = `live-${Date.now()}`;
  log(`invoking investmentOperation/${key}/execute — REAL plan -> dispatch -> stepResults...`);
  const { result, elapsedMs } = await timedExecute(key);

  const steps = result.plan?.steps ?? [];
  const stepResults = result.stepResults ?? [];

  log('');
  log('RESULT (honest, per-step):');
  log(`  plan summary:        ${result.plan?.summary ?? '(none)'}`);
  log(`  plan riskScore:      ${result.plan?.riskScore}`);
  log(`  plan steps:          ${steps.length}  soIds=[${steps.map((s) => s.soId).join(', ')}]`);
  log(`  operation status:    ${result.status}`);
  log(`  fulfilled / rejected: ${result.fulfilledCount} / ${result.rejectedCount}`);
  for (const r of stepResults) {
    if (r.status === 'fulfilled') {
      log(`    step[${r.index}] ${r.soId}: FULFILLED — computedBy=${r.result?.computedBy} methodology=${r.result?.provenance?.methodology}`);
    } else {
      log(`    step[${r.index}] ${r.soId}: CLEAN FAILURE (surfaced) — ${r.error}`);
    }
  }
  log(`  wall-clock:          ${elapsedMs}ms`);

  // PASS condition: the CHAIN works (a real plan was produced, every step was
  // dispatched, every outcome collected, the operation completed) — NOT that every
  // step fulfilled (a real plan may carry an unresolved-args step → a clean failure,
  // the honest forward boundary).
  const chainWorks =
    result.status === 'completed' &&
    steps.length >= 1 &&
    stepResults.length === steps.length &&
    result.fulfilledCount + result.rejectedCount === steps.length;

  // Tear down ONLY what this run spawned: killAll() kills the TS proof endpoint
  // always + the Python endpoint only if WE spawned it; the prune targets only our
  // own investmentOperation TS deployment — never the shared Python deployment.
  killAll();
  await new Promise((res) => setTimeout(res, 800));
  await pruneDeployments('investmentOperation', PROOF_PORT);
  if (!pySpawnedByUs) {
    log('reused the shared Python endpoint — left bd09/agentinvestPlanner/pyTools registered on exit (not stripping a shared resource).');
  }
  rmSync(work, { recursive: true, force: true });

  log('');
  if (chainWorks) {
    log('LIVE plan->dispatch END-TO-END PROVEN:');
    log('  - a REAL Sonnet 4.6 .plan() produced a journaled plan on the production investmentOperation VO');
    log('  - the dispatch step EXECUTED every step over bd09 and collected every outcome');
    log(`  - ${result.fulfilledCount} step(s) fulfilled, ${result.rejectedCount} surfaced as a clean failure (honest v0.1 — unresolved args are forward)`);
    log('  - the operation completed cleanly (no abort, no retry-storm)');
    process.exit(0);
  }
  log(
    `FAILED: chainWorks=${chainWorks} (status=${result.status} steps=${steps.length} ` +
      `stepResults=${stepResults.length} f+r=${result.fulfilledCount}+${result.rejectedCount})`,
  );
  process.exit(1);
}

main().catch((err) => {
  log(`ERROR: ${err.message}`);
  killAll();
  try {
    rmSync(work, { recursive: true, force: true });
  } catch {
    /* best-effort */
  }
  process.exit(1);
});
