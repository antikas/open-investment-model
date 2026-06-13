#!/usr/bin/env node
/**
 * End-to-end proof for the `NavCalculationWorkflow` — the production workflow
 * exercised over synthetic data: the multi-step journaled NAV strike with the high-stakes
 * approval gate at the irreversible PUBLISH step. The same patterns as the approval-gate
 * proof and the production crash-replay proofs.
 *
 * What it exercises, ALL on the REAL `navCalculation` workflow (reading the actual
 * marts via the `navData` Python service — NO LLM, deterministic):
 *
 *   (d) GREEN E2E + GENUINE CROSS-MART §A1 RECONCILE — strike the NAV for each real seed fund
 *       (PF-0001/2/3), approve at the gate → publish. The workflow rolls the fund's gross up
 *       INDEPENDENTLY from `mart_portfolio_holdings` (load-positions) and reconciles it against
 *       `mart_fund_nav.gross_market_value` (two marts, two SQL paths — a falsifiable check, not
 *       X==X); then NAV = gross + accruals − fees ties to the mart's published `nav_usd` (the
 *       §A1 identity, dbt-enforced upstream). The struck NAV reconciles to `mart_fund_nav`.
 *   (g) PAST-AS-OF REFUSED ON THE WIRE — a past `navKnowledgeDate` to `navData` over the ingress
 *       returns the 422 refusal (NOT a current NAV) — the honest boundary holds end-to-end,
 *       refused on the wire.
 *   (b) THE GATE AT PUBLISH — APPROVE → publishes (a publish record, status=published);
 *       REJECT → terminal abort ("aborted-by-operator", status=aborted), NO publish record
 *       (the gate precedes publish — no half-published NAV).
 *   (c) CRASH MID-STEP RECOVERS — the class:
 *         · crash mid-gate-PAUSE → resume STILL-AWAITING (the awakeable id stable, NOT
 *           re-prompted), then approve → publishes (the durable pause survived the crash);
 *         · crash AFTER PUBLISH (the publish-exactly-once case) → on resume the journaled
 *           publish record is READ BACK, the publish step is NOT re-run (the published NAV is
 *           byte-identical, struckAt unchanged — exactly-once).
 *
 * The gate is resolved exactly as an operator would (no Operator UI): the Restate ingress
 * awakeable API — `POST {ingress}/restate/awakeables/{id}/resolve|reject`. The awakeable id is
 * read from the journaled notify the handler logs (the operator's "notification").
 *
 * The workflow is invoked over the ingress as a workflow submit:
 * `POST {ingress}/navCalculation/{workflowId}/run`; its state via the shared `status` handler:
 * `POST {ingress}/navCalculation/{workflowId}/status`.
 *
 * Reuse-safe teardown: the SHARED Python deployment (:9091 — now carrying
 * bd09/agentinvestPlanner/pyTools/navData) is torn down ONLY if THIS run spawned it
 * (pySpawnedByUs). If reused, it is LEFT REGISTERED — never strip a shared resource (other local
 * projects sharing the dev substrate + concurrent OpenIM work depend on it). NEVER `wsl --shutdown`.
 *
 * Run (from reference/, substrate up via `pnpm dev:restate`):
 *   node scripts/nav-workflow-proof.mjs   (or: pnpm nav-workflow)
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

const PROOF_PORT = process.env.NAV_PROOF_PORT ?? '9099';
// The gate fires unconditionally (publish is high-stakes by declaration, riskScore 1.0). A
// LONG approval timeout so the durable timer does NOT fire during a crash+restart window.
const LONG_TIMEOUT = process.env.NAV_APPROVAL_TIMEOUT_MS ?? '600000';
// The three real seed funds (verified against mart_fund_nav).
const SEED_FUNDS = ['PF-0001', 'PF-0002', 'PF-0003'];

function log(line) {
  process.stderr.write(`[nav-workflow] ${line}\n`);
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
    args = ['-d', WSL_DISTRO, '--', 'bash', '-lc', `${wslPrelude()} && uv run --group dbt python -m agentinvest_tools.endpoint`];
  } else {
    cmd = 'bash';
    args = ['-lc', `export PATH="$HOME/.local/bin:$PATH" && cd ${REFERENCE_ROOT}/python && uv run --group dbt python -m agentinvest_tools.endpoint`];
  }
  log('starting the PYTHON endpoint (navData marts-read + bd09 — :9091)...');
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

/** Per-TS-endpoint log state — reset between processes. */
function makeLogState() {
  return {
    awakeableId: null,
    sawPausing: false,
    sawReplaying: false,
    sawPublished: false,
    notifyCount: 0,
    publishCount: 0,
    prePublishPause: false,
  };
}

