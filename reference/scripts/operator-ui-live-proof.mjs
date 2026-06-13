#!/usr/bin/env node
/**
 * OPERATOR UI v0.1 LIVE PROOF — proves the two load-bearing surfaces work
 * against the DEPLOYED stack over synthetic data, NOT mocked. It exercises the EXACT
 * server-side data paths the Operator UI's pages use (the same admin + ingress calls
 * `operator-ui/src/lib/restate.ts` makes), driving a REAL `navCalculation` workflow
 * paused at the high-stakes approval gate:
 *
 *   APPROVALS QUEUE (load-bearing):
 *     1. force the gate to fire — submit a real NAV strike (riskScore 1.0 → pauses at
 *        the gate). This is a LIVE workflow paused awaiting a decision.
 *     2. the UI's data source — `POST {ingress}/approvalRegistryReader/list` — LISTS
 *        the pending approval (operationId, awakeable id, riskScore, summary, raised-at):
 *        the additive pending-approvals registry the gate's notify also records to. REAL,
 *        not a mock.
 *     3. APPROVE (the UI's action path): resolve the awakeable
 *        `POST {ingress}/restate/awakeables/{id}/resolve {"approved":true}` → the
 *        workflow PROCEEDS → completes (status=published); then mark the registry
 *        resolved → it LEAVES the pending list.
 *     4. REJECT (a second strike): resolve `{"approved":false,"reason":...}` → the
 *        workflow ABORTS (status=aborted, aborted-by-operator, NO publish record); it
 *        leaves the pending list.
 *
 *   OPERATIONS DASHBOARD (read-only):
 *     5. read each operation's recorded `status` over the ingress (the UI's Operations
 *        data source) — the published strike carries its publish record; both operations'
 *        recorded state is the audit trail the dashboard renders.
 *
 * Reuse-safe teardown: the SHARED Python deployment (:9091 — navData/bd09) is
 * torn down ONLY if THIS run spawned it (pySpawnedByUs). If reused (the usual case on
 * a dev workstation), it is LEFT REGISTERED — never strip a shared resource (other local
 * projects sharing the dev substrate + concurrent OpenIM work depend on it). The TS proof
 * endpoint (navCalculation + the registry) we always spawn, so it is always cleaned up.
 * NEVER `wsl --shutdown`.
 *
 * Run (from reference/, substrate up via `pnpm dev:restate`):
 *   node scripts/operator-ui-live-proof.mjs   (or: pnpm operator-ui-live)
 */
import { spawn, execFileSync } from 'node:child_process';
import { existsSync, mkdtempSync, rmSync } from 'node:fs';
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
const PROOF_PORT = process.env.OPERATOR_UI_PROOF_PORT ?? '9100';
const LONG_TIMEOUT = process.env.NAV_APPROVAL_TIMEOUT_MS ?? '600000';

function log(line) {
  process.stderr.write(`[operator-ui-proof] ${line}\n`);
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
  let cmd, args;
  if (isWin) {
    cmd = 'wsl';
    args = ['-d', WSL_DISTRO, '--', 'bash', '-lc', `${wslPrelude()} && uv run --group dbt python -m agentinvest_tools.endpoint`];
  } else {
    cmd = 'bash';
    args = ['-lc', `export PATH="$HOME/.local/bin:$PATH" && cd ${REFERENCE_ROOT}/python && uv run --group dbt python -m agentinvest_tools.endpoint`];
  }
  log('starting the PYTHON endpoint (navData marts-read — :9091)...');
  return spawn(cmd, args, { stdio: 'inherit', env });
}

function makeLogState() {
  return { awakeableByWorkflow: {}, lastAwakeable: null };
}

function attachLogParsing(child, state) {
  const onChunk = (buf) => {
    const text = buf.toString();
    process.stderr.write(text);
    // Capture the awakeable id the gate logs when it pauses (the operator's notification).
    const m = text.match(/awakeableId=(\S+)/);
    if (m) state.lastAwakeable = m[1].replace(/[.,]+$/, '');
  };
  child.stdout?.on('data', onChunk);
  child.stderr?.on('data', onChunk);
}

