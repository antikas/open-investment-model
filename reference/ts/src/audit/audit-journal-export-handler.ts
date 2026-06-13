/**
 * `auditJournalExport` — the invokable Restate handler for the audit-journal export.
 *
 * A thin Restate SERVICE handler that runs the same GATHER → CHAIN → WRITE pipeline the CLI runs, so
 * the export is invokable over the ingress (e.g. by a future nightly scheduler). The NIGHTLY CRON
 * TRIGGER IS DEFERRED (deploy-surface) — this handler is built INVOKABLE; nothing wires a
 * schedule here.
 *
 * JOURNALING DISCIPLINE. The two side effects — the GATHER (admin/ingress reads
 * over `fetch`) and the WRITE (the JSON-L file write) — each run inside a TOP-LEVEL `ctx.run` so
 * their results are journaled exactly-once; neither nests a further context action inside its
 * closure. The export TIMESTAMP is read as a TOP-LEVEL journaled `ctx.date.now()` (never a bare
 * `Date.now()` inside a journaled closure — the determinism anti-pattern), then PASSED IN to the
 * write, so a replay reproduces the same export filename + manifest timestamp.
 *
 * READ-ONLY over the audit trail. The handler enumerates + reads + chains + writes a SEPARATE export
 * file. It does not alter how `operation-closed` / the NAV publish record are produced.
 *
 * S3 + cron DEFERRED (v0.1 honest boundary). Writes a LOCAL file (tamper-EVIDENCE); the S3
 * object-lock immutable store + the nightly schedule are v0.2/deploy.
 */
import { service, type Context } from '@restatedev/restate-sdk';
import { gatherAuditRecords, defaultEndpoints, type GatherResult } from './gather.js';
import { writeJsonlExport, defaultExportDir, type WriteResult } from './jsonl-export.js';
import type { NormalisedAuditRecord } from './audit-record.js';

export const AUDIT_JOURNAL_EXPORT_NAME = 'auditJournalExport';

/** The export handler's input — an optional output dir override (defaults to the env / repo path). */
export interface AuditExportInput {
  /** Output directory override; default `AGENTINVEST_AUDIT_EXPORT_DIR` / `./.audit-export`. */
  dir?: string | null;
}

/** The export handler's result — the on-disk paths + the chain tip + count + the read summary. */
export interface AuditExportOutput {
  dataPath: string;
  manifestPath: string;
  chainTip: string;
  recordCount: number;
  keysSeen: number;
  statesRead: number;
  exportedAt: string;
}

export const auditJournalExport = service({
  name: AUDIT_JOURNAL_EXPORT_NAME,
  handlers: {
    /**
     * Run one export: gather → chain → write. Each step is a journaled top-level `ctx.run`; the
     * timestamp is a top-level journaled `ctx.date.now()`. Replay reads each step back.
     */
    async run(ctx: Context, input: AuditExportInput = {}): Promise<AuditExportOutput> {
      const dir = input.dir ?? defaultExportDir();
      const endpoints = defaultEndpoints();

      // GATHER — a journaled side effect (admin/ingress reads). The result (the real records) is
      // journaled so a replay reads the SAME records back rather than re-querying a changed engine.
      const gathered = await ctx.run<GatherResult>('audit-export-gather', () =>
        gatherAuditRecords(endpoints),
      );
      ctx.console.log(
        `[audit-journal-export] gathered ${gathered.records.length} audit record(s) ` +
          `(${gathered.keysSeen} key(s), ${gathered.statesRead} state(s) read).`,
      );

      // The export timestamp — a TOP-LEVEL journaled clock read (never Date.now() inside a closure).
      const exportedAtMs = await ctx.date.now();
      const exportedAt = new Date(exportedAtMs).toISOString();

      // WRITE — a journaled side effect (the JSON-L + manifest file write). The records came from the
      // journaled gather; the timestamp is the journaled clock — so a replay reproduces the same file.
      const records = gathered.records as NormalisedAuditRecord[];
      const written = await ctx.run<WriteResult>('audit-export-write', () =>
        writeJsonlExport(records, exportedAt, dir),
      );
      ctx.console.log(
        `[audit-journal-export] wrote ${written.recordCount} record(s) → ${written.dataPath} ` +
          `(tip ${written.chainTip}). v0.1 local file — tamper-EVIDENCE, not prevention (S3 + cron deferred).`,
      );

      return {
        dataPath: written.dataPath,
        manifestPath: written.manifestPath,
        chainTip: written.chainTip,
        recordCount: written.recordCount,
        keysSeen: gathered.keysSeen,
        statesRead: gathered.statesRead,
        exportedAt,
      };
    },
  },
});