function attachLogParsing(child, state) {
  const onChunk = (buf) => {
    const text = buf.toString();
    process.stderr.write(text);
    const m = text.match(/awakeableId=(\S+)/);
    if (m && !state.awakeableId) state.awakeableId = m[1].replace(/[.,]+$/, '');
    if (/PAUSING for operator approval/.test(text)) state.sawPausing = true;
    const notifies = text.match(/OPERATOR APPROVAL REQUIRED/g);
    if (notifies) state.notifyCount += notifies.length;
    // The PUBLISH step logs `PUBLISH (exactly-once): NAV ... struck + journaled` — count
    // emissions so the crash-after-publish flow can assert publish is NOT re-run on resume.
    const publishes = text.match(/PUBLISH \(exactly-once\)/g);
    if (publishes) state.publishCount += publishes.length;
    if (/crash window between the approved/.test(text)) state.prePublishPause = true;
    if (/Replaying invocation/.test(text)) state.sawReplaying = true;
    if (/STEP roll-up.*RECONCILES/.test(text)) state.sawReconcile = true;
  };
  child.stdout?.on('data', onChunk);
  child.stderr?.on('data', onChunk);
}

function startTsEndpoint(readyFile, state, extraEnv = {}) {
  const entry = path.join(TS_DIR, 'src', 'orchestrator', 'nav-workflow-proof-endpoint.ts');
  const child = spawn(process.execPath, ['--import', 'tsx', entry], {
    cwd: TS_DIR,
    stdio: ['ignore', 'pipe', 'pipe'],
    env: {
      ...process.env,
      AGENTINVEST_NAV_PROOF_PORT: String(PROOF_PORT),
      NAV_PROOF_READY_FILE: readyFile,
      AGENTINVEST_APPROVAL_TIMEOUT_MS: LONG_TIMEOUT,
      ...extraEnv,
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
    await new Promise((res) => setTimeout(res, 200));
  }
  throw new Error(`timed out waiting for: ${label}`);
}

/** Fire-and-forget submit of the workflow run (it pauses at the gate; we don't await). */
function submitRunAsync(workflowId, fundId) {
  fetch(`${INGRESS_URL}/navCalculation/${encodeURIComponent(workflowId)}/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ fundId }),
  }).catch(() => undefined);
}

/**
 * ATTACH to a (submitted/resumed) workflow run via Restate's workflow attach endpoint —
 * `GET {ingress}/restate/workflow/{name}/{key}/attach` — which blocks until the run finishes
 * and returns its OUTPUT (200) or the terminal error (4xx). Distinct from re-POSTing `/run`
 * (which 409s — a workflow is one-shot per key, so a second submit conflicts). This is the
 * correct way to await an already-submitted workflow's result.
 */
async function attachRun(workflowId, _fundId, timeoutMs = 90_000) {
  const res = await fetch(
    `${INGRESS_URL}/restate/workflow/navCalculation/${encodeURIComponent(workflowId)}/attach`,
    { method: 'GET', signal: AbortSignal.timeout(timeoutMs) },
  );
  const text = await res.text();
  let json = null;
  try {
    json = JSON.parse(text);
  } catch {
    /* terminal error bodies are not JSON */
  }
  return { ok: res.ok, status: res.status, body: text, json };
}

async function readStatus(workflowId) {
  const res = await fetch(`${INGRESS_URL}/navCalculation/${encodeURIComponent(workflowId)}/status`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: '{}',
    signal: AbortSignal.timeout(15_000),
  });
  if (!res.ok) throw new Error(`status failed ${res.status}: ${await res.text()}`);
  return res.json();
}

/** Resolve an awakeable via the Restate ingress — exactly how a CLI/admin operator would. */
async function resolveAwakeable(awakeableId, payload) {
  const res = await fetch(`${INGRESS_URL}/restate/awakeables/${encodeURIComponent(awakeableId)}/resolve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal: AbortSignal.timeout(15_000),
  });
  if (!res.ok) throw new Error(`resolve awakeable failed ${res.status}: ${await res.text()}`);
  log(`resolved awakeable ${awakeableId} with ${JSON.stringify(payload)} (via the ingress — the operator path).`);
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
        log(`pruned nav-proof ${serviceName} deployment ${dep.id} (${dep.uri})`);
      }
    }
  } catch {
    /* best-effort */
  }
}

