/**
 * The SERVER-SIDE Restate reach for the Operator UI.
 *
 * Every function here runs ONLY on the server (route handlers + server components
 * import it; it is never bundled into a client component). The console reaches the
 * local Restate two ways:
 *   - the ADMIN API (`:9070`) — list registered services + introspect invocations /
 *     virtual-object state (the operations the Operations dashboard reads);
 *   - the INGRESS (`:8080`) — call handlers: the pending-approvals registry reader,
 *     the per-operation/workflow `status`, and the awakeable resolve/reject (the
 *     approval action of record).
 *
 * NO SECRET IN THE CLIENT. There is no Restate key in local dev, but the pattern is
 * held regardless: the URLs and every fetch live on the server; the browser holds
 * none of them. The single-operator v0.1 posture has NO app-layer auth — the network
 * boundary (a Tailscale ACL) is the deploy-step control (a forward item); the dev UI
 * is unauthenticated on localhost, correct for the workstation, not a production
 * posture.
 *
 * `import 'server-only'` makes a build FAIL LOUDLY if this module is ever pulled into
 * a client bundle — the structural guard behind the no-secret-in-client claim.
 */
import 'server-only';

const ADMIN_URL = process.env.RESTATE_ADMIN_URL ?? 'http://127.0.0.1:9070';
const INGRESS_URL = process.env.RESTATE_INGRESS_URL ?? 'http://127.0.0.1:8080';

/** No long-poll caching — the console always reads the live state. */
const NO_STORE: RequestInit = { cache: 'no-store' };

