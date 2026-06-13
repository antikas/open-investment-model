#!/usr/bin/env node
/**
 * PRODUCTION-VO journaled-EXACTLY-ONCE crash-replay proof for the .plan() step
 * (the same production-shell crash pattern as the dispatch/full-chain proofs).
 *
 * This proves the load-bearing fiduciary-determinism property of the planning
 * step: the LLM's non-deterministic plan is journaled EXACTLY ONCE on the
 * PRODUCTION `investmentOperation` VO, so a crash+replay reads the recorded plan
 * back and does NOT re-invoke the model. The witness is an LLM-call-count
 * side-effect log (written by the Python planner): it must hold EXACTLY ONE line
 * across the whole crash-and-restart. A second line would mean replay re-called
 * the model — the determinism property broken.
 *
 * Run against the REAL `investmentOperation`, not a probe.
 *
 * Mechanism (extends shell-crash-proof.mjs):
 *   1. Start the PYTHON endpoint (binds agentinvestPlanner + bd09), with
 *      AGENTINVEST_LLM_CALL_LOG pointing at a shared file so the planner records
 *      each real model call. (One Python endpoint stays up across the whole proof —
 *      we crash the TS VO, not the planner; the planner records the ONE call the
 *      pre-crash plan step made.)
 *      Reuse-safe teardown: the SHARED Python deployment (:9091 — carrying
 *      bd09/agentinvestPlanner/navData/pyTools) is torn down ONLY if THIS run spawned
 *      it (pySpawnedByUs). If reused, it is LEFT REGISTERED — never strip a shared
 *      resource (other local projects sharing the dev substrate + concurrent OpenIM
 *      work depend on it). NEVER `wsl --shutdown`.
 *      NOTE: this proof's LLM-call-count instrument (AGENTINVEST_LLM_CALL_LOG) is only
 *      armed on an endpoint THIS run spawns; on a REUSE run the running shared planner
 *      records its call to a different log, so the at-plan precondition (callsAtPlan===1)
 *      surfaces a clear harness note and the proof spawns its own. Either way the shared
 *      deployment is never stripped.
 *   2. Start the TS shell-crash endpoint (the REAL investmentOperation) with the
 *      proof-only durable pause (AGENTINVEST_CRASH_PROOF_DELAY_MS) so execute
 *      pauses in the window between the journaled plan and the terminal write.
 *   3. Invoke investmentOperation/<key>/execute (idempotency key; fire-and-forget).
 *   4. Wait until the handler logs `journaled plan:` (the plan RPC has returned +
 *      been journaled; the operation is MID-FLIGHT in the pause window). Capture
 *      the LLM-call-log line count: it must be 1 (the plan step made one model call).
 *   5. SIGKILL the TS endpoint process tree (a real crash) in the window.
 *   6. Restart a FRESH TS endpoint (different pid); re-register.
 *   7. Re-POST the SAME idempotency key — Restate ATTACHES to the resumed
 *      invocation and returns its journaled OperationResult (the recorded plan).
 *   8. Assert: the LLM-call-log STILL holds exactly ONE line (replay did NOT
 *      re-call the model); the resumed plan equals the pre-crash plan; the VO
 *      reached `completed`; the TS pid changed; Restate logged Replaying.
 *
 * Run (from reference/, substrate up via `pnpm dev:restate`):
 *   node scripts/plan-crash-proof.mjs   (or: pnpm plan-crash)
 */
import { spawn, execFileSync } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
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

const CRASH_PROOF_DELAY_MS = process.env.AGENTINVEST_CRASH_PROOF_DELAY_MS ?? '12000';

// The LLM-call-count side-effect log — on the shared /mnt/d mount so BOTH the
// Python planner (in WSL2) and this controller (Windows) see the same file. The
// path lives under reference/ so it is gitignored-adjacent; we delete it at the end.
const LLM_CALL_LOG_WIN = path.join(REFERENCE_ROOT, `.llm-call-count-${Date.now()}.log`);

const work = mkdtempSync(path.join(tmpdir(), 'agentinvest-plan-crash-'));
const READY_FILE = path.join(work, 'ready');
const OP_KEY = `plancrash-${Date.now()}`;
const IDEMPOTENCY_KEY = `plan-crash-${Date.now()}`;

function log(line) {
  process.stderr.write(`[plan-crash] ${line}\n`);
}

/** WSL2 path for a Windows drive-lettered path. */
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

function llmCallLogCount() {
  if (!existsSync(LLM_CALL_LOG_WIN)) return 0;
  const txt = readFileSync(LLM_CALL_LOG_WIN, 'utf8');
  return txt.split(/\r?\n/).filter((l) => l.trim().length > 0).length;
}