/** Read the published NAV components for a fund from `mart_fund_nav` (a read-back of the same row). */
async function readMartNav(fundId) {
  // Read via the navData service over the ingress — a read-back of the mart's nav_usd. (The
  // GENUINE independent check is the workflow's cross-mart reconcile inside roll-up: holdings
  // mart gross == NAV mart gross; this read-back confirms the struck NAV == the mart's nav_usd.)
  const res = await fetch(`${INGRESS_URL}/navData/getFundNavComponents`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ fundId }),
    signal: AbortSignal.timeout(20_000),
  });
  if (!res.ok) throw new Error(`navData read failed ${res.status}: ${await res.text()}`);
  return res.json();
}

/**
 * PAST-AS-OF REFUSED ON THE WIRE (g). A past `navKnowledgeDate` to
 * `navData/getFundNavComponents` over the ingress must return a 422 refusal (a TerminalError),
 * NOT a current NAV with HTTP 200. Drives the EXACT RPC the workflow makes, on the wire — a unit
 * test alone does not walk that radius.
 */
async function runPastAsOfRefusedOnTheWire(fundId) {
  log('');
  log(`──── FLOW: PAST-AS-OF refused on the wire (g) (${fundId}) ────`);
  // Baseline: a current strike (no date) succeeds (HTTP 200).
  const current = await fetch(`${INGRESS_URL}/navData/getFundNavComponents`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ fundId }),
    signal: AbortSignal.timeout(20_000),
  });
  const currentOk = current.ok;
  // A past date must now be REFUSED (422), not silently returned as a current NAV.
  const past = await fetch(`${INGRESS_URL}/navData/getFundNavComponents`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ fundId, navKnowledgeDate: '2020-01-01' }),
    signal: AbortSignal.timeout(20_000),
  });
  const pastBody = await past.text();
  const refused = past.status === 422 && /past-as-of/i.test(pastBody);
  log(
    `current(no date)=HTTP ${current.status}; past(2020-01-01)=HTTP ${past.status} ` +
      `(refused=${refused}; ${refused ? 'past-as-of bound HOLDS on the wire' : 'LEAK — current NAV returned!'}).`,
  );
  const pass = currentOk && refused;
  if (!pass) {
    log(`PAST-AS-OF-WIRE(${fundId}) FAILED: currentOk=${currentOk} pastStatus=${past.status} refused=${refused}`);
  } else {
    log(`PAST-AS-OF-WIRE(${fundId}) PASS: current strike 200; past date → 422 refusal (NOT a current NAV). Bound holds on the wire.`);
  }
  return pass;
}

const work = mkdtempSync(path.join(tmpdir(), 'agentinvest-navwf-'));
let pyChild = null;
// Did THIS run spawn the shared Python endpoint (:9091)? Gates ALL Python-side teardown —
// never strip a shared deployment we did not spawn (other local projects sharing
// the dev substrate + concurrent OpenIM work depend on it). The TS proof endpoint we always
// spawn, so it is always cleaned up.
let pySpawnedByUs = false;
let tsChild = null;

/**
 * GREEN E2E + §A1 RECONCILE + the gate-APPROVE path, for one fund: submit, wait for the gate
 * PAUSE, approve via the ingress, attach for the published result, assert status=published and
 * the struck NAV reconciles to the mart's nav_usd to the penny.
 */
