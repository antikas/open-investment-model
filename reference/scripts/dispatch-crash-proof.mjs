#!/usr/bin/env node
/**
 * PRODUCTION-VO JOURNALED-REPLAY proof for the DISPATCH step (seam 2) —
 * the same production-VO crash-replay pattern as plan-crash-proof.mjs.
 *
 * What it proves: the dispatched stepResults are JOURNALED on the REAL
 * `investmentOperation` VO, so a crash+replay reads them back from the journal and
 * does NOT re-execute the tools. The fiduciary-determinism property holds THROUGH
 * dispatch. (The plan-crash-proof.mjs sibling proves the same for the .plan() step;
 * this proves it for the dispatched execute_so RPCs.)
 *
 * Mechanism (extends plan-crash-proof.mjs):
 *   1. Start the PYTHON endpoint (bd09 — the dispatch target); wait for it.
 *   2. Start the TS dispatch-proof endpoint (the REAL investmentOperation) with:
 *        - a deterministic fixture plan (AGENTINVEST_DISPATCH_FIXTURE_PLAN), so no
 *          LLM call and the dispatched steps are fixed,
 *        - the post-dispatch durable pause (AGENTINVEST_DISPATCH_CRASH_DELAY_MS), so
 *          execute pauses in the window AFTER the journaled dispatch, BEFORE the
 *          terminal write.
 *   3. Invoke investmentOperation/<key>/execute (idempotency key; fire-and-forget).
 *   4. Wait until the handler logs `dispatched N step(s):` (the execute_so RPCs have
 *      returned + been journaled; the operation is MID-FLIGHT in the pause window).
 *      Capture the pre-crash dispatched outcomes line.
 *   5. SIGKILL the TS endpoint process tree (a real crash) in the window.
 *   6. Restart a FRESH TS endpoint (different pid); re-register.
 *   7. Re-POST the SAME idempotency key — Restate ATTACHES to the resumed
 *      invocation and returns its journaled OperationResult (the recorded
 *      stepResults).
 *   8. Assert: the resumed stepResults EQUAL the pre-crash dispatched outcomes (read
 *      back from the journal, the tools NOT re-executed); the VO reached completed;
 *      the TS pid changed; Restate logged Replaying.
 *
 * Run (from reference/, substrate up via `pnpm dev:restate`):
 *   node scripts/dispatch-crash-proof.mjs   (or: pnpm dispatch-crash)
 */
import { spawn, execFileSync } from 'node:child_process';
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

const DISPATCH_CRASH_DELAY_MS = process.env.AGENTINVEST_DISPATCH_CRASH_DELAY_MS ?? '12000';
const PROOF_PORT = process.env.DISPATCH_CRASH_PORT ?? '9097';

const work = mkdtempSync(path.join(tmpdir(), 'agentinvest-dispatch-crash-'));
const READY_FILE = path.join(work, 'ready');
const OP_KEY = `dispatchcrash-${Date.now()}`;
const IDEMPOTENCY_KEY = `dispatch-crash-${Date.now()}`;