function startTsEndpoint(readyFile, state, approvalTimeoutMs = LONG_TIMEOUT) {
  const entry = path.join(TS_DIR, 'src', 'orchestrator', 'nav-workflow-proof-endpoint.ts');
  const child = spawn(process.execPath, ['--import', 'tsx', entry], {
    cwd: TS_DIR,
    stdio: ['ignore', 'pipe', 'pipe'],
    env: {
      ...process.env,
      AGENTINVEST_NAV_PROOF_PORT: String(PROOF_PORT),
      NAV_PROOF_READY_FILE: readyFile,
      AGENTINVEST_APPROVAL_TIMEOUT_MS: String(approvalTimeoutMs),
    },
  });
  attachLogParsing(child, state);
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
    await new Promise((r) => setTimeout(r, 200));
  }
  throw new Error(`timed out waiting for: ${label}`);
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
    await new Promise((r) => setTimeout(r, 1500));
  }
  return false;
}

async function adminHealthy() {
  try {
    const r = await fetch(`${ADMIN_URL}/health`, { signal: AbortSignal.timeout(2000) });
    return r.ok;
  } catch {
    return false;
  }
}

// ── The UI's server-side data paths (identical to operator-ui/src/lib/restate.ts) ──

/** The Approvals page data source: list pending + resolved approvals from the registry reader. */
async function uiListApprovals() {
  const res = await fetch(`${INGRESS_URL}/approvalRegistryReader/list`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: '{}',
    signal: AbortSignal.timeout(15_000),
  });
  if (!res.ok) throw new Error(`approvalRegistryReader/list failed ${res.status}: ${await res.text()}`);
  return res.json();
}

/** The Approvals action path: resolve the awakeable, then mark the registry resolved. */
async function uiDecide(operationId, awakeableId, approved, reason) {
  const res = await fetch(`${INGRESS_URL}/restate/awakeables/${encodeURIComponent(awakeableId)}/resolve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ approved, reason: reason ?? undefined }),
    signal: AbortSignal.timeout(15_000),
  });
  if (!res.ok) throw new Error(`resolve awakeable failed ${res.status}: ${await res.text()}`);
  await fetch(`${INGRESS_URL}/approvalRegistry/${encodeURIComponent(operationId)}/resolve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ decision: approved ? 'approved' : 'rejected' }),
    signal: AbortSignal.timeout(15_000),
  }).catch(() => undefined);
}

/** The Operations dashboard data source: read a workflow's recorded status. */
async function uiReadOperation(workflowId) {
  const res = await fetch(`${INGRESS_URL}/navCalculation/${encodeURIComponent(workflowId)}/status`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: '{}',
    signal: AbortSignal.timeout(15_000),
  });
  if (!res.ok) throw new Error(`status failed ${res.status}: ${await res.text()}`);
  return res.json();
}

/**
 * A RAW out-of-band resolve — exactly a CLI/admin operator resolving the awakeable on the
 * ingress, WITHOUT the UI's registry-mark. The gate's own resolve-mark plus the reader's
 * liveness-reconcile must make such an entry leave the queue anyway, even though the UI never
 * marked it. Mirrors `resolveAwakeable` in the gate proof. Returns the HTTP status (202 for a
 * dead/already-resolved awakeable too).
 */