// ── the Python endpoint (agentinvestPlanner + bd09) ─────────────────────────
function startPyEndpoint() {
  const llmLogWsl = toWsl(LLM_CALL_LOG_WIN);
  const env = { ...process.env, WSL_UTF8: '1', AGENTINVEST_LLM_CALL_LOG: llmLogWsl };
  let cmd;
  let args;
  if (isWin) {
    cmd = 'wsl';
    args = [
      '-d',
      WSL_DISTRO,
      '--',
      'bash',
      '-lc',
      `export AGENTINVEST_LLM_CALL_LOG='${llmLogWsl}'; ${wslPrelude()} && uv run python -m agentinvest_tools.endpoint`,
    ];
  } else {
    cmd = 'bash';
    args = [
      '-lc',
      `export AGENTINVEST_LLM_CALL_LOG='${LLM_CALL_LOG_WIN}'; export PATH="$HOME/.local/bin:$PATH" && cd ${REFERENCE_ROOT}/python && uv run python -m agentinvest_tools.endpoint`,
    ];
  }
  log('starting the PYTHON endpoint (agentinvestPlanner + bd09; AGENTINVEST_LLM_CALL_LOG set)...');
  const child = spawn(cmd, args, { stdio: 'inherit', env });
  return child;
}

async function awaitPlannerRegistered(timeoutSeconds = 90) {
  const deadline = Date.now() + timeoutSeconds * 1000;
  while (Date.now() < deadline) {
    try {
      const r = await fetch(`${ADMIN_URL}/services/agentinvestPlanner/openapi`, {
        signal: AbortSignal.timeout(3000),
      });
      if (r.ok) return true;
    } catch {
      /* retry */
    }
    await new Promise((res) => setTimeout(res, 1500));
  }
  return false;
}

// ── the TS production-VO endpoint (the REAL investmentOperation) ─────────────
let capturedPlanBefore = null;
let sawReplaying = false;
let sawCompleted = false;

function attachLogParsing(child) {
  const onChunk = (buf) => {
    const text = buf.toString();
    process.stderr.write(text);
    const m = text.match(/journaled plan: (.+)$/m);
    if (m && !capturedPlanBefore) capturedPlanBefore = m[1].trim();
    if (/Replaying invocation/.test(text)) sawReplaying = true;
    if (/Invocation completed successfully/.test(text)) sawCompleted = true;
  };
  child.stdout?.on('data', onChunk);
  child.stderr?.on('data', onChunk);
}