async function runApprovePublishReconcile(fundId) {
  log('');
  log(`──── FLOW: APPROVE → publish + §A1 reconcile (${fundId}) ────`);
  const workflowId = `navapprove-${fundId}-${Date.now()}`;
  const readyFile = path.join(work, `ready-${workflowId}`);
  const state = makeLogState();
  tsChild = startTsEndpoint(readyFile, state);
  await waitFor(() => existsSync(readyFile), 60_000, `${fundId}: TS endpoint ready`);
  await new Promise((res) => setTimeout(res, 1500));

  log(`submitting navCalculation/${workflowId}/run (fund ${fundId}; will strike steps then PAUSE at the gate)`);
  submitRunAsync(workflowId, fundId);

  await waitFor(() => state.sawPausing && state.awakeableId !== null, 60_000, `${fundId}: gate to PAUSE`);
  log(`PAUSE confirmed — awakeableId=${state.awakeableId} (steps load/price/fees/roll-up journaled; notifies=${state.notifyCount}).`);

  await new Promise((res) => setTimeout(res, 500));
  await resolveAwakeable(state.awakeableId, { approved: true });
  const terminal = await attachRun(workflowId, fundId);
  await new Promise((res) => setTimeout(res, 800));
  const status = await readStatus(workflowId);

  // Read-back of the mart's nav_usd via navData (a consistency read, NOT an
  // independent oracle — the genuine cross-mart check lives in the workflow's
  // roll-up: holdings gross from mart_portfolio_holdings vs mart_fund_nav.gross).
  const martNav = await readMartNav(fundId);
  const pubRec = status?.publishRecord ?? terminal.json?.publishRecord ?? terminal.json;
  const struckNav = pubRec?.navUsd;
  const reconciles =
    struckNav != null && struckNav === martNav.navUsd && pubRec?.martNavUsd === martNav.navUsd;

  log(
    `terminal: HTTP ${terminal.status} ok=${terminal.ok}; status=${status?.status}; ` +
      `struckNAV=${struckNav}; mart_fund_nav.nav_usd=${martNav.navUsd}; reconciles=${reconciles}.`,
  );

  killTree(tsChild);
  tsChild = null;
  await new Promise((res) => setTimeout(res, 600));
  await pruneDeployments('navCalculation', PROOF_PORT);

  const pass =
    terminal.ok &&
    status?.status === 'published' &&
    status?.publishRecord?.kind === 'nav-published' &&
    reconciles &&
    state.publishCount === 1 &&
    state.notifyCount === 1;
  if (!pass) {
    log(
      `FLOW APPROVE(${fundId}) FAILED: ok=${terminal.ok} status=${status?.status} reconciles=${reconciles} ` +
        `publishCount=${state.publishCount} notifyCount=${state.notifyCount}`,
    );
  } else {
    log(`FLOW APPROVE(${fundId}) PASS: status=published; struck NAV ${struckNav} reconciles to mart §A1; one publish; one notify.`);
  }
  return pass;
}

