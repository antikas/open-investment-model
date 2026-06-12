/**
 * The GATHER — enumerate the REAL agentINVEST audit records via the authoritative admin-API path
 * (OIM-151 part 3).
 *
 * The audit records live in the operation/workflow STATE (the `investmentOperation` VO's
 * `auditRecord`, the `navCalculation` workflow's `publishRecord`), read over the Restate ingress
 * `status` handler — exactly the OIM-142 Operations-dashboard read path. This module REUSES that
 * read path rather than coupling the export to the Operator UI's server-only `lib/restate.ts` (which
 * `import 'server-only'`s and cannot be pulled into this orchestrator-adjacent package): it factors a
 * small, dependency-free reader that speaks the SAME two surfaces the UI uses —
 *   - the ADMIN API (`:9070`) to ENUMERATE operation keys (`sys_invocation` introspection), and
 *   - the INGRESS (`:8080`) to READ each operation's recorded state (the `status` handler).
 *
 * The UI's `listOperations` enumerates keys from a STUBBED `queryInvocations` (it returns `[]` to
 * avoid an Arrow-IPC dependency) plus the approval registry — so it sees only GATED operations'
 * keys. The export needs EVERY operation, so the gather enumerates keys from the admin `/query` SQL
 * surface requested as JSON (`Accept: application/json` → `{rows:[...]}`, no Arrow dependency) — the
 * authoritative engine view of every invocation against our two handlers. It then reads each key's
 * recorded state over the ingress and extracts the audit record (the VO `auditRecord`, the workflow
 * `publishRecord`), normalising each via the single recognition SSOT (`audit-record.ts`).
 *
 * READ-ONLY. The gather never writes — it enumerates + reads + normalises. It does not alter how an
 * audit record is produced (the export CONSUMES the records). Best-effort + honest: an unreachable
 * key is skipped (not fabricated); the result is whatever real records were readable, in
 * deterministic chain order.
 */
import {
  normaliseAuditRecord,
  orderAuditRecords,
  type NormalisedAuditRecord,
} from './audit-record.js';

/** The two surfaces the gather reaches (defaulted; overridable for a different dev/CI Restate). */
export interface GatherEndpoints {
  /** The Restate admin API base (key enumeration). Default env RESTATE_ADMIN_URL or :9070. */
  adminUrl: string;
  /** The Restate ingress base (state reads). Default env RESTATE_INGRESS_URL or :8080. */
  ingressUrl: string;
}

/** The agentINVEST audit-bearing handlers. */
type OperationKind = 'investmentOperation' | 'navCalculation';
const AUDIT_KINDS: readonly OperationKind[] = ['investmentOperation', 'navCalculation'];

export function defaultEndpoints(): GatherEndpoints {
  return {
    adminUrl: process.env.RESTATE_ADMIN_URL ?? 'http://127.0.0.1:9070',
    ingressUrl: process.env.RESTATE_INGRESS_URL ?? 'http://127.0.0.1:8080',
  };
}

const NO_STORE: RequestInit = { cache: 'no-store' };

/**
 * Enumerate the operation/workflow keys the engine has seen for our two handlers, via the admin
 * `/query` SQL surface requested as JSON (no Arrow dependency). Returns the distinct `{operationId,
 * kind}` pairs. Best-effort: returns [] on any failure (the export then has nothing to gather rather
 * than throwing on a transient admin hiccup).
 */
export async function enumerateOperationKeys(
  endpoints: GatherEndpoints = defaultEndpoints(),
): Promise<{ operationId: string; kind: OperationKind }[]> {
  const out = new Map<string, OperationKind>();
  try {
    const res = await fetch(`${endpoints.adminUrl}/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({
        query:
          `SELECT target_service_name, target_service_key FROM sys_invocation ` +
          `WHERE target_service_name IN ('investmentOperation','navCalculation') ` +
          `AND target_service_key IS NOT NULL`,
      }),
      signal: AbortSignal.timeout(8000),
      ...NO_STORE,
    });
    if (!res.ok) return [];
    const body = (await res.json()) as { rows?: { target_service_name?: string; target_service_key?: string }[] };
    for (const row of body.rows ?? []) {
      const svc = row.target_service_name;
      const key = row.target_service_key;
      if (!key) continue;
      if (svc === 'investmentOperation') out.set(`investmentOperation:${key}`, 'investmentOperation');
      else if (svc === 'navCalculation') out.set(`navCalculation:${key}`, 'navCalculation');
    }
  } catch {
    return [];
  }
  return [...out.entries()].map(([combined, kind]) => ({
    operationId: combined.slice(combined.indexOf(':') + 1),
    kind,
  }));
}

/** Read one operation's recorded state over the ingress `status` handler. Null on any failure. */
export async function readOperationState(
  kind: OperationKind,
  operationId: string,
  endpoints: GatherEndpoints,
): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(`${endpoints.ingressUrl}/${kind}/${encodeURIComponent(operationId)}/status`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
      signal: AbortSignal.timeout(15_000),
      ...NO_STORE,
    });
    if (!res.ok) return null;
    return (await res.json()) as Record<string, unknown> | null;
  } catch {
    return null;
  }
}

/**
 * Extract the audit record(s) from a recorded operation/workflow state. The VO carries its audit
 * record under `auditRecord` (the `operation-closed` record); the workflow carries it under
 * `publishRecord` (the `nav-published` record). Each is normalised via the single recognition SSOT;
 * a state with neither (an in-flight / aborted op) yields nothing — never a fabricated record.
 */
export function extractAuditRecords(state: Record<string, unknown> | null): NormalisedAuditRecord[] {
  if (!state) return [];
  const out: NormalisedAuditRecord[] = [];
  for (const field of ['auditRecord', 'publishRecord'] as const) {
    const candidate = state[field];
    const normalised = normaliseAuditRecord(candidate);
    if (normalised) out.push(normalised);
  }
  return out;
}

/** The gather result — the real records (in deterministic chain order) + a small read summary. */
export interface GatherResult {
  records: NormalisedAuditRecord[];
  /** How many operation keys the engine reported (the enumeration size). */
  keysSeen: number;
  /** How many keys yielded a readable state (the rest were unreachable / in-flight). */
  statesRead: number;
}

/**
 * Gather every real agentINVEST audit record: enumerate the operation keys (admin), read each key's
 * recorded state (ingress), extract + normalise the audit records, and return them in DETERMINISTIC
 * chain order (by occurredAt then operationId — so the chain is reproducible across runs over the
 * same data). READ-ONLY; best-effort; never fabricates.
 */
export async function gatherAuditRecords(
  endpoints: GatherEndpoints = defaultEndpoints(),
): Promise<GatherResult> {
  const keys = await enumerateOperationKeys(endpoints);
  let statesRead = 0;
  const records: NormalisedAuditRecord[] = [];
  await Promise.all(
    keys.map(async ({ operationId, kind }) => {
      const state = await readOperationState(kind, operationId, endpoints);
      if (state) {
        statesRead++;
        records.push(...extractAuditRecords(state));
      }
    }),
  );
  return {
    records: orderAuditRecords(records),
    keysSeen: keys.length,
    statesRead,
  };
}

export { AUDIT_KINDS };