function startTsEndpoint() {
  const entry = path.join(TS_DIR, 'src', 'orchestrator', 'shell-crash-endpoint.ts');
  const child = spawn(process.execPath, ['--import', 'tsx', entry], {
    cwd: TS_DIR,
    stdio: ['ignore', 'pipe', 'pipe'],
    env: {
      ...process.env,
      SHELL_CRASH_READY_FILE: READY_FILE,
      AGENTINVEST_CRASH_PROOF_DELAY_MS: CRASH_PROOF_DELAY_MS,
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

function invokeExecuteAsync(key) {
  const controller = new AbortController();
  fetch(`${INGRESS_URL}/investmentOperation/${encodeURIComponent(key)}/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'idempotency-key': IDEMPOTENCY_KEY },
    body: JSON.stringify({ kind: 'plan-crash-proof', params: { task: 'Compute the time-weighted return for fund X over Q1 so I can compare the manager against the benchmark.' } }),
    signal: controller.signal,
  }).catch(() => undefined);
  return controller;
}

async function attachExecuteAfterResume(key) {
  const res = await fetch(`${INGRESS_URL}/investmentOperation/${encodeURIComponent(key)}/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'idempotency-key': IDEMPOTENCY_KEY },
    body: JSON.stringify({ kind: 'plan-crash-proof', params: { task: 'Compute the time-weighted return for fund X over Q1 so I can compare the manager against the benchmark.' } }),
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
        log(`pruned dead-port ${serviceName} deployment ${dep.id} (${dep.uri})`);
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

let pyChild = null;
// Did THIS run spawn the shared Python endpoint (bd09/agentinvestPlanner/navData/
// pyTools on :9091)? Only true if we started it; false if we REUSED an already-
// running shared endpoint. Gates ALL Python-side teardown: we only ever tear down
// what we started. Reusing and then stripping the shared deployment would disrupt
// other local projects sharing the dev substrate + concurrent OpenIM work.
// The TS proof endpoint we always spawn, so it is always cleaned up; only the shared
// Python deployment is left intact when reused.
let pySpawnedByUs = false;
let tsChild = null;

async function main() {
  log(`work dir ${work}`);
  log(`LLM-call-count log: ${LLM_CALL_LOG_WIN}`);
  writeFileSync(LLM_CALL_LOG_WIN, '');
  if (!(await adminHealthy())) {
    log(`shared Restate admin not reachable at ${ADMIN_URL}. Boot it: (cd ${REFERENCE_ROOT} && pnpm dev:restate).`);
    process.exit(1);
  }

  // ── 1. Python endpoint up (agentinvestPlanner + bd09), call-log armed ─────
  // Reuse the running shared planner if already registered (the shared :9091); only
  // spawn our own if not (reuse-safety — never strip a shared deployment we
  // did not spawn). On a REUSE run the running planner records to a different
  // call-log, so the at-plan precondition below surfaces that clearly.
  if (await awaitPlannerRegistered(2)) {
    log('agentinvestPlanner already registered — reusing the running shared Python endpoint (no spawn). LEFT REGISTERED on exit (the LLM-call-count instrument is not armed on a reused endpoint; the at-plan precondition surfaces it).');
  } else {
    pyChild = startPyEndpoint();
    pySpawnedByUs = true;
    if (!(await awaitPlannerRegistered())) {
      log('agentinvestPlanner did not register within the timeout. Aborting.');
      try {
        pyChild.kill('SIGKILL');
      } catch {
        /* best-effort */
      }
      process.exit(1);
    }
    log('agentinvestPlanner registered (planner reachable; LLM-call-count instrument armed).');
  }

  // ── 2. TS production-VO endpoint (process 1), with the proof pause ───────
  log('starting the TS production-VO endpoint (process 1) — binds the REAL investmentOperation...');
  tsChild = startTsEndpoint();
  await waitFor(() => existsSync(READY_FILE), 60_000, 'TS endpoint process 1 ready');
  const pid1 = readFileSync(READY_FILE, 'utf8').trim();
  log(`TS endpoint process 1 ready (pid ${pid1}); registered.`);
  await new Promise((res) => setTimeout(res, 2000));

  // ── 3. invoke execute (async; handler will plan then pause in the window) ─
  log(`invoking investmentOperation/${OP_KEY}/execute (async; will plan + pause in the crash window)`);
  invokeExecuteAsync(OP_KEY);

  // ── 4. wait until the plan is journaled (the `journaled plan:` log line) ──
  await waitFor(() => capturedPlanBefore !== null, 90_000, 'the plan to journal (journaled plan: log line)');
  const callsAtPlan = llmCallLogCount();
  log(`plan journaled: ${capturedPlanBefore}`);
  log(`LLM-call-count at plan time: ${callsAtPlan} (expected 1 — the one .plan() model call). Operation MID-FLIGHT in the pause window.`);

  // PRECONDITION (assert loudly, not a spurious atPlan=0 FAIL at the end): the
  // plan journaled, so the planner MUST have made exactly one model call and the
  // call-log MUST hold one line. A read of 0 here means our planner's call-log was
  // not the one that served this run — almost always a STALE Python endpoint
  // holding :9091 (an old process from a prior run) answered the planTask, so its
  // call went to a different/old log file and ours stayed empty. That is a harness
  // setup fault, NOT a determinism failure — surface it clearly so it is not read
  // as "replay re-called the model".
  if (callsAtPlan !== 1) {
    log('');
    log(`PRECONDITION FAILED: LLM-call-count at plan time is ${callsAtPlan}, expected 1.`);
    log('  The plan journaled but THIS run\'s LLM-call-log did not record the call.');
    log('  Most likely a STALE endpoint is holding port 9091 (an old agentinvestPlanner');
    log('  process from a previous run answered planTask against a different call-log).');
    log('  This is a harness/setup fault, not a determinism failure. Recover by killing');
    log('  the stale :9091 endpoint and restarting Restate via `pnpm dev:restate`');
    log('  (idempotent, leaves WSL up) — do NOT run `wsl --shutdown`. Then re-run.');
    try {
      tsChild.kill('SIGKILL');
    } catch {
      /* best-effort */
    }
    // Only kill the Python endpoint if THIS run spawned it (never a reused shared one).
    if (pySpawnedByUs) {
      try {
        pyChild.kill('SIGKILL');
      } catch {
        /* best-effort */
      }
    }
    rmSync(LLM_CALL_LOG_WIN, { force: true });
    rmSync(work, { recursive: true, force: true });
    process.exit(1);
  }

  // ── 5. SIGKILL the TS endpoint (a real crash) IN the window ──────────────
  log(`SIGKILL the TS endpoint process tree (pid ${tsChild.pid}) — a REAL crash, between the journaled plan and the terminal write.`);
  rmSync(READY_FILE, { force: true });
  killTree(tsChild);
  await new Promise((res) => setTimeout(res, 1500));
  log('TS endpoint process 1 is dead. The production operation is interrupted, its plan in the journal, the terminal write NOT done.');

  // ── 6. restart a FRESH TS endpoint (process 2) ───────────────────────────
  log('restarting a FRESH TS endpoint (process 2) — same shared Restate + the same Python planner.');
  tsChild = startTsEndpoint();
  await waitFor(() => existsSync(READY_FILE), 60_000, 'TS endpoint process 2 ready');
  const pid2 = readFileSync(READY_FILE, 'utf8').trim();
  log(`TS endpoint process 2 ready (pid ${pid2}); re-registered. (pid ${pid1} -> ${pid2}: a different process.)`);
  await new Promise((res) => setTimeout(res, 2000));

  // ── 7. attach to the resumed invocation + read its journaled result ──────
  log('attaching to the resumed invocation (same idempotency key) to read its journaled OperationResult...');
  const result = await attachExecuteAfterResume(OP_KEY);
  const status = await readStatus(OP_KEY);

  // give the replay a moment to fully settle, then re-read the call count
  await new Promise((res) => setTimeout(res, 1500));
  const callsAfter = llmCallLogCount();

  const resumedPlanSummary =
    result.plan && Array.isArray(result.plan.steps)
      ? `${result.plan.steps.length} step(s), soIds=[${result.plan.steps.map((s) => s.soId).join(', ')}], riskScore=${result.plan.riskScore}`
      : '(no plan!)';

  log('');
  log('RESULT:');
  log(`  journaled plan BEFORE crash:  ${capturedPlanBefore}`);
  log(`  resumed OperationResult.plan: ${resumedPlanSummary}`);
  log(`  resumed status: ${result.status}`);
  log(`  VO state (status handler) AFTER resume: status=${status && status.status}`);
  log(`  LLM-call-count: at plan time=${callsAtPlan}  after resume=${callsAfter}  (must BOTH be 1 — replay did NOT re-call the model)`);
  log(`  TS endpoint pid BEFORE: ${pid1}  AFTER: ${pid2}`);
  log(`  server log witnesses — Replaying=${sawReplaying} Completed=${sawCompleted}`);

  const llmCalledOnce = callsAtPlan === 1 && callsAfter === 1;
  const planMatches =
    `${result.plan.steps.length} step(s), soIds=[${result.plan.steps.map((s) => s.soId).join(', ')}], riskScore=${result.plan.riskScore}` ===
    capturedPlanBefore;
  const reachedCompleted = result.status === 'completed' && status && status.status === 'completed';
  const realRestart = pid1 !== pid2;
  const resumedSameInvocation = sawReplaying;

  const ok = llmCalledOnce && planMatches && reachedCompleted && realRestart && resumedSameInvocation;

  // cleanup — tear down ONLY what this run spawned. The TS proof endpoint is always
  // this-run-spawned (clean it up). The shared Python deployment (bd09/agentinvestPlanner/
  // navData/pyTools on :9091) is torn down ONLY if WE spawned it; if we reused the running
  // shared endpoint, leave it registered + alive (other local projects sharing the dev
  // substrate + concurrent OpenIM work depend on it).
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
  await pruneDeployments('investmentOperation', process.env.AGENTINVEST_SHELL_CRASH_PORT ?? '9096');
  if (pySpawnedByUs) {
    await pruneDeployments('agentinvestPlanner', process.env.AGENTINVEST_PY_ENDPOINT_PORT ?? '9091');
  } else {
    log('reused the shared Python endpoint — leaving bd09/agentinvestPlanner/navData/pyTools registered on exit (not stripping a shared resource).');
  }
  rmSync(LLM_CALL_LOG_WIN, { force: true });
  rmSync(work, { recursive: true, force: true });

  log('');
  if (ok) {
    log('PRODUCTION-VO JOURNALED-EXACTLY-ONCE CRASH-REPLAY PROVEN (.plan()):');
    log('  - the REAL investmentOperation was SIGKILLed mid-execute, between its journaled .plan() RPC and the terminal write');
    log('  - Restate RESUMED the SAME invocation from the journal on a fresh process (Replaying invocation, new pid)');
    log('  - the LLM-call-count stayed at 1 across the crash+restart — replay READ THE JOURNALED PLAN BACK, it did NOT re-invoke the model');
    log('  - the resumed plan EQUALS the pre-crash journaled plan; the VO reached completed; the pid changed (a real crash)');
    process.exit(0);
  }
  log(
    `FAILED: llmCalledOnce=${llmCalledOnce} (atPlan=${callsAtPlan} after=${callsAfter}) ` +
      `planMatches=${planMatches} reachedCompleted=${reachedCompleted} realRestart=${realRestart} ` +
      `resumedSameInvocation=${resumedSameInvocation}`,
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
    rmSync(LLM_CALL_LOG_WIN, { force: true });
    rmSync(work, { recursive: true, force: true });
  } catch {
    /* best-effort */
  }
  process.exit(1);
});