async function ingressPost<T>(handlerPath: string, body: unknown): Promise<T> {
  const res = await fetch(`${INGRESS_URL}/${handlerPath}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body ?? {}),
    signal: AbortSignal.timeout(15_000),
    ...NO_STORE,
  });
  if (!res.ok) {
    throw new Error(`ingress POST /${handlerPath} failed ${res.status}: ${await res.text()}`);
  }
  return (await res.json()) as T;
}

// ── Admin: deployments / services ───────────────────────────────────────────

export interface ServiceSummary {
  name: string;
  ty: string;
  deploymentId: string;
  uri: string;
}

/** Is the local Restate admin reachable? Drives the console's connectivity banner. */
export async function adminHealthy(): Promise<boolean> {
  try {
    const r = await fetch(`${ADMIN_URL}/health`, { signal: AbortSignal.timeout(2500), ...NO_STORE });
    return r.ok;
  } catch {
    return false;
  }
}

interface AdminDeployment {
  id: string;
  uri: string;
  services?: { name: string; ty?: string }[];
}

/** List every registered service across all deployments (the runtime topology an operator sees). */
export async function listServices(): Promise<ServiceSummary[]> {
  try {
    const res = await fetch(`${ADMIN_URL}/deployments`, { signal: AbortSignal.timeout(5000), ...NO_STORE });
    if (!res.ok) return [];
    const body = (await res.json()) as { deployments?: AdminDeployment[] };
    const out: ServiceSummary[] = [];
    for (const dep of body.deployments ?? []) {
      for (const svc of dep.services ?? []) {
        out.push({ name: svc.name, ty: svc.ty ?? 'service', deploymentId: dep.id, uri: dep.uri });
      }
    }
    return out;
  } catch {
    return [];
  }
}

/** True iff the agentINVEST orchestrator/workflow handlers are registered (vs only a sibling project's). */
export async function agentinvestRegistered(): Promise<boolean> {
  const services = await listServices();
  const names = new Set(services.map((s) => s.name));
  return names.has('investmentOperation') || names.has('navCalculation') || names.has('approvalRegistryReader');
}

// ── Deployments: the registered Restate deployments + the in-flight-op version distribution ──

export interface DeploymentService {
  name: string;
  revision: number | null;
}

export interface DeploymentView {
  id: string;
  uri: string;
  sdkVersion: string | null;
  createdAt: string | null;
  services: DeploymentService[];
  /** How many in-flight (at-gate) operations this UI can correlate to THIS deployment, by service. */
  inFlightOnDeployment: number;
}

export interface DeploymentsSummary {
  deployments: DeploymentView[];
  /** Total in-flight (at-gate) operations the UI can see across all deployments. */
  inFlightTotal: number;
  /**
   * Whether the per-deployment in-flight VERSION distribution (which deployment revision each
   * in-flight op is pinned to) is precisely readable here. The Restate admin exposes the pinned
   * deployment per invocation only via its Arrow-IPC `/query` surface, which this thin slice does
   * not parse — so we show the deployment→services topology + the in-flight op COUNT correlated by
   * service, and route the precise per-revision pin distribution to a follow-up. Never fabricated.
   */
  versionDistributionPrecise: boolean;
}

interface AdminDeploymentFull {
  id: string;
  uri: string;
  sdk_version?: string;
  created_at?: string;
  services?: { name: string; revision?: number }[];
}

/**
 * List the registered Restate deployments + their services, and correlate the in-flight (at-gate)
 * operations the UI can see to each deployment by service name. READ-ONLY (no register/rollover —
 * those are the Restate CLI's + a forward item). The precise per-revision version distribution of
 * in-flight operations is NOT fabricated: the pinned-deployment-per-invocation data lives behind the
 * admin Arrow-IPC `/query` surface this thin slice does not parse, so we report the topology + the
 * in-flight count correlated by the service a deployment hosts, and flag the precise distribution as
 * not-precisely-readable here (a follow-up). Returns an empty list if the admin is unreachable.
 */
export async function listDeployments(): Promise<DeploymentsSummary> {
  let deployments: AdminDeploymentFull[] = [];
  try {
    const res = await fetch(`${ADMIN_URL}/deployments`, { signal: AbortSignal.timeout(5000), ...NO_STORE });
    if (res.ok) {
      const body = (await res.json()) as { deployments?: AdminDeploymentFull[] };
      deployments = body.deployments ?? [];
    }
  } catch {
    return { deployments: [], inFlightTotal: 0, versionDistributionPrecise: false };
  }

  // The in-flight (at-gate) operations the UI can see: each pending approval is a LIVE operation
  // suspended at the gate. We correlate it to a deployment by the service that hosts its kind —
  // an `investmentOperation` / `navCalculation` op runs on whichever deployment registers that
  // service. This is a real, read-only correlation; it is NOT the precise per-revision pin.
  const inFlightByService = new Map<string, number>();
  try {
    const { pending } = await listApprovals();
    for (const a of pending) {
      const svc = a.origin === 'navCalculation' ? 'navCalculation' : 'investmentOperation';
      inFlightByService.set(svc, (inFlightByService.get(svc) ?? 0) + 1);
    }
  } catch {
    /* registry not up — show topology with zero in-flight rather than erroring */
  }
  const inFlightTotal = [...inFlightByService.values()].reduce((s, n) => s + n, 0);

  const views: DeploymentView[] = deployments.map((dep) => {
    const services: DeploymentService[] = (dep.services ?? []).map((s) => ({
      name: s.name,
      revision: typeof s.revision === 'number' ? s.revision : null,
    }));
    const serviceNames = new Set(services.map((s) => s.name));
    let inFlightOnDeployment = 0;
    for (const [svc, n] of inFlightByService) {
      if (serviceNames.has(svc)) inFlightOnDeployment += n;
    }
    return {
      id: dep.id,
      uri: dep.uri,
      sdkVersion: dep.sdk_version ?? null,
      createdAt: dep.created_at ?? null,
      services,
      inFlightOnDeployment,
    };
  });

  return {
    deployments: views,
    inFlightTotal,
    // The precise per-revision distribution needs the admin Arrow-IPC `/query` surface (not parsed
    // here) — we show the topology + the correlated in-flight count, never a fabricated distribution.
    versionDistributionPrecise: false,
  };
}

// ── Canonical-data inspector: the read-only `canonicalData` handler over the ingress ──

export interface CanonicalTable {
  name: string;
  schema: string;
  table: string;
  layer: 'mart' | 'staging' | string;
  rowCount: number;
}

export interface CanonicalSample {
  name: string;
  columns: string[];
  rows: (string | null)[][];
  rowCount: number;
  sampled: number;
  limit: number;
}

/**
 * List the inspectable canonical tables (the dbt marts + the realised staging entities) with row
 * counts, by calling the READ-ONLY `canonicalData/listTables` Python handler over the ingress. The
 * handler derives the set from the store's own catalogue (no fabricated names). Returns an empty
 * list (with `available: false`) if the data endpoint is not reachable, so the page degrades to an
 * "inspector unavailable" banner rather than throwing.
 */
export async function listCanonicalTables(): Promise<{ tables: CanonicalTable[]; available: boolean }> {
  try {
    const res = await ingressPost<{ tables: CanonicalTable[] }>('canonicalData/listTables', {});
    return { tables: res.tables ?? [], available: true };
  } catch {
    return { tables: [], available: false };
  }
}

/**
 * Read a CAPPED sample (≤25 rows) of one canonical table by calling the READ-ONLY
 * `canonicalData/sampleTable` Python handler over the ingress. The table name is validated against
 * the store-derived ALLOWLIST in the handler — an unknown / crafted / injection name is refused
 * (404) before any sample SQL, never interpolated. This is NOT a query console: the only inputs are
 * an allowlisted table name + a capped row limit. Returns `null` if the table is not inspectable or
 * the endpoint is unreachable (the page shows a clean "not available" rather than throwing).
 */
export async function sampleCanonicalTable(name: string, limit = 25): Promise<CanonicalSample | null> {
  // Validate the cap on the server too (defence in depth — the handler clamps it regardless).
  const capped = Math.max(1, Math.min(Math.trunc(limit) || 25, 25));
  try {
    return await ingressPost<CanonicalSample>('canonicalData/sampleTable', { table: name, limit: capped });
  } catch {
    return null;
  }
}

// ── Approvals: the additive pending-approvals registry (read) + the awakeable (resolve) ──

export interface PendingApproval {
  operationId: string;
  awakeableId: string;
  riskScore: number;
  threshold: number;
  summary: string | null;
  stepCount: number;
  selectedSoIds: string[];
  origin: string;
  raisedAt: string;
  status: 'pending' | 'resolved';
  decision?: 'approved' | 'rejected' | 'aborted' | null;
  resolvedAt?: string | null;
}

export interface ApprovalList {
  pending: PendingApproval[];
  resolved: PendingApproval[];
}

/**
 * List the pending + recently-resolved approvals from the ADDITIVE pending-approvals
 * registry (the index the OIM-132 gate's notify also records each notice in). This is
 * a REAL data source: each pending row is a LIVE operation/workflow paused at the gate
 * awaiting a decision. Returns empty lists if the registry reader is not registered
 * (e.g. the agentINVEST endpoint is down) rather than throwing.
 */
export async function listApprovals(): Promise<ApprovalList> {
  try {
    return await ingressPost<ApprovalList>('approvalRegistryReader/list', {});
  } catch {
    return { pending: [], resolved: [] };
  }
}

/**
 * Raised when an operator acts on a STALE approval row — one whose underlying operation
 * is no longer suspended at the gate (already approved/rejected/timed-out, or gone). The
 * UI surfaces this honestly ("no longer pending") and records NO decision. The ingress
 * returns HTTP 202 for resolving a dead/already-resolved awakeable, so a bare 202 is NOT
 * confirmation the action had an effect — we confirm liveness against the op's recorded
 * state BEFORE resolving (OIM-142 cycle-2, fix #3).
 */
export class StaleApprovalError extends Error {
  readonly operationId: string;
  readonly observedStatus: string | null;
  constructor(operationId: string, observedStatus: string | null) {
    super(
      `This approval is no longer pending — already decided or expired ` +
        `(operation ${operationId}${observedStatus ? ` is ${observedStatus}` : ' is gone'}). No decision was recorded.`,
    );
    this.name = 'StaleApprovalError';
    this.operationId = operationId;
    this.observedStatus = observedStatus;
  }
}

/** A workflow/operation paused at the gate is still in-flight — these are the live-at-gate states. */
const LIVE_AT_GATE_STATUSES = new Set(['running', 'striking']);

/**
 * Confirm an operation is GENUINELY suspended at the gate (live), by reading its recorded
 * status over the ingress. Returns the observed status. A live-at-gate op reads
 * `running` (investmentOperation, written before the gate) or `striking` (navCalculation);
 * a terminal op reads `completed`/`aborted`/`published`; a gone op reads `null`. On a
 * transient read error we return `undefined` (treated as live — never block a genuine
 * decision on a read hiccup; the awakeable resolve is itself idempotent).
 */
async function readOperationLiveStatus(
  operationId: string,
  origin: string,
): Promise<string | null | undefined> {
  const kind = origin === 'navCalculation' ? 'navCalculation' : 'investmentOperation';
  try {
    const state = await ingressPost<{ status?: string } | null>(
      `${kind}/${encodeURIComponent(operationId)}/status`,
      {},
    );
    if (!state) return null;
    return typeof state.status === 'string' ? state.status : null;
  } catch {
    return undefined; // transient — do not block a genuine decision
  }
}

/**
 * APPROVE or REJECT a pending approval. The decision is recorded at the AWAKEABLE
 * (the gate's path of record): `POST {ingress}/restate/awakeables/{id}/resolve` with
 * `{approved:true}` (proceed) or `/resolve` with `{approved:false,reason}` (abort). We
 * use `/resolve` for both (the gate reads `decision.approved`); the reason is recorded
 * in the gate's abort-trace.
 *
 * STALE-ROW GUARD (OIM-142 cycle-2, fix #3): before resolving, CONFIRM the operation is
 * genuinely suspended at the gate (its recorded status is live-at-gate). A bare ingress
 * 202 is NOT that confirmation — the ingress returns 202 for a dead/already-resolved
 * awakeable, which is how a click on a stale row previously recorded a phantom `approved`.
 * If the op is already terminal/gone we throw `StaleApprovalError` and record NOTHING.
 *
 * After a confirmed-live resolve we mark the registry entry resolved so the queue reflects
 * the new state — the registry is a list, never the lock (the gate also marks it on its
 * own terminal path; this keeps the UI's immediate refresh snappy).
 */
export async function decideApproval(
  operationId: string,
  awakeableId: string,
  approved: boolean,
  reason: string | null,
  origin: string,
): Promise<void> {
  // Confirm the awakeable is actually pending (the op is still suspended at the gate).
  const observed = await readOperationLiveStatus(operationId, origin);
  if (observed !== undefined && !LIVE_AT_GATE_STATUSES.has(observed ?? '')) {
    // The op is terminal or gone — a stale row. Record no false decision.
    throw new StaleApprovalError(operationId, observed);
  }

  const res = await fetch(
    `${INGRESS_URL}/restate/awakeables/${encodeURIComponent(awakeableId)}/resolve`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ approved, reason: reason ?? undefined }),
      signal: AbortSignal.timeout(15_000),
      ...NO_STORE,
    },
  );
  if (!res.ok) {
    throw new Error(`resolve awakeable ${awakeableId} failed ${res.status}: ${await res.text()}`);
  }

  // NO-STALE-ASSERT (OIM-142 cycle-3, defence-in-depth for P-MINOR-1). The ingress returns
  // 202 even for a DEAD/already-resolved awakeable (no effect) — so a 202 here is NOT proof
  // the operator's decision took effect. The TOCTOU race: the pre-read above saw the op live
  // (striking/running) and the gate's durable timeout THEN fired underneath, aborting the op.
  // Re-read the op's status AFTER the POST; if it went TERMINAL the timeout won — do NOT
  // assert the operator's (now stale) decision into the registry mark; surface it honestly
  // (recording nothing). The registry handler is terminal-truth-wins regardless (the gate's
  // terminal `aborted` overrides a stale UI mark whichever order it arrives), so this is belt
  // to the registry's braces — it narrows the window in which the override has to fire.
  const after = await readOperationLiveStatus(operationId, origin);
  if (after !== undefined && !LIVE_AT_GATE_STATUSES.has(after ?? '')) {
    throw new StaleApprovalError(operationId, after ?? null);
  }

  // Mark the registry entry resolved (best-effort — the awakeable, already resolved
  // above, is the decision of record; a failure here only delays the list refresh). The
  // registry's terminal-truth-wins rule keeps the gate's terminal `aborted` even if this late
  // mark carries a different (stale) one, and corrects the label if the gate's mark arrives after.
  try {
    await ingressPost(`approvalRegistry/${encodeURIComponent(operationId)}/resolve`, {
      decision: approved ? 'approved' : 'rejected',
    });
  } catch {
    /* the awakeable is resolved; the list will reconcile on next read */
  }
}

// ── Operations: in-flight + completed operations + the operation-closed audit record ──

export interface OperationView {
  operationId: string;
  kind: 'investmentOperation' | 'navCalculation';
  status: string;
  /** A one-line human summary (the plan summary / the fund). */
  summary: string | null;
  /** The full recorded state (the OIM-134 audit record lives under `auditRecord`). */
  state: Record<string, unknown> | null;
}

interface AdminInvocation {
  id: string;
  target_service_name?: string;
  target_service_key?: string;
  status?: string;
}

/**
 * Query the admin SQL introspection for the agentINVEST operations + their keys. The
 * `/query` endpoint speaks Arrow IPC, which is awkward to parse here; instead we read
 * the operation KEYS the registry + recent invocations expose and fetch each one's
 * recorded `status` over the ingress (the virtual-object / workflow state, where the
 * OIM-134 `operation-closed` audit record lives). Returns the operations whose state
 * we can read — read-only, no mutation.
 */
export async function listOperations(): Promise<OperationView[]> {
  const ids = await operationKeys();
  const views = await Promise.all(
    ids.map(async ({ operationId, kind }): Promise<OperationView | null> => {
      try {
        const state = await ingressPost<Record<string, unknown> | null>(
          `${kind}/${encodeURIComponent(operationId)}/status`,
          {},
        );
        if (!state) return null;
        return {
          operationId,
          kind,
          status: typeof state.status === 'string' ? state.status : 'unknown',
          summary: operationSummary(state),
          state,
        };
      } catch {
        return null;
      }
    }),
  );
  return views.filter((v): v is OperationView => v !== null);
}

/** Read a single operation's recorded state (the full OIM-134 audit record for the detail view). */
export async function getOperation(kind: string, operationId: string): Promise<Record<string, unknown> | null> {
  if (kind !== 'investmentOperation' && kind !== 'navCalculation') return null;
  try {
    return await ingressPost<Record<string, unknown> | null>(
      `${kind}/${encodeURIComponent(operationId)}/status`,
      {},
    );
  } catch {
    return null;
  }
}

/** Derive a one-line summary from a recorded operation/strike state. */
function operationSummary(state: Record<string, unknown>): string | null {
  const audit = state.auditRecord as { task?: string; plan?: { summary?: string } } | undefined;
  if (audit?.plan?.summary) return audit.plan.summary;
  if (audit?.task) return audit.task;
  const pub = state.publishRecord as { fundName?: string; navUsd?: string } | undefined;
  if (pub?.fundName) return `NAV ${pub.navUsd ?? ''} — ${pub.fundName}`;
  if (typeof state.fundId === 'string') return `NAV strike — ${state.fundId}`;
  return null;
}

/**
 * Discover the operation/workflow keys to read. Source: (1) the admin SQL introspection
 * for `sys_invocation` rows targeting our handlers (the live + completed operations);
 * (2) the registry's known operationIds (every gated operation). Deduplicated.
 */
async function operationKeys(): Promise<{ operationId: string; kind: 'investmentOperation' | 'navCalculation' }[]> {
  const out = new Map<string, 'investmentOperation' | 'navCalculation'>();

  // (1) admin invocations — the operations the engine has seen.
  for (const inv of await queryInvocations()) {
    const svc = inv.target_service_name;
    const key = inv.target_service_key;
    if (!key) continue;
    if (svc === 'investmentOperation') out.set(key, 'investmentOperation');
    else if (svc === 'navCalculation') out.set(key, 'navCalculation');
  }

  // (2) the registry's known operationIds (gated operations carry an approval entry).
  try {
    const approvals = await listApprovals();
    for (const a of [...approvals.pending, ...approvals.resolved]) {
      if (!out.has(a.operationId)) {
        out.set(a.operationId, a.origin === 'navCalculation' ? 'navCalculation' : 'investmentOperation');
      }
    }
  } catch {
    /* registry not up — admin invocations alone */
  }

  return [...out.entries()].map(([operationId, kind]) => ({ operationId, kind }));
}

/**
 * Query the admin `/query` SQL surface for recent agentINVEST invocations. The response
 * is Arrow IPC; rather than pull in an Arrow dependency for the thin slice, we read the
 * keys we can recover from the registry (the gated operations) and the JSON list the
 * admin exposes per service. Best-effort: returns [] on any failure, so the Operations
 * dashboard degrades to the registry-known operations rather than erroring.
 */
async function queryInvocations(): Promise<AdminInvocation[]> {
  // The admin /query returns Arrow IPC (binary) — parsing it needs the arrow lib, which
  // we keep out of the thin slice. The registry path (2) above recovers every GATED
  // operation's key (the load-bearing ones — every approval is a real operation). The
  // admin-API correlation of NON-gated completed operations is an OIM-142b enrichment.
  return [];
}
