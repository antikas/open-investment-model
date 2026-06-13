/**
 * JSON-L export of the audit hash chain to a LOCAL file + a chain-tip manifest.
 *
 * Writes the chained entries (`hash-chain.ts`) as JSON-L — one JSON object per line — to a
 * configurable LOCAL directory (`AGENTINVEST_AUDIT_EXPORT_DIR`, default a repo-tmp path), plus a
 * MANIFEST sidecar carrying the chain tip (the final `chainHash`), the record count, and the export
 * timestamp. The verifier (`verifier.ts`) reads the JSON-L back; the manifest's tip lets a holder
 * assert the export's tip without recomputing (and lets the verifier catch a FORGED tip — a manifest
 * tip that disagrees with the recomputed chain).
 *
 * EACH JSON-L LINE is the canonical JSON of one `ChainEntry` (`{seq, record, prevHash, chainHash}`) —
 * canonical so a re-export of the same records is byte-identical (the reproducibility property). The
 * verifier recomputes the chain from each line's `record` and compares; the on-line `chainHash` is
 * the stored claim the recompute checks.
 *
 * S3 IS DEFERRED (v0.2). This writes a LOCAL file only. The local file is tamper-EVIDENCE (the chain
 * makes an edit detectable) but NOT tamper-PREVENTION: it can be deleted or replaced. The S3
 * object-lock write-once-immutable store that PREVENTS deletion is the deferred v0.2 layer.
 *
 * NO CLOCK INSIDE A JOURNALED PATH. The export timestamp is passed IN (the CLI supplies a real
 * `new Date()`; a Restate handler must pass a journaled `ctx.date.now()` — never call `Date.now()`
 * inside a journaled closure). `writeJsonlExport` takes the timestamp as a parameter; it never reads
 * a clock itself. The only I/O is the file write (and `mkdir -p` of the output dir).
 */
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { chainRecords, chainTip, type ChainEntry } from './hash-chain.js';
import { canonicalJSON } from './canonical-json.js';

/** The export's manifest — the chain tip + count + timestamp; the holder's at-a-glance integrity head. */
export interface ExportManifest {
  auditKind: 'agentinvest-audit-export-manifest';
  /** The export-format version (v0.1 local hash-chain). */
  version: 'v0.1';
  /** The chain TIP — the final entry's chainHash (the SHA-256 fold of the whole sequence). */
  chainTip: string;
  /** The genesis seed the chain started from (documented; lets a verifier confirm the construction). */
  genesisSeed: string;
  /** The number of records in the export. */
  recordCount: number;
  /** When the export was produced (ISO-8601) — passed IN (never a clock inside a journaled path). */
  exportedAt: string;
  /** The JSON-L data file this manifest heads (basename). */
  dataFile: string;
}

/** The result of a write — the on-disk paths + the chain tip + count, for the caller's report. */
export interface WriteResult {
  /** Absolute path to the JSON-L data file. */
  dataPath: string;
  /** Absolute path to the manifest sidecar. */
  manifestPath: string;
  /** The chain tip written. */
  chainTip: string;
  /** The record count written. */
  recordCount: number;
}

/** The default export directory — a repo-tmp path, GITIGNORED (no committed audit data). */
export function defaultExportDir(): string {
  return process.env.AGENTINVEST_AUDIT_EXPORT_DIR ?? path.resolve(process.cwd(), '.audit-export');
}

/** Render the chained entries as JSON-L text (one canonical-JSON line per entry, trailing newline). */
export function entriesToJsonl(entries: readonly ChainEntry[]): string {
  if (entries.length === 0) return '';
  return entries.map((e) => canonicalJSON(e)).join('\n') + '\n';
}

/** A stable export basename derived from the (passed-in) timestamp — sortable, filename-safe. */
function exportBasename(exportedAt: string): string {
  const safe = exportedAt.replace(/[:.]/g, '-');
  return `audit-journal-${safe}`;
}

/**
 * Chain a list of records and WRITE the JSON-L export + manifest to the output dir.
 *
 * @param records   the records in deterministic chain order (the gather supplies this order).
 * @param exportedAt the export timestamp (ISO-8601) — passed IN; never a clock read here.
 * @param dir       the output directory (default `AGENTINVEST_AUDIT_EXPORT_DIR` / `.audit-export`).
 * @returns the on-disk paths + the chain tip + the record count.
 */
export async function writeJsonlExport<R>(
  records: readonly R[],
  exportedAt: string,
  dir: string = defaultExportDir(),
): Promise<WriteResult> {
  const entries = chainRecords(records);
  const tip = chainTip(entries);
  const base = exportBasename(exportedAt);
  const dataFile = `${base}.jsonl`;
  const manifestFile = `${base}.manifest.json`;
  const dataPath = path.resolve(dir, dataFile);
  const manifestPath = path.resolve(dir, manifestFile);

  const manifest: ExportManifest = {
    auditKind: 'agentinvest-audit-export-manifest',
    version: 'v0.1',
    chainTip: tip,
    genesisSeed: entries.length === 0 ? tip : entries[0].prevHash,
    recordCount: entries.length,
    exportedAt,
    dataFile,
  };

  await mkdir(dir, { recursive: true });
  await writeFile(dataPath, entriesToJsonl(entries), 'utf8');
  await writeFile(manifestPath, canonicalJSON(manifest) + '\n', 'utf8');

  return { dataPath, manifestPath, chainTip: tip, recordCount: entries.length };
}