/** REJECT path: submit, pause, reject via the ingress, assert status=aborted + NO publish record. */
async function runRejectNoPublish(fundId) {
  log('');
  log(`──── FLOW: REJECT → terminal abort, NO publish (${fundId}) ────`);
  const workflowId = `navreject-${fundId}-${Date.now()}`;
  const readyFile = path.join(work, `ready-${workflowId}`);
  const state = makeLogState();
  tsChild = startTsEndpoint(readyFile, state);
  await waitFor(() => existsSync(readyFile), 60_000, `${fundId}: TS endpoint ready`);
  await new Promise((res) => setTimeout(res, 1500));

  submitRunAsync(workflowId, fundId);
  await waitFor(() => state.sawPausing && state.awakeableId !== null, 60_000, `${fundId}: gate to PAUSE`);
  log(`PAUSED — awakeableId=${state.awakeableId}. Rejecting via the ingress...`);

  await new Promise((res) => setTimeout(res, 500));
  await resolveAwakeable(state.awakeableId, { approved: false, reason: 'proof: operator rejects the high-stakes NAV publish' });
  const terminal = await attachRun(workflowId, fundId);
  await new Promise((res) => setTimeout(res, 800));
  const status = await readStatus(workflowId);

  log(
    `terminal: HTTP ${terminal.status} ok=${terminal.ok}; status=${status?.status}; ` +
      `abort=${JSON.stringify(status?.abort)}; publishRecord=${status?.publishRecord ? 'PRESENT(!)' : 'null'}; ` +
      `publishCount(logs)=${state.publishCount}.`,
  );

  killTree(tsChild);
  tsChild = null;
  await new Promise((res) => setTimeout(res, 600));
  await pruneDeployments('navCalculation', PROOF_PORT);

  // Clean terminal 4xx, aborted, NO publish record, publish step NEVER ran (the gate precedes it).
  const pass =
    !terminal.ok &&
    terminal.status >= 400 &&
    terminal.status < 500 &&
    status?.status === 'aborted' &&
    status?.abort?.kind === 'aborted-by-operator' &&
    !status?.publishRecord &&
    state.publishCount === 0;
  if (!pass) {
    log(
      `FLOW REJECT(${fundId}) FAILED: ok=${terminal.ok} status=${status?.status} ` +
        `abortKind=${status?.abort?.kind} publishRecord=${!!status?.publishRecord} publishCount=${state.publishCount}`,
    );
  } else {
    log(`FLOW REJECT(${fundId}) PASS: clean terminal ${terminal.status}; status=aborted (by-operator); NO publish record, publish step never ran.`);
  }
  return pass;
}

/**
 * CRASH MID-GATE-PAUSE: submit, pause at the gate, SIGKILL mid-pause, restart, confirm the
 * workflow resumes STILL-AWAITING (the awakeable id stable, NOT re-prompted), then approve →
 * publishes. The durable pause survived a real crash.
 */
async function runCrashMidPauseThenApprove(fundId) {
  log('');
  log(`──── FLOW: CRASH mid-gate-pause → resume still-awaiting → approve → publish (${fundId}) ────`);
  const workflowId = `navcrashpause-${fundId}-${Date.now()}`;
  const readyFile = path.join(work, `ready-${workflowId}`);

  const state1 = makeLogState();
  tsChild = startTsEndpoint(readyFile, state1);
  await waitFor(() => existsSync(readyFile), 60_000, 'crash-pause: TS endpoint 1 ready');
  const pid1 = readFileSync(readyFile, 'utf8').trim();
  await new Promise((res) => setTimeout(res, 1500));

  submitRunAsync(workflowId, fundId);
  await waitFor(() => state1.sawPausing && state1.awakeableId !== null, 60_000, 'crash-pause: gate to PAUSE');
  const awakeableBefore = state1.awakeableId;
  log(`PAUSED — awakeableId=${awakeableBefore}; notifies(before crash)=${state1.notifyCount}. SIGKILL now (mid-pause).`);

  rmSync(readyFile, { force: true });
  killTree(tsChild);
  await new Promise((res) => setTimeout(res, 1500));
  log('TS endpoint 1 dead. The strike is suspended at the awakeable, NOT yet decided.');

  const state2 = makeLogState();
  tsChild = startTsEndpoint(readyFile, state2);
  await waitFor(() => existsSync(readyFile), 60_000, 'crash-pause: TS endpoint 2 ready');
  const pid2 = readFileSync(readyFile, 'utf8').trim();
  log(`TS endpoint 2 ready (pid ${pid1} -> ${pid2}). Giving the resumed strike a moment...`);
  await new Promise((res) => setTimeout(res, 4000));

  let midStatus = null;
  try {
    midStatus = await readStatus(workflowId);
  } catch {
    /* may be striking with no terminal write */
  }
  const stillAwaiting = !midStatus || midStatus.status === 'striking';
  const noRePrompt = state2.notifyCount === 0;
  log(
    `after resume: status=${midStatus?.status} (still-awaiting=${stillAwaiting}); ` +
      `notifies(resumed)=${state2.notifyCount} (re-prompt-free=${noRePrompt}); Replaying=${state2.sawReplaying}.`,
  );

  await resolveAwakeable(awakeableBefore, { approved: true });
  const terminal = await attachRun(workflowId, fundId);
  await new Promise((res) => setTimeout(res, 800));
  const finalStatus = await readStatus(workflowId);
  const martNav = await readMartNav(fundId);
  const reconciles = finalStatus?.publishRecord?.navUsd === martNav.navUsd;
  log(`after approve (same awakeable id): HTTP ${terminal.status}; status=${finalStatus?.status}; reconciles=${reconciles}.`);

  killTree(tsChild);
  tsChild = null;
  await new Promise((res) => setTimeout(res, 600));
  await pruneDeployments('navCalculation', PROOF_PORT);

  const realRestart = pid1 !== pid2;
  const reachedPublished = terminal.ok && finalStatus?.status === 'published';
  const pass = stillAwaiting && noRePrompt && realRestart && state2.sawReplaying && reachedPublished && reconciles;
  if (!pass) {
    log(
      `CRASH-MID-PAUSE FAILED: stillAwaiting=${stillAwaiting} noRePrompt=${noRePrompt} realRestart=${realRestart} ` +
        `replaying=${state2.sawReplaying} reachedPublished=${reachedPublished} reconciles=${reconciles}`,
    );
  } else {
    log('CRASH-MID-PAUSE PASS: crashed mid-pause → resumed STILL-AWAITING on a fresh pid (Replaying), awakeable id stable, NO re-prompt; approved same id → published + reconciles.');
  }
  return pass;
}

