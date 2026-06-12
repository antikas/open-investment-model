/**
 * The normalised audit-record shape the hash chain folds over (OIM-151).
 *
 * agentINVEST produces two kinds of fiduciary audit record today, both READ-ONLY for the export:
 *  - the `investmentOperation` `operation-closed` record (`aggregate-close.ts`'s
 *    `OperationAuditRecord`), held in the VO state as `auditRecord`;
 *  - the `navCalculation` `publish` record (`nav-calculation-workflow.ts`'s `NavPublishRecord`),
 *    held in the workflow state as `publishRecord`.
 *
 * The export does NOT change how either is produced — it CONSUMES them. To chain a heterogeneous
 * stream deterministically, each source record is mapped to a small NORMALISED envelope:
 *
 *     { auditKind, operationId, recordType, occurredAt, source }
 *
 * where `source` is the ORIGINAL record verbatim (so no fiduciary detail is lost), `recordType` is
 * the record's own discriminant (`operation-closed` / `nav-published`), `operationId` is the
 * operation/workflow key, and `occurredAt` is the record's own timestamp where it carries one (the
 * NAV publish's `struckAt`); the `operation-closed` record carries no timestamp of its own, so
 * `occurredAt` is null for it and ordering falls back to the operationId (the gather documents this).
 *
 * `auditKind` is a fixed envelope marker so the chained record is self-describing. The envelope is a
 * PURE projection — building it never mutates the source record. The chain hashes the WHOLE
 * envelope (via canonical JSON), so a tamper to ANY field of the original `source` is detected.
 */

/** The normalised audit-record envelope the chain folds over. The chained record. */
export interface NormalisedAuditRecord {
  /** Fixed envelope marker — identifies this as a normalised agentINVEST audit record. */
  auditKind: 'agentinvest-audit-record';
  /** The record's own discriminant: an operation close, or a NAV publish. */
  recordType: 'operation-closed' | 'nav-published';
  /** The operation/workflow key the record belongs to (the chain's stable secondary sort key). */
  operationId: string;
  /**
   * The record's own event timestamp (ISO-8601) where it carries one — the NAV publish's `struckAt`.
   * Null for `operation-closed` (the VO audit record carries no timestamp of its own). The PRIMARY
   * chain order key (records with a timestamp sort before null; ties break on operationId).
   */
  occurredAt: string | null;
  /** The ORIGINAL source record, verbatim — no fiduciary detail dropped. The chain hashes all of it. */
  source: Record<string, unknown>;
}

/** A minimal structural read of an `operation-closed` audit record (we do not re-import the orchestrator type to keep the export decoupled). */
interface OperationClosedLike {
  kind?: unknown;
  operationId?: unknown;
}

/** A minimal structural read of a NAV publish record. */
interface NavPublishedLike {
  kind?: unknown;
  workflowId?: unknown;
  struckAt?: unknown;
}

/** Type guard: an `operation-closed` audit record (the VO `auditRecord`). */
export function isOperationClosed(v: unknown): v is OperationClosedLike & Record<string, unknown> {
  return (
    typeof v === 'object' &&
    v !== null &&
    (v as OperationClosedLike).kind === 'operation-closed' &&
    typeof (v as OperationClosedLike).operationId === 'string'
  );
}

/** Type guard: a NAV publish record (the workflow `publishRecord`). */
export function isNavPublished(v: unknown): v is NavPublishedLike & Record<string, unknown> {
  return (
    typeof v === 'object' &&
    v !== null &&
    (v as NavPublishedLike).kind === 'nav-published' &&
    typeof (v as NavPublishedLike).workflowId === 'string'
  );
}

/** Normalise an `operation-closed` audit record into the chain envelope. Pure projection. */
export function normaliseOperationClosed(record: Record<string, unknown>): NormalisedAuditRecord {
  return {
    auditKind: 'agentinvest-audit-record',
    recordType: 'operation-closed',
    operationId: String(record.operationId),
    occurredAt: null, // the VO audit record carries no timestamp of its own
    source: record,
  };
}

/** Normalise a NAV publish record into the chain envelope. Pure projection. */
export function normaliseNavPublished(record: Record<string, unknown>): NormalisedAuditRecord {
  const struckAt = record.struckAt;
  return {
    auditKind: 'agentinvest-audit-record',
    recordType: 'nav-published',
    operationId: String(record.workflowId),
    occurredAt: typeof struckAt === 'string' ? struckAt : null,
    source: record,
  };
}

/**
 * Map an arbitrary recorded value to a normalised audit record IF it is one of the two known audit
 * record types; otherwise null (the caller skips non-audit values). The single recognition SSOT used
 * by the gather and reused by any caller that needs to normalise.
 */
export function normaliseAuditRecord(v: unknown): NormalisedAuditRecord | null {
  if (isOperationClosed(v)) return normaliseOperationClosed(v);
  if (isNavPublished(v)) return normaliseNavPublished(v);
  return null;
}

/**
 * The deterministic chain-order comparator: PRIMARY by `occurredAt` (records with a timestamp first,
 * ascending; nulls last), SECONDARY by `operationId` (ascending), TERTIARY by `recordType`. A total
 * order over the records so the chain is REPRODUCIBLE across runs over the same data — the
 * reproducibility property the audit gate proves. Stable and side-effect-free.
 */
export function compareAuditRecords(a: NormalisedAuditRecord, b: NormalisedAuditRecord): number {
  // occurredAt: non-null sorts before null; among non-nulls, ascending ISO order.
  if (a.occurredAt !== b.occurredAt) {
    if (a.occurredAt === null) return 1;
    if (b.occurredAt === null) return -1;
    if (a.occurredAt < b.occurredAt) return -1;
    if (a.occurredAt > b.occurredAt) return 1;
  }
  if (a.operationId !== b.operationId) return a.operationId < b.operationId ? -1 : 1;
  if (a.recordType !== b.recordType) return a.recordType < b.recordType ? -1 : 1;
  return 0;
}

/** Sort a list of normalised records into deterministic chain order (a copy; the input is untouched). */
export function orderAuditRecords(records: readonly NormalisedAuditRecord[]): NormalisedAuditRecord[] {
  return [...records].sort(compareAuditRecords);
}