async function rawResolveAwakeable(awakeableId, payload) {
  const res = await fetch(`${INGRESS_URL}/restate/awakeables/${encodeURIComponent(awakeableId)}/resolve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal: AbortSignal.timeout(15_000),
  });
  return { ok: res.ok, status: res.status };
}

/**
 * The UI's stale-row guard — mirrors `decideApproval`'s
 * status pre-check in operator-ui/src/lib/restate.ts: confirm the op is genuinely
 * suspended at the gate BEFORE resolving; refuse honestly (StaleApprovalError-shaped) and
 * record NOTHING if it is terminal/gone. Returns {recorded, observedStatus}.
 */
const LIVE_AT_GATE = new Set(['running', 'striking']);
async function uiDecideWithStaleGuard(workflowId, awakeableId, approved) {
  let observedStatus = undefined;
  try {
    const state = await uiReadOperation(workflowId);
    observedStatus = state && typeof state.status === 'string' ? state.status : null;
  } catch {
    observedStatus = undefined; // transient — treat as live (do not block a genuine decision)
  }
  if (observedStatus !== undefined && !LIVE_AT_GATE.has(observedStatus ?? '')) {
    // Stale row — record NO decision (the UI surfaces "no longer pending").
    return { recorded: false, observedStatus };
  }
  await uiDecide(workflowId, awakeableId, approved, null);
  return { recorded: true, observedStatus };
}

function submitRunAsync(workflowId, fundId) {
  fetch(`${INGRESS_URL}/navCalculation/${encodeURIComponent(workflowId)}/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ fundId }),
  }).catch(() => undefined);
}

async function attachRun(workflowId, timeoutMs = 90_000) {
  const res = await fetch(
    `${INGRESS_URL}/restate/workflow/navCalculation/${encodeURIComponent(workflowId)}/attach`,
    { method: 'GET', signal: AbortSignal.timeout(timeoutMs) },
  );
  return { ok: res.ok, status: res.status };
}

/**
 * Clear any stale dev-state pending entries so
 * the proof starts from a clean queue. Reads the shared index via the ingress reader, then
 * replaces each per-op `entry` VO + the shared `__index__` with empty via the admin
 * modify-state endpoint. Same mechanism as scripts/clear-approval-registry-state.mjs.
 */
async function clearStaleRegistryState() {
  let index = [];
  try {
    const r = await fetch(`${INGRESS_URL}/approvalRegistry/__index__/readIndex`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
      signal: AbortSignal.timeout(15_000),
    });
    if (r.ok) index = (await r.json()) ?? [];
  } catch {
    /* none */
  }
  const clearOne = async (objectKey) => {
    await fetch(`${ADMIN_URL}/services/approvalRegistry/state`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ object_key: objectKey, new_state: {} }),
      signal: AbortSignal.timeout(10_000),
    }).catch(() => undefined);
  };
  for (const operationId of index) await clearOne(operationId);
  await clearOne('__index__');
  log(`cleared ${index.length} pre-fold stale pending entr${index.length === 1 ? 'y' : 'ies'} + the shared index (clean start).`);
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
        log(`pruned operator-ui-proof ${serviceName} deployment ${dep.id} (${dep.uri})`);
      }
    }
  } catch {
    /* best-effort */
  }
}

const work = mkdtempSync(path.join(tmpdir(), 'agentinvest-operatorui-'));
let pyChild = null;
let pySpawnedByUs = false;
let tsChild = null;

/** Fire a real NAV strike, wait for the gate pause, return the {workflowId, awakeableId, operationId}. */
async function fireGate(fundId, state) {
  const workflowId = `opui-${fundId}-${Date.now()}`;
  state.lastAwakeable = null;
  log(`submitting navCalculation/${workflowId}/run (fund ${fundId}) — will strike then PAUSE at the gate.`);
  submitRunAsync(workflowId, fundId);
  await waitFor(() => state.lastAwakeable !== null, 60_000, `${fundId}: gate to PAUSE`);
  const awakeableId = state.lastAwakeable;
  log(`PAUSED — workflowId=${workflowId} awakeableId=${awakeableId} (a live workflow awaiting an operator decision).`);
  // The registry write is FIRE-AND-FORGET (it must NOT block the gate), so there is a
  // small lag between the pause and the entry appearing in the pending list. Wait for
  // the UI's data source to reflect it before asserting — this is the UI's own list call.
  await waitFor(
    async () => {
      const list = await uiListApprovals();
      return list.pending.some((p) => p.operationId === workflowId);
    },
    20_000,
    `${workflowId}: registry to reflect the pending approval`,
  );
  return { workflowId, awakeableId };
}