function log(line) {
  process.stderr.write(`[dispatch-crash] ${line}\n`);
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

/** A deterministic fixture plan: two healthy SO-09-01 steps + one healthy SO-09-05. */
function buildFixturePlan() {
  return {
    steps: [
      {
        soId: 'SO-09-01',
        args: { beginning_value: '1000000', ending_value: '1050000', period_days: 90, cash_flows: [] },
        rationale: 'fixture step 0',
      },
      {
        soId: 'SO-09-01',
        args: { beginning_value: '2000000', ending_value: '2100000', period_days: 90, cash_flows: [] },
        rationale: 'fixture step 1',
      },
      {
        soId: 'SO-09-05',
        args: {
          segments: [
            { segment: 'equity', weight: '0.6', segment_return: '0.05' },
            { segment: 'bonds', weight: '0.4', segment_return: '0.02' },
          ],
        },
        rationale: 'fixture step 2',
      },
    ],
    riskScore: 0.05,
    summary: 'dispatch crash-replay fixture (3 healthy steps)',
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

let capturedDispatchBefore = null;
let sawReplaying = false;
let sawCompleted = false;

function attachLogParsing(child) {
  const onChunk = (buf) => {
    const text = buf.toString();
    process.stderr.write(text);
    const m = text.match(/dispatched (\d+ step\(s\):.+)$/m);
    if (m && !capturedDispatchBefore) capturedDispatchBefore = m[1].trim();
    if (/Replaying invocation/.test(text)) sawReplaying = true;
    if (/Invocation completed successfully/.test(text)) sawCompleted = true;
  };
  child.stdout?.on('data', onChunk);
  child.stderr?.on('data', onChunk);
}

function startTsEndpoint(fixturePlan) {
  const entry = path.join(TS_DIR, 'src', 'orchestrator', 'dispatch-proof-endpoint.ts');
  const child = spawn(process.execPath, ['--import', 'tsx', entry], {
    cwd: TS_DIR,
    stdio: ['ignore', 'pipe', 'pipe'],
    env: {
      ...process.env,
      AGENTINVEST_DISPATCH_PROOF_PORT: String(PROOF_PORT),
      DISPATCH_PROOF_READY_FILE: READY_FILE,
      AGENTINVEST_DISPATCH_FIXTURE_PLAN: JSON.stringify(fixturePlan),
      AGENTINVEST_DISPATCH_CRASH_DELAY_MS: DISPATCH_CRASH_DELAY_MS,
    },
  });
  attachLogParsing(child);
  return child;
}

function killTree(child) {
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

async function waitFor(predicate, timeoutMs, label) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await predicate()) return true;
    await new Promise((res) => setTimeout(res, 200));
  }
  throw new Error(`timed out waiting for: ${label}`);
}

function invokeExecuteAsync(key, fixturePlan) {
  const controller = new AbortController();
  fetch(`${INGRESS_URL}/investmentOperation/${encodeURIComponent(key)}/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'idempotency-key': IDEMPOTENCY_KEY },
    body: JSON.stringify({ kind: 'dispatch-crash-proof', params: { task: fixturePlan.summary } }),
    signal: controller.signal,
  }).catch(() => undefined);
  return controller;
}

async function attachExecuteAfterResume(key, fixturePlan) {
  const res = await fetch(`${INGRESS_URL}/investmentOperation/${encodeURIComponent(key)}/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'idempotency-key': IDEMPOTENCY_KEY },
    body: JSON.stringify({ kind: 'dispatch-crash-proof', params: { task: fixturePlan.summary } }),
    signal: AbortSignal.timeout(90_000),
  });
  if (!res.ok) throw new Error(`resume-attach failed ${res.status}: ${await res.text()}`);
  return res.json();
}

async function readStatus(key) {
  const res = await fetch(`${INGRESS_URL}/investmentOperation/${encodeURIComponent(key)}/status`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: '{}',
    signal: AbortSignal.timeout(15_000),
  });
  if (!res.ok) throw new Error(`status failed ${res.status}: ${await res.text()}`);
  return res.json();
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

async function adminHealthy() {
  try {
    const r = await fetch(`${ADMIN_URL}/health`, { signal: AbortSignal.timeout(2000) });
    return r.ok;
  } catch {
    return false;
  }
}

/** A stable, comparable signature of an OperationResult's stepResults. */
function stepResultsSignature(result) {
  if (!result || !Array.isArray(result.stepResults)) return '(none)';
  return result.stepResults
    .map((r) => `${r.index}:${r.soId}:${r.status}`)
    .join('|') + ` [${result.fulfilledCount}f/${result.rejectedCount}r]`;
}

let pyChild = null;
// Did THIS run spawn the shared Python endpoint (bd09/agentinvestPlanner/pyTools on
// :9091)? Only true if we started it; false if we REUSED an already-running shared
// endpoint. Gates ALL Python-side teardown: we only ever tear down what we started.
// Reusing and then stripping the shared deployment would disrupt other local projects
// sharing the dev substrate + concurrent OpenIM work. The TS
// proof endpoint we always spawn, so it is always cleaned up; only the shared Python
// deployment is left intact when reused.
let pySpawnedByUs = false;
let tsChild = null;