/**
 * PUBLISH-EXACTLY-ONCE: submit with the post-approval pre-publish crash pause armed; pause at
 * the gate, approve (decision journals), wait until the strike enters the pre-publish pause,
 * SIGKILL there (a real crash AFTER approval but the publish window). On resume the journaled
 * decision is read back and the publish runs ONCE; the published NAV is byte-identical
 * (struckAt unchanged), the publish step NOT re-run on the resumed process.
 *
 * NOTE: the crash here is BEFORE the publish ctx.run records — so "exactly once" means the
 * publish executes exactly once across the crash (it had not run pre-crash; it runs once on
 * resume). To ALSO cover a crash AFTER the publish record (read-back, no re-run), we then
 * re-submit the SAME workflow id (a workflow is one-shot per id) and confirm the SAME published
 * record is returned without a second publish-step emission.
 */
async function runPublishExactlyOnce(fundId) {
  log('');
  log(`──── FLOW: PUBLISH-exactly-once (crash after approval, in the publish window → publish ONCE) (${fundId}) ────`);
  const workflowId = `navonce-${fundId}-${Date.now()}`;
  const readyFile = path.join(work, `ready-${workflowId}`);

  // process 1 — pause at the gate, with the pre-publish crash pause armed (8s) so AFTER we
  // approve, the strike pauses in the between-approval-and-publish window.
  const state1 = makeLogState();
  tsChild = startTsEndpoint(readyFile, state1, { AGENTINVEST_NAV_PREPUBLISH_CRASH_DELAY_MS: '8000' });
  await waitFor(() => existsSync(readyFile), 60_000, 'once: TS endpoint 1 ready');
  const pid1 = readFileSync(readyFile, 'utf8').trim();
  await new Promise((res) => setTimeout(res, 1500));

  submitRunAsync(workflowId, fundId);
  await waitFor(() => state1.sawPausing && state1.awakeableId !== null, 60_000, 'once: gate to PAUSE');
  const awakeableBefore = state1.awakeableId;
  log(`PAUSED at the gate — awakeableId=${awakeableBefore}. Approving so the decision JOURNALS, then crashing in the publish window...`);

  await resolveAwakeable(awakeableBefore, { approved: true });
  // Wait for the strike to ENTER the pre-publish pause (the handler logs it), so the crash lands
  // AFTER the decision journaled and BEFORE the publish ctx.run records.
  await waitFor(() => state1.prePublishPause, 30_000, 'once: strike to enter the pre-publish pause');
  log('strike is in the pre-publish window (decision journaled, publish pending). SIGKILL now.');
  rmSync(readyFile, { force: true });
  killTree(tsChild);
  await new Promise((res) => setTimeout(res, 1500));
  log('SIGKILLed AFTER approval, BEFORE publish. On resume the decision must be read back + the publish runs exactly once.');

  // process 2 — restart with the SAME crash-delay env so the replayed code matches the journal
  // (the journaled ctx.sleep entry must be reproduced). On resume the strike replays past the
  // elapsed sleep, reads the decision back, publishes ONCE.
  const state2 = makeLogState();
  tsChild = startTsEndpoint(readyFile, state2, { AGENTINVEST_NAV_PREPUBLISH_CRASH_DELAY_MS: '8000' });
  await waitFor(() => existsSync(readyFile), 60_000, 'once: TS endpoint 2 ready');
  const pid2 = readFileSync(readyFile, 'utf8').trim();
  await new Promise((res) => setTimeout(res, 2000));

  const terminal = await attachRun(workflowId, fundId);
  await new Promise((res) => setTimeout(res, 800));
  const finalStatus = await readStatus(workflowId);
  const publishedRecord1 = finalStatus?.publishRecord;
  log(
    `after resume: HTTP ${terminal.status}; status=${finalStatus?.status}; ` +
      `publishCount(resumed process logs)=${state2.publishCount}; notifies(resumed)=${state2.notifyCount}; ` +
      `Replaying=${state2.sawReplaying}; struckAt=${publishedRecord1?.struckAt}.`,
  );

  // NOW the read-back case: re-submit the SAME workflow id (a workflow is one-shot per id) —
  // Restate returns the SAME terminal result WITHOUT re-running the publish step (exactly-once
  // on a completed workflow). Start a fresh process so any re-emission would be visible on it.
  killTree(tsChild);
  await new Promise((res) => setTimeout(res, 800));
  const state3 = makeLogState();
  const readyFile3 = path.join(work, `ready3-${workflowId}`);
  tsChild = startTsEndpoint(readyFile3, state3);
  await waitFor(() => existsSync(readyFile3), 60_000, 'once: TS endpoint 3 ready');
  await new Promise((res) => setTimeout(res, 1500));
  log('re-submitting the SAME completed workflow id — must return the SAME published record, publish step NOT re-run.');
  const terminal2 = await attachRun(workflowId, fundId);
  await new Promise((res) => setTimeout(res, 600));
  const finalStatus2 = await readStatus(workflowId);
  const publishedRecord2 = finalStatus2?.publishRecord ?? terminal2.json?.publishRecord;
  log(
    `re-submit: HTTP ${terminal2.status}; struckAt=${publishedRecord2?.struckAt}; ` +
      `publishCount(process 3 logs)=${state3.publishCount} (must be 0 — read back, not re-published).`,
  );

  killTree(tsChild);
  tsChild = null;
  await new Promise((res) => setTimeout(res, 600));
  await pruneDeployments('navCalculation', PROOF_PORT);

  const realRestart = pid1 !== pid2;
  const publishedOnceAcrossCrash = state2.publishCount === 1 && finalStatus?.status === 'published';
  // The re-submit returned the identical published record (struckAt byte-identical) and process
  // 3 NEVER re-emitted a publish — exactly-once read-back.
  const identicalRecord =
    publishedRecord1 && publishedRecord2 && publishedRecord1.struckAt === publishedRecord2.struckAt &&
    publishedRecord1.navUsd === publishedRecord2.navUsd;
  const noRepublishOnReadback = state3.publishCount === 0;
  const pass = realRestart && state2.sawReplaying && publishedOnceAcrossCrash && identicalRecord && noRepublishOnReadback;
  if (!pass) {
    log(
      `PUBLISH-EXACTLY-ONCE FAILED: realRestart=${realRestart} replaying=${state2.sawReplaying} ` +
        `publishedOnceAcrossCrash=${publishedOnceAcrossCrash} (publishCount=${state2.publishCount}) ` +
        `identicalRecord=${identicalRecord} noRepublishOnReadback=${noRepublishOnReadback} (p3 publishCount=${state3.publishCount})`,
    );
  } else {
    log('PUBLISH-EXACTLY-ONCE PASS: crashed after approval in the publish window → resumed, decision read back, published ONCE; re-submit returned the IDENTICAL record (struckAt unchanged), NO re-publish. Exactly-once.');
  }
  return pass;
}