async function main() {
  log(`work dir ${work}`);
  if (!(await adminHealthy())) {
    log(`shared Restate admin not reachable at ${ADMIN_URL}. Boot it: (cd ${REFERENCE_ROOT} && pnpm dev:restate).`);
    process.exit(1);
  }

  // navData up (the marts-read seam the NAV workflow needs). Reuse the shared :9091 if
  // registered; only spawn if not (reuse-safety).
  if (await awaitServiceRegistered('navData', 5)) {
    log('navData already registered — reusing the shared Python endpoint (no spawn). LEFT INTACT on exit (shared).');
  } else {
    pyChild = startPyEndpoint();
    pySpawnedByUs = true;
    if (!(await awaitServiceRegistered('navData'))) {
      log('navData did not register within the timeout. Aborting.');
      try { pyChild.kill('SIGKILL'); } catch { /* best-effort */ }
      process.exit(1);
    }
    log('navData registered (marts-read seam reachable).');
  }

  // Spawn the TS proof endpoint (navCalculation + the additive approvalRegistry + reader).
  const state = makeLogState();
  const readyFile = path.join(work, 'ready');
  tsChild = startTsEndpoint(readyFile, state);
  await waitFor(() => existsSync(readyFile), 60_000, 'TS proof endpoint ready');
  await new Promise((r) => setTimeout(r, 1500));
  if (!(await awaitServiceRegistered('approvalRegistryReader', 30))) {
    log('approvalRegistryReader did not register — aborting.');
    killTree(tsChild);
    process.exit(1);
  }
  log('TS proof endpoint up: navCalculation + approvalRegistry + approvalRegistryReader registered.');

  // Clear the pre-fold stale dev-state pending entries so the queue starts clean (and the
  // liveness-reconcile is not weighed down by a long-stale index). Deliverable #5.
  await clearStaleRegistryState();

  const results = {};

  // ── APPROVE FLOW (load-bearing) ───────────────────────────────────────────
  log('');
  log('──── APPROVALS QUEUE: APPROVE a real paused workflow ────');
  const a = await fireGate('PF-0001', state);
  // The UI's data source LISTS the pending approval (REAL, not a mock).
  let approvals = await uiListApprovals();
  const listedPending = approvals.pending.find((p) => p.operationId === a.workflowId);
  log(`UI Approvals list — pending=${approvals.pending.length}; this workflow listed=${!!listedPending}.`);
  if (listedPending) {
    log(`  ROW: operation=${listedPending.operationId} risk=${listedPending.riskScore} ` +
      `awakeable=${listedPending.awakeableId} origin=${listedPending.origin} summary="${listedPending.summary}".`);
  }
  // APPROVE via the UI action path (resolve the awakeable + mark the registry resolved).
  await uiDecide(a.workflowId, a.awakeableId, true, null);
  const approveTerminal = await attachRun(a.workflowId);
  await new Promise((r) => setTimeout(r, 800));
  const approveState = await uiReadOperation(a.workflowId);
  // It must have LEFT the pending list and PUBLISHED.
  approvals = await uiListApprovals();
  const stillPending = approvals.pending.some((p) => p.operationId === a.workflowId);
  log(`after APPROVE: HTTP ${approveTerminal.status}; status=${approveState?.status}; ` +
    `published=${approveState?.publishRecord ? 'yes' : 'no'}; leftPendingQueue=${!stillPending}.`);
  results.approve =
    !!listedPending && approveTerminal.ok && approveState?.status === 'published' &&
    !!approveState?.publishRecord && !stillPending;
  log(`APPROVE flow: ${results.approve ? 'PASS' : 'FAIL'}`);

  // ── REJECT FLOW ───────────────────────────────────────────────────────────
  log('');
  log('──── APPROVALS QUEUE: REJECT a real paused workflow (no publish) ────');
  const r = await fireGate('PF-0003', state);
  approvals = await uiListApprovals();
  const listedReject = approvals.pending.find((p) => p.operationId === r.workflowId);
  log(`UI Approvals list — pending=${approvals.pending.length}; this workflow listed=${!!listedReject}.`);
  await uiDecide(r.workflowId, r.awakeableId, false, 'operator rejects the high-stakes NAV publish (UI proof)');
  const rejectTerminal = await attachRun(r.workflowId);
  await new Promise((x) => setTimeout(x, 800));
  const rejectState = await uiReadOperation(r.workflowId);
  approvals = await uiListApprovals();
  const stillPendingR = approvals.pending.some((p) => p.operationId === r.workflowId);
  log(`after REJECT: HTTP ${rejectTerminal.status} (clean 4xx=${!rejectTerminal.ok && rejectTerminal.status >= 400 && rejectTerminal.status < 500}); ` +
    `status=${rejectState?.status}; abort=${JSON.stringify(rejectState?.abort)}; ` +
    `publishRecord=${rejectState?.publishRecord ? 'PRESENT(!)' : 'null'}; leftPendingQueue=${!stillPendingR}.`);
  results.reject =
    !!listedReject && !rejectTerminal.ok && rejectTerminal.status >= 400 && rejectTerminal.status < 500 &&
    rejectState?.status === 'aborted' && rejectState?.abort?.kind === 'aborted-by-operator' &&
    !rejectState?.publishRecord && !stillPendingR;
  log(`REJECT flow: ${results.reject ? 'PASS' : 'FAIL'}`);

  // ── CLI / OUT-OF-BAND RESOLVE LEAVES THE QUEUE ──
  // A CLI/raw resolve never touches the UI's registry mark, so the gate's own resolve-mark
  // (the gate marks the entry on the await-completes path) + the reader liveness-reconcile
  // are what make a RAW resolve (no UI mark) leave the pending queue.
  log('');
  log('──── APPROVALS QUEUE: a CLI / OUT-OF-BAND resolve LEAVES the queue (no UI mark) ────');
  const cli = await fireGate('PF-0001', state);
  approvals = await uiListApprovals();
  const listedCli = approvals.pending.some((p) => p.operationId === cli.workflowId);
  log(`UI Approvals list — this workflow listed pending=${listedCli}.`);
  // Resolve the awakeable RAW (as a CLI operator would), WITHOUT the UI's registry mark.
  const cliResolve = await rawResolveAwakeable(cli.awakeableId, { approved: true });
  const cliTerminal = await attachRun(cli.workflowId);
  await new Promise((x) => setTimeout(x, 1000));
  const cliState = await uiReadOperation(cli.workflowId);
  approvals = await uiListApprovals();
  const stillPendingCli = approvals.pending.some((p) => p.operationId === cli.workflowId);
  log(`after RAW resolve (HTTP ${cliResolve.status}): workflow status=${cliState?.status}; ` +
    `leftPendingQueue=${!stillPendingCli} (gate resolve-mark + liveness-reconcile, NOT a UI mark).`);
  results.cliResolveLeaves = !!listedCli && cliState?.status === 'published' && !stillPendingCli;
  log(`CLI/OUT-OF-BAND resolve leaves the queue: ${results.cliResolveLeaves ? 'PASS' : 'FAIL'}`);

  // ── STALE ROW: acting on an already-resolved row records NO false approved ──
  // The rejected workflow `r` is now terminal (aborted). Its awakeable is dead. Clicking
  // Approve on a dead awakeable returns 202 but must NOT record a phantom `approved` audit:
  // the UI stale-row guard confirms the op is no longer suspended and records NOTHING.
  log('');
  log('──── APPROVALS QUEUE: a STALE row records NO false approved ────');
  const beforeResolvedCount = (await uiListApprovals()).resolved.length;
  const staleDecision = await uiDecideWithStaleGuard(r.workflowId, r.awakeableId, true);
  await new Promise((x) => setTimeout(x, 600));
  const staleState = await uiReadOperation(r.workflowId);
  const afterResolvedCount = (await uiListApprovals()).resolved.length;
  log(`stale-row Approve attempt: recorded=${staleDecision.recorded} ` +
    `observedStatus=${staleDecision.observedStatus} (refused honestly = ${!staleDecision.recorded}).`);
  log(`the op stayed aborted (no phantom approve): status=${staleState?.status}; ` +
    `abort=${staleState?.abort?.kind}; publishRecord=${staleState?.publishRecord ? 'PRESENT(!)' : 'null'}.`);
  // No decision recorded; the op stays aborted-by-operator with no publish; no new resolved
  // row fabricated as approved for this terminal op.
  results.staleNoFalseApproved =
    staleDecision.recorded === false &&
    staleState?.status === 'aborted' &&
    staleState?.abort?.kind === 'aborted-by-operator' &&
    !staleState?.publishRecord &&
    afterResolvedCount === beforeResolvedCount;
  log(`STALE row records no false approved: ${results.staleNoFalseApproved ? 'PASS' : 'FAIL'}`);

  // ── TIMED-OUT approval LEAVES the queue ─────────────────────────────────────
  // Restart the endpoint with a SHORT approval timeout so a real gated workflow times out;
  // its registry entry must leave the pending queue (the gate's timeout path resolve-mark +
  // the liveness-reconcile against the now-aborted op).
  log('');
  log('──── APPROVALS QUEUE: a TIMED-OUT approval LEAVES the queue ────');
  const SHORT_TIMEOUT = process.env.NAV_APPROVAL_SHORT_TIMEOUT_MS ?? '8000';
  killTree(tsChild);
  tsChild = null;
  await new Promise((x) => setTimeout(x, 800));
  const readyFile2 = path.join(work, 'ready-timeout');
  const stateT = makeLogState();
  tsChild = startTsEndpoint(readyFile2, stateT, SHORT_TIMEOUT);
  await waitFor(() => existsSync(readyFile2), 60_000, 'TS proof endpoint (short-timeout) ready');
  await new Promise((x) => setTimeout(x, 1500));
  if (!(await awaitServiceRegistered('approvalRegistryReader', 30))) {
    log('approvalRegistryReader did not re-register (short-timeout endpoint) — failing the timeout flow.');
    results.timeoutLeaves = false;
  } else {
    const t = await fireGate('PF-0001', stateT);
    approvals = await uiListApprovals();
    const listedTimeout = approvals.pending.some((p) => p.operationId === t.workflowId);
    log(`UI Approvals list — this workflow listed pending=${listedTimeout}; NOT resolving (let it time out).`);
    // Do NOT resolve — let the short durable timeout fire; attach picks up the terminal abort.
    const timeoutTerminal = await attachRun(t.workflowId);
    await new Promise((x) => setTimeout(x, 1200));
    const timeoutState = await uiReadOperation(t.workflowId);
    approvals = await uiListApprovals();
    const stillPendingT = approvals.pending.some((p) => p.operationId === t.workflowId);
    log(`after TIMEOUT (HTTP ${timeoutTerminal.status}, clean 4xx=${!timeoutTerminal.ok && timeoutTerminal.status >= 400 && timeoutTerminal.status < 500}): ` +
      `status=${timeoutState?.status}; abort=${timeoutState?.abort?.kind}; leftPendingQueue=${!stillPendingT}.`);
    results.timeoutLeaves =
      !!listedTimeout && timeoutState?.status === 'aborted' &&
      timeoutState?.abort?.kind === 'aborted-by-timeout' && !stillPendingT;
  }
  log(`TIMED-OUT approval leaves the queue: ${results.timeoutLeaves ? 'PASS' : 'FAIL'}`);

  // ── OPERATIONS DASHBOARD (read-only) ──────────────────────────────────────
  log('');
  log('──── OPERATIONS DASHBOARD: read the live journal + audit record ────');
  // The dashboard reads each operation's recorded state. The approved strike carries a
  // publish record (the audit trail); the rejected one carries the abort trace.
  const opPublished = await uiReadOperation(a.workflowId);
  const opAborted = await uiReadOperation(r.workflowId);
  const pubRec = opPublished?.publishRecord;
  log(`Operations row 1: ${a.workflowId} status=${opPublished?.status} ` +
    `nav=${pubRec?.navUsd} fund=${pubRec?.fundName} approvedAwakeable=${pubRec?.approvedAwakeableId}.`);
  log(`Operations row 2: ${r.workflowId} status=${opAborted?.status} abort=${opAborted?.abort?.kind}.`);
  results.operations =
    opPublished?.status === 'published' && !!pubRec?.navUsd &&
    Array.isArray(opPublished?.checkpoints) && opPublished.checkpoints.length === 4 &&
    opAborted?.status === 'aborted';
  log(`OPERATIONS dashboard: ${results.operations ? 'PASS' : 'FAIL'} (published strike's 4 step checkpoints + publish record rendered; aborted strike's state rendered).`);

  // ── Teardown (reuse-safe) ─────────────────────────────────────────────────
  killTree(tsChild);
  tsChild = null;
  await new Promise((x) => setTimeout(x, 600));
  await pruneDeployments('navCalculation', PROOF_PORT);
  await pruneDeployments('approvalRegistryReader', PROOF_PORT);
  if (pySpawnedByUs) {
    try { pyChild.kill('SIGKILL'); } catch { /* best-effort */ }
    // On Windows the SIGKILL hits the `wsl` parent, not the in-WSL `uv run python`
    // child (the signal does not cross the WSL boundary) — pkill it in-WSL too so the
    // endpoint process does not linger (it is harmless once deregistered, but tidy).
    if (isWin) {
      try {
        execFileSync('wsl', ['-d', WSL_DISTRO, '--', 'pkill', '-9', '-f', 'agentinvest_tools.endpoint'], {
          stdio: 'ignore',
        });
      } catch { /* best-effort */ }
    }
    await new Promise((x) => setTimeout(x, 600));
    await pruneDeployments('navData', process.env.AGENTINVEST_PY_ENDPOINT_PORT ?? '9091');
  } else {
    log('reused the shared Python endpoint — leaving navData/bd09 registered on exit (shared).');
  }
  rmSync(work, { recursive: true, force: true });

  const allPass =
    results.approve && results.reject && results.cliResolveLeaves && results.staleNoFalseApproved &&
    results.timeoutLeaves && results.operations;
  log('');
  log('SUMMARY:');
  log(`  APPROVALS — list a real pending approval, APPROVE → workflow proceeds/completes : ${results.approve ? 'PASS' : 'FAIL'}`);
  log(`  APPROVALS — REJECT → workflow aborts (aborted-by-operator), NO publish          : ${results.reject ? 'PASS' : 'FAIL'}`);
  log(`  APPROVALS — CLI/OUT-OF-BAND resolve LEAVES the queue (no UI mark)                 : ${results.cliResolveLeaves ? 'PASS' : 'FAIL'}`);
  log(`  APPROVALS — STALE row records NO false approved (refused honestly)                : ${results.staleNoFalseApproved ? 'PASS' : 'FAIL'}`);
  log(`  APPROVALS — TIMED-OUT approval LEAVES the queue                                  : ${results.timeoutLeaves ? 'PASS' : 'FAIL'}`);
  log(`  OPERATIONS — read the live journal + the publish/audit record                   : ${results.operations ? 'PASS' : 'FAIL'}`);
  log('');
  if (allPass) {
    log('OPERATOR UI v0.1 surfaces PROVEN LIVE against the deployed stack: the Approvals queue lists a REAL');
    log('paused workflow and approve→proceeds / reject→aborts (no publish) by resolving the awakeable on the ingress; a');
    log('CLI/out-of-band-resolved AND a timed-out approval each LEAVE the pending queue, and a STALE row records no false');
    log('approved (the registry is true to the world). The Operations dashboard reads the');
    log('live journal + audit record. Synthetic data; the gate pause/resolve/timeout behaviour UNCHANGED (additive marks).');
    process.exit(0);
  }
  log('FAILED — see the per-flow diagnostics above.');
  process.exit(1);
}

main().catch((err) => {
  log(`ERROR: ${err.message}`);
  try {
    if (tsChild) killTree(tsChild);
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
