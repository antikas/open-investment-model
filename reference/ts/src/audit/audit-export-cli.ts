/**
 * `pnpm audit-export` — the invokable audit-journal export CLI.
 *
 * Runs the GATHER → CHAIN → WRITE pipeline: enumerate the real agentINVEST audit records over the
 * authoritative admin-API + ingress read path, hash-chain them, and write a JSON-L export + a
 * chain-tip manifest to the local output dir (`AGENTINVEST_AUDIT_EXPORT_DIR`). The export is
 * runnable NOW; the NIGHTLY CRON trigger is DEFERRED (deploy-surface) — this builds it
 * invokable, the scheduler wires it later.
 *
 * S3 IS DEFERRED (v0.2). This writes a LOCAL file (tamper-EVIDENCE — the chain makes an edit
 * detectable). It is NOT tamper-PREVENTION: the local file can be deleted/replaced; the S3
 * object-lock write-once-immutable store is the deferred v0.2 layer. Do not imply immutability.
 *
 * The export timestamp is a real clock here (a CLI is not a journaled Restate path, so `new Date()`
 * is fine — the journaling discipline forbids a clock only inside a `ctx.run`/handler closure).
 *
 * Exit codes: 0 = export written; 1 = a runtime failure.
 */
import { gatherAuditRecords, defaultEndpoints } from './gather.js';
import { writeJsonlExport, defaultExportDir } from './jsonl-export.js';

const CLI = 'audit-export';

function out(line = ''): void {
  process.stdout.write(`${line}\n`);
}

const HELP = `${CLI} — export the agentINVEST audit journal as a hash-chained JSON-L file (v0.1)

USAGE
  pnpm audit-export [--dir <path>]

WHAT IT DOES
  1. GATHER — enumerates the real audit records (the investmentOperation 'operation-closed'
     records + the navCalculation 'nav-published' records) via the admin API (key enumeration)
     + the ingress (state reads) — READ-ONLY.
  2. CHAIN  — folds them (in deterministic order) into a SHA-256 hash chain
     (chainHash = sha256(prevHash || canonicalJSON(record)), documented genesis seed).
  3. WRITE  — writes the chained entries as JSON-L + a chain-tip manifest to the output dir.

OPTIONS
  --dir <path>   Output directory (default env AGENTINVEST_AUDIT_EXPORT_DIR or ./.audit-export).
  -h, --help     Show this help.

VERIFY THE EXPORT
  pnpm audit-verify <the-written-.jsonl>

HONEST BOUNDARY (v0.1)
  This is tamper-EVIDENCE, NOT tamper-PREVENTION. The hash chain makes an in-place edit to an
  exported record DETECTABLE (the verifier names the first broken seq). It does NOT make the
  export immutable: the local file can be deleted/replaced, and a file holder can re-chain a
  forged record set from the public genesis seed. S3 object-lock write-once-immutability (which
  prevents deletion) + the nightly cron are DEFERRED to v0.2/deploy.

PREREQUISITE (for a non-empty export)
  The shared Restate must be up and the agentINVEST handlers registered, with at least one
  completed operation/strike. With nothing to gather it writes an empty (genesis-only) export.`;

async function main(): Promise<number> {
  const args = process.argv.slice(2);
  if (args.includes('-h') || args.includes('--help')) {
    out(HELP);
    return 0;
  }
  const dirIdx = args.indexOf('--dir');
  const dir = dirIdx >= 0 && dirIdx + 1 < args.length ? args[dirIdx + 1] : defaultExportDir();

  const endpoints = defaultEndpoints();
  out(`[${CLI}] gathering audit records (admin ${endpoints.adminUrl}, ingress ${endpoints.ingressUrl})...`);
  const gathered = await gatherAuditRecords(endpoints);
  out(
    `[${CLI}] gathered ${gathered.records.length} audit record(s) ` +
      `(${gathered.keysSeen} operation key(s) seen, ${gathered.statesRead} state(s) read).`,
  );

  // The export timestamp — a real clock (a CLI, not a journaled path).
  const exportedAt = new Date().toISOString();
  const result = await writeJsonlExport(gathered.records, exportedAt, dir);

  out('');
  out(`[${CLI}] EXPORT WRITTEN:`);
  out(`  data:     ${result.dataPath}`);
  out(`  manifest: ${result.manifestPath}`);
  out(`  records:  ${result.recordCount}`);
  out(`  chainTip: ${result.chainTip}`);
  out('');
  out(`[${CLI}] verify it:  pnpm audit-verify ${result.dataPath}`);
  out(
    `[${CLI}] NOTE (v0.1): tamper-EVIDENCE, not tamper-PREVENTION — the local file can be deleted/` +
      `replaced; S3 object-lock immutability is deferred to v0.2.`,
  );
  return 0;
}

main()
  .then((code) => process.exit(code))
  .catch((err: unknown) => {
    const msg = err instanceof Error ? err.message : String(err);
    process.stderr.write(`${CLI}: ${msg}\n`);
    process.exit(1);
  });