async function main() {
  log(`work dir ${work}`);
  if (!(await adminHealthy())) {
    log(`shared Restate admin not reachable at ${ADMIN_URL}. Boot it: (cd ${REFERENCE_ROOT} && pnpm dev:restate).`);
    process.exit(1);
  }

  log('the gate fires unconditionally (publish is high-stakes by declaration, riskScore 1.0). NO LLM — deterministic marts compute + the gate.');

  // navData up (the marts-read seam). Reuse the shared :9091 endpoint if registered; only spawn
  // if not (reuse-safety). navData is bound beside bd09 in the same endpoint.
  if (await awaitServiceRegistered('navData', 2)) {
    log('navData already registered — reusing the running Python endpoint (no spawn). LEFT INTACT on exit (shared).');
  } else {
    pyChild = startPyEndpoint();
    pySpawnedByUs = true;
    if (!(await awaitServiceRegistered('navData'))) {
      log('navData did not register within the timeout. Aborting.');
      try {
        pyChild.kill('SIGKILL');
      } catch {
        /* best-effort */
      }
      process.exit(1);
    }
    log('navData registered (marts-read seam reachable).');
  }

  const results = {};
  // (d) green e2e + cross-mart §A1 reconcile + (b) approve→publish — for EACH real seed fund.
  for (const fundId of SEED_FUNDS) {
    results[`approve-${fundId}`] = await runApprovePublishReconcile(fundId);
  }
  // (g) past-as-of refused on the wire — one fund (the class is the past-as-of field, not the fund).
  results.pastAsOfWire = await runPastAsOfRefusedOnTheWire('PF-0001');
  // (b) reject → no publish (one fund — the class is direction, not fund).
  results.reject = await runRejectNoPublish('PF-0003');
  // (c) crash mid-gate-pause → resume still-awaiting → approve → publish.
  results.crashMidPause = await runCrashMidPauseThenApprove('PF-0002');
  // (c) publish-exactly-once — crash after approval in the publish window + read-back on re-submit.
  results.publishOnce = await runPublishExactlyOnce('PF-0001');

  // Teardown — only what THIS run spawned. The TS proof endpoints are all self-pruned
  // per flow. The shared Python :9091 deployment is torn down ONLY if WE spawned it.
  if (pySpawnedByUs) {
    try {
      pyChild.kill('SIGKILL');
    } catch {
      /* best-effort */
    }
    await new Promise((res) => setTimeout(res, 600));
    await pruneDeployments('navData', process.env.AGENTINVEST_PY_ENDPOINT_PORT ?? '9091');
  } else {
    log('reused the shared Python endpoint — leaving navData/bd09/agentinvestPlanner/pyTools registered on exit (shared).');
  }
  rmSync(work, { recursive: true, force: true });

  const allPass = Object.values(results).every(Boolean);
  log('');
  log('SUMMARY:');
  for (const fundId of SEED_FUNDS) {
    log(`  (d/b) APPROVE→publish + cross-mart §A1 reconcile ${fundId} : ${results[`approve-${fundId}`] ? 'PASS' : 'FAIL'}`);
  }
  log(`  (g) PAST-AS-OF refused on the wire (past date → 422)  : ${results.pastAsOfWire ? 'PASS' : 'FAIL'}`);
  log(`  (b) REJECT → terminal abort, NO publish              : ${results.reject ? 'PASS' : 'FAIL'}`);
  log(`  (c) CRASH mid-gate-pause → resume → approve → publish: ${results.crashMidPause ? 'PASS' : 'FAIL'}`);
  log(`  (c) PUBLISH-exactly-once (crash in publish window)   : ${results.publishOnce ? 'PASS' : 'FAIL'}`);
  log('');
  if (allPass) {
    log('The production NavCalculationWorkflow exercised end-to-end over synthetic data: multi-step journaled NAV');
    log('strike; the gate fires at the irreversible publish (approve→publishes / reject→no-publish); a real crash mid-strike');
    log('recovers (steps replayed, publish exactly-once — internal-journal record, no external write yet); a past-as-of date is');
    log('refused on the wire (422); the struck NAV reconciles across two marts (holdings ↔ mart_fund_nav gross) + the §A1');
    log('identity. Synthetic data, not a struck production NAV; the gate resolved via the ingress.');
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