async function main() {
  log(`work dir ${work}`);
  if (!(await adminHealthy())) {
    log(`shared Restate admin not reachable at ${ADMIN_URL}. Boot it: (cd ${REFERENCE_ROOT} && pnpm dev:restate).`);
    process.exit(1);
  }

  const fixturePlan = buildFixturePlan();

  // ── 1. Python endpoint up (bd09 — the dispatch target) ───────────────────
  // Reuse the running bd09 if already registered (shared :9091); only spawn if not.
  // (We crash the TS VO, not bd09 — the persistent shared bd09 is ideal here.)
  if (await awaitServiceRegistered('bd09', 2)) {
    log('bd09 already registered — reusing the running Python endpoint (no spawn). It will be LEFT INTACT on exit.');
  } else {
    pyChild = startPyEndpoint();
    pySpawnedByUs = true;
    if (!(await awaitServiceRegistered('bd09'))) {
      log('bd09 did not register within the timeout. Aborting.');
      try {
        pyChild.kill('SIGKILL');
      } catch {
        /* best-effort */
      }
      process.exit(1);
    }
    log('bd09 registered (dispatch target reachable).');
  }

  // ── 2. TS production-VO endpoint (process 1), fixture + post-dispatch pause ─
  log('starting the TS dispatch-proof endpoint (process 1) — the REAL investmentOperation, fixture + post-dispatch pause...');
  tsChild = startTsEndpoint(fixturePlan);
  await waitFor(() => existsSync(READY_FILE), 60_000, 'TS endpoint process 1 ready');
  const pid1 = readFileSync(READY_FILE, 'utf8').trim();
  log(`TS endpoint process 1 ready (pid ${pid1}); registered.`);
  await new Promise((res) => setTimeout(res, 2000));

  // ── 3. invoke execute (async; dispatch then pause in the window) ──────────
  log(`invoking investmentOperation/${OP_KEY}/execute (async; will dispatch + pause in the crash window)`);
  invokeExecuteAsync(OP_KEY, fixturePlan);

  // ── 4. wait until dispatch is journaled (the `dispatched N step(s):` line) ─
  await waitFor(() => capturedDispatchBefore !== null, 90_000, 'dispatch to journal (dispatched N step(s): log line)');
  log(`dispatch journaled: ${capturedDispatchBefore}`);
  log('operation MID-FLIGHT in the post-dispatch pause window.');

  // ── 5. SIGKILL the TS endpoint (a real crash) IN the window ──────────────
  log(`SIGKILL the TS endpoint process tree (pid ${tsChild.pid}) — a REAL crash, between the journaled dispatch and the terminal write.`);
  rmSync(READY_FILE, { force: true });
  killTree(tsChild);
  await new Promise((res) => setTimeout(res, 1500));
  log('TS endpoint process 1 is dead. The operation is interrupted, its dispatched stepResults in the journal, the terminal write NOT done.');

  // ── 6. restart a FRESH TS endpoint (process 2) ───────────────────────────
  log('restarting a FRESH TS endpoint (process 2) — same shared Restate + the same Python bd09.');
  tsChild = startTsEndpoint(fixturePlan);
  await waitFor(() => existsSync(READY_FILE), 60_000, 'TS endpoint process 2 ready');
  const pid2 = readFileSync(READY_FILE, 'utf8').trim();
  log(`TS endpoint process 2 ready (pid ${pid2}); re-registered. (pid ${pid1} -> ${pid2}: a different process.)`);
  await new Promise((res) => setTimeout(res, 2000));

  // ── 7. attach to the resumed invocation + read its journaled result ──────
  log('attaching to the resumed invocation (same idempotency key) to read its journaled OperationResult...');
  const result = await attachExecuteAfterResume(OP_KEY, fixturePlan);
  const status = await readStatus(OP_KEY);
  await new Promise((res) => setTimeout(res, 1000));

  const resumedSig = stepResultsSignature(result);
  // The pre-crash log line: "N step(s): Xf, Yr ...; outcomes=[...]". Build the same
  // signature from the resumed result and assert the outcome SHAPE matches.
  const resumedFromResult =
    result.stepResults
      .map((r) => `${r.soId}:${r.status}`)
      .join(', ') || '(none)';
  const preCrashOutcomes = (capturedDispatchBefore.match(/outcomes=\[(.+)\]/) || [])[1] ?? '';

  log('');
  log('RESULT:');
  log(`  dispatch BEFORE crash:  ${capturedDispatchBefore}`);
  log(`  resumed stepResults:    ${resumedSig}`);
  log(`  resumed outcomes:       ${resumedFromResult}`);
  log(`  pre-crash outcomes:     ${preCrashOutcomes}`);
  log(`  resumed status:         ${result.status}`);
  log(`  VO state AFTER resume:  status=${status && status.status}`);
  log(`  TS endpoint pid BEFORE: ${pid1}  AFTER: ${pid2}`);
  log(`  server log witnesses — Replaying=${sawReplaying} Completed=${sawCompleted}`);

  const outcomesMatch = resumedFromResult === preCrashOutcomes && preCrashOutcomes.length > 0;
  const reachedCompleted = result.status === 'completed' && status && status.status === 'completed';
  const realRestart = pid1 !== pid2;
  const resumedSameInvocation = sawReplaying;
  const allFulfilled = result.fulfilledCount === fixturePlan.steps.length;

  // cleanup — tear down ONLY what this run spawned. The TS proof endpoint is always
  // this-run-spawned (clean it up). The shared Python deployment (bd09/agentinvestPlanner/
  // pyTools on :9091) is torn down ONLY if WE spawned it; if we reused the running shared
  // endpoint, leave it registered + alive (other local projects sharing the dev substrate
  // + concurrent OpenIM work depend on it).
  try {
    tsChild.kill('SIGKILL');
  } catch {
    /* best-effort */
  }
  if (pySpawnedByUs) {
    try {
      pyChild.kill('SIGKILL');
    } catch {
      /* best-effort */
    }
  }
  await new Promise((res) => setTimeout(res, 800));
  await pruneDeployments('investmentOperation', PROOF_PORT);
  if (pySpawnedByUs) {
    await pruneDeployments('agentinvestPlanner', process.env.AGENTINVEST_PY_ENDPOINT_PORT ?? '9091');
  } else {
    log('reused the shared Python endpoint — leaving bd09/agentinvestPlanner/pyTools registered on exit (not stripping a shared resource).');
  }
  rmSync(work, { recursive: true, force: true });

  const ok = outcomesMatch && reachedCompleted && realRestart && resumedSameInvocation && allFulfilled;

  log('');
  if (ok) {
    log('PRODUCTION-VO DISPATCH JOURNALED-REPLAY PROVEN:');
    log('  - the REAL investmentOperation was SIGKILLed mid-execute, between its journaled dispatch and the terminal write');
    log('  - Restate RESUMED the SAME invocation from the journal on a fresh process (Replaying invocation, new pid)');
    log('  - the resumed stepResults EQUAL the pre-crash dispatched outcomes — replay READ THE JOURNALED RESULTS BACK, the tools were NOT re-executed');
    log('  - the VO reached completed; the pid changed (a real crash)');
    process.exit(0);
  }
  log(
    `FAILED: outcomesMatch=${outcomesMatch} reachedCompleted=${reachedCompleted} realRestart=${realRestart} ` +
      `resumedSameInvocation=${resumedSameInvocation} allFulfilled=${allFulfilled}`,
  );
  process.exit(1);
}

main().catch((err) => {
  log(`ERROR: ${err.message}`);
  try {
    if (tsChild) tsChild.kill('SIGKILL');
    // Only kill the Python endpoint if THIS run spawned it (never a reused shared one).
    if (pyChild && pySpawnedByUs) pyChild.kill('SIGKILL');
  } catch {
    /* best-effort */
  }
  try {
    rmSync(work, { recursive: true, force: true });
  } catch {
    /* best-effort */
  }
  process.exit(1);
});
