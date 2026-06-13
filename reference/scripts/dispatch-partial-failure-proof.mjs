#!/usr/bin/env node
/**
 * CLEAN PARTIAL-FAILURE proof for the DISPATCH step (seam 2) — the HEADLINE
 * proof. On the REAL `investmentOperation` VO (not a probe).
 *
 * What it proves: when ONE dispatched step fails deterministically, the siblings
 * STILL complete and the failure is SURFACED cleanly — never swallowed, never a
 * whole-operation abort, never a retry-storm. This is the `Promise.allSettled`
 * contract: `Promise.all` would reject fail-fast and kill the siblings (the gate
 * this proof exists to defend).
 *
 * Mechanism:
 *   1. Start the PYTHON endpoint (bd09 — the dispatch target); wait for it.
 *   2. Build a deterministic fixture plan with THREE steps:
 *        - SO-09-01 with VALID args        (a healthy sibling),
 *        - SO-09-01 with an ENGINEERED BAD ARG (an extra key under the tool's
 *          extra="forbid" input → bd09 raises a deterministic TerminalError 400,
 *          retry_count=0 — the honest "planner couldn't resolve the args" case),
 *        - SO-09-05 with VALID args        (another healthy sibling).
 *   3. Start a TS dispatch-proof endpoint (the REAL investmentOperation) fed that
 *      fixture; invoke execute; time it.
 *   4. Assert (the whole class, not one): the operation completes (no abort); the
 *      bad step is `rejected` with its surfaced bd09 error; BOTH siblings are
 *      `fulfilled`; the failure is present in stepResults (not dropped); and the
 *      wall-clock is well under a retry-storm (a terminal error does NOT retry —
 *      the operation returns promptly, not after bounded/unbounded retries).
 *
 * Run (from reference/, substrate up via `pnpm dev:restate`):
 *   node scripts/dispatch-partial-failure-proof.mjs   (or: pnpm dispatch-partial-failure)
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

const PROOF_PORT = process.env.DISPATCH_PARTIAL_PORT ?? '9099';
// A terminal error returns promptly; a retry-storm would blow past this. Generous
// to absorb a cold path, but far below a bounded-retry ladder of a "transient" error.
const RETRY_STORM_CEILING_MS = Number(process.env.DISPATCH_RETRY_STORM_CEILING_MS ?? 15_000);

const work = mkdtempSync(path.join(tmpdir(), 'agentinvest-dispatch-partial-'));

function log(line) {
  process.stderr.write(`[dispatch-partial] ${line}\n`);
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

/**
 * A deterministic fixture plan: a healthy SO-09-01, an ENGINEERED BAD-ARG SO-09-01
 * (an extra key the tool's extra="forbid" input rejects → terminal 400), and a
 * healthy SO-09-05. The bad arg is the honest "planner could not resolve the args"
 * case.
 */
function buildPartialFailurePlan() {
  return {
    steps: [
      {
        soId: 'SO-09-01',
        args: { beginning_value: '1000000', ending_value: '1050000', period_days: 90, cash_flows: [] },
        rationale: 'healthy sibling A',
      },
      {
        soId: 'SO-09-01',
        // ENGINEERED DETERMINISTIC FAILURE: `not_a_real_field` is an extra key the
        // SO-09-01 input (extra="forbid") rejects → bd09 raises TerminalError(400),
        // retry_count=0. The honest unresolved-args case.
        args: { beginning_value: '1000000', ending_value: '1050000', period_days: 90, not_a_real_field: 'x' },
        rationale: 'engineered bad-arg step (unresolved args → terminal failure)',
      },
      {
        soId: 'SO-09-05',
        args: {
          segments: [
            { segment: 'equity', weight: '0.6', segment_return: '0.05' },
            { segment: 'bonds', weight: '0.4', segment_return: '0.02' },
          ],
        },
        rationale: 'healthy sibling B',
      },
    ],
    riskScore: 0.05,
    summary: 'dispatch partial-failure fixture (one terminal step amid healthy siblings)',
  };
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
  log('starting the PYTHON endpoint (bd09 + agentinvestPlanner)...');
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

function startTsEndpoint({ port, readyFile, fixturePlan }) {
  const entry = path.join(TS_DIR, 'src', 'orchestrator', 'dispatch-proof-endpoint.ts');
  const child = spawn(process.execPath, ['--import', 'tsx', entry], {
    cwd: TS_DIR,
    stdio: ['ignore', 'inherit', 'inherit'],
    env: {
      ...process.env,
      AGENTINVEST_DISPATCH_PROOF_PORT: String(port),
      DISPATCH_PROOF_READY_FILE: readyFile,
      AGENTINVEST_DISPATCH_FIXTURE_PLAN: JSON.stringify(fixturePlan),
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

async function timedExecute(key, fixturePlan) {
  const started = Date.now();
  const res = await fetch(`${INGRESS_URL}/investmentOperation/${encodeURIComponent(key)}/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ kind: 'dispatch-partial-failure-proof', params: { task: fixturePlan.summary } }),
    signal: AbortSignal.timeout(60_000),
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
// Did THIS run spawn the shared Python endpoint (bd09/agentinvestPlanner/pyTools on
// :9091)? Only true if we started it; false on reuse. The TS proof endpoint is always
// this-run-spawned (always killed); the shared Python endpoint is killed ONLY if we
// spawned it — reusing then killing it would strip the shared deployment that other
// local projects sharing the dev substrate + concurrent OpenIM work depend on.
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
  log(`work dir ${work}; retry-storm ceiling ${RETRY_STORM_CEILING_MS}ms`);
  if (!(await adminHealthy())) {
    log(`shared Restate admin not reachable at ${ADMIN_URL}. Boot it: (cd ${REFERENCE_ROOT} && pnpm dev:restate).`);
    process.exit(1);
  }

  const fixturePlan = buildPartialFailurePlan();

  // Reuse the running bd09 if it is already registered (the shared OpenIM Python
  // endpoint is often already up on :9091); only spawn one if it is not, so we do
  // not collide with the pre-existing endpoint on the port.
  if (await awaitServiceRegistered('bd09', 2)) {
    log('bd09 already registered — reusing the running Python endpoint (no spawn). It will be LEFT INTACT on exit.');
  } else {
    pyChild = startPyEndpoint();
    pySpawnedByUs = true;
    if (!(await awaitServiceRegistered('bd09'))) {
      log('bd09 did not register within the timeout. Aborting.');
      killAll();
      process.exit(1);
    }
    log('bd09 registered (dispatch target reachable).');
  }

  const ready = path.join(work, 'ready');
  log('starting the dispatch-proof endpoint (the REAL investmentOperation, partial-failure fixture)...');
  tsChild = startTsEndpoint({ port: PROOF_PORT, readyFile: ready, fixturePlan });
  await waitFor(() => existsSync(ready), 60_000, 'dispatch-proof endpoint ready');
  const pid = readFileSync(ready, 'utf8').trim();
  log(`endpoint ready (pid ${pid}); registered on :${PROOF_PORT}.`);
  await new Promise((res) => setTimeout(res, 1000));

  const key = `partial-${Date.now()}`;
  const { result, elapsedMs } = await timedExecute(key, fixturePlan);

  const stepResults = result.stepResults ?? [];
  const byIndex = (i) => stepResults.find((r) => r.index === i);
  const siblingA = byIndex(0);
  const badStep = byIndex(1);
  const siblingB = byIndex(2);

  log('');
  log('RESULT:');
  log(`  operation status:   ${result.status} (completed = NOT aborted by the failing step)`);
  log(`  fulfilled / rejected: ${result.fulfilledCount} / ${result.rejectedCount}`);
  log(`  step[0] sibling A:  ${siblingA && siblingA.status}`);
  log(`  step[1] bad-arg:    ${badStep && badStep.status}  error=${badStep && badStep.error}`);
  log(`  step[2] sibling B:  ${siblingB && siblingB.status}`);
  log(`  wall-clock:         ${elapsedMs}ms (retry-storm ceiling ${RETRY_STORM_CEILING_MS}ms — a terminal error does NOT retry)`);

  const completed = result.status === 'completed';
  const siblingsFulfilled = siblingA?.status === 'fulfilled' && siblingB?.status === 'fulfilled';
  const badRejected = badStep?.status === 'rejected';
  const failureSurfaced = badRejected && typeof badStep.error === 'string' && badStep.error.length > 0;
  const countsRight = result.fulfilledCount === 2 && result.rejectedCount === 1;
  const noRetryStorm = elapsedMs < RETRY_STORM_CEILING_MS;

  killAll();
  await new Promise((res) => setTimeout(res, 800));
  await pruneDeployments('investmentOperation', PROOF_PORT);
  rmSync(work, { recursive: true, force: true });

  const ok = completed && siblingsFulfilled && badRejected && failureSurfaced && countsRight && noRetryStorm;
  log('');
  if (ok) {
    log('CLEAN PARTIAL-FAILURE PROVEN (the headline audit gate):');
    log('  - one dispatched step failed deterministically (bd09 TerminalError, an unresolved-args step)');
    log('  - the siblings STILL completed (the operation was NOT aborted — allSettled, not Promise.all fail-fast)');
    log('  - the failure was SURFACED cleanly in stepResults (not swallowed, not a silent drop)');
    log(`  - NO retry-storm: the operation returned in ${elapsedMs}ms (a terminal error is not retried)`);
    process.exit(0);
  }
  log(
    `FAILED: completed=${completed} siblingsFulfilled=${siblingsFulfilled} badRejected=${badRejected} ` +
      `failureSurfaced=${failureSurfaced} countsRight=${countsRight} noRetryStorm=${noRetryStorm}`,
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
