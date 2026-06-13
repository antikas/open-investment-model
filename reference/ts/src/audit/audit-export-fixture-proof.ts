/**
 * FIXTURE export proof — the full file-level pipeline (chain → write JSON-L + manifest →
 * verify green → tamper → verify RED) over a deterministic FIXTURE record set, exercising the REAL
 * production modules (`writeJsonlExport`, `verifyExportFile`) and the REAL CLI exit semantics.
 *
 * This is the CI/deterministic counterpart to the live proof: it does NOT need the running substrate.
 * It proves, on real files written by the real export code:
 *   1. the chain is well-formed + the manifest tip matches;
 *   2. the verifier passes the clean exported file (GREEN);
 *   3. an in-place tamper to the written JSON-L is DETECTED (RED, first-broken seq named);
 *   4. the export is byte-reproducible for the same records + timestamp (the determinism property).
 *
 * The fixture records mirror the two real audit-record shapes (an `operation-closed` record + a
 * `nav-published` record), so the normalisation + ordering + chaining are exercised on realistic
 * data. The live proof (`scripts/audit-export-live-proof.mjs`) proves the SAME pipeline over REAL
 * gathered records when the substrate is up; this proves it deterministically regardless.
 */
import { mkdtempSync, readFileSync, writeFileSync, rmSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { writeJsonlExport } from './jsonl-export.js';
import { verifyExportFile } from './verifier.js';
import { normaliseAuditRecord, orderAuditRecords } from './audit-record.js';

/** Run the REAL audit-verify CLI on a file; return its exit code (mask-immune assertion). */
function runVerifyCli(dataPath: string): number {
  const cliEntry = path.resolve(path.dirname(fileURLToPath(import.meta.url)), 'audit-verify-cli.ts');
  const r = spawnSync(process.execPath, ['--import', 'tsx', cliEntry, dataPath], {
    encoding: 'utf8',
    stdio: 'ignore',
  });
  return r.status ?? -1;
}

function out(line = ''): void {
  process.stdout.write(`${line}\n`);
}

/** Two fixture audit records mirroring the real shapes (operation-closed + nav-published). */
function fixtureRecords() {
  const opClosed = {
    kind: 'operation-closed',
    operationId: 'op-attr-PF0003-1',
    task: 'Performance attribution for PF-0003 by sector.',
    plan: { steps: [{ soId: 'SO-09-01', args: { fund: 'PF-0003' } }], riskScore: 0.05, summary: 'attribution' },
    aggregated: { kind: 'performance-attribution', coherent: true, totalReturn: '0.10' },
    gateDecision: { gated: false, riskScore: 0.05, approvedAwakeableId: null },
    status: 'completed',
  };
  const navPub = {
    kind: 'nav-published',
    workflowId: 'nav-PF0003-1',
    fundId: 'PF-0003',
    fundName: 'Multi-Asset Fund',
    navUsd: '125000000.00',
    martNavUsd: '125000000.00',
    approvedAwakeableId: 'prom_abc',
    struckAt: '2026-06-01T10:00:00.000Z',
  };
  const normalised = [opClosed, navPub]
    .map((r) => normaliseAuditRecord(r))
    .filter((r): r is NonNullable<typeof r> => r !== null);
  return orderAuditRecords(normalised);
}

async function main(): Promise<number> {
  const work = mkdtempSync(path.join(tmpdir(), 'agentinvest-audit-fixture-'));
  const exportedAt = '2026-06-03T00:00:00.000Z';
  try {
    const records = fixtureRecords();
    out(`[fixture-proof] ${records.length} fixture audit record(s) (operation-closed + nav-published).`);

    // 1. WRITE — the real export code writes the JSON-L + manifest.
    const w1 = await writeJsonlExport(records, exportedAt, work);
    out(`[fixture-proof] wrote ${w1.recordCount} record(s) → ${path.basename(w1.dataPath)} (tip ${w1.chainTip.slice(0, 12)}…)`);

    // 2. VERIFY CLEAN — GREEN.
    const clean = await verifyExportFile(w1.dataPath, w1.manifestPath);
    if (!clean.ok) throw new Error(`clean export did NOT verify: ${clean.reason}`);
    out(`[fixture-proof] (a) clean export VERIFIES GREEN — ${clean.entryCount} record(s), tip matches manifest. PASS`);

    // 3. REPRODUCIBILITY — same records + timestamp → byte-identical data file.
    const work2 = mkdtempSync(path.join(tmpdir(), 'agentinvest-audit-fixture2-'));
    const w2 = await writeJsonlExport(records, exportedAt, work2);
    const bytes1 = readFileSync(w1.dataPath, 'utf8');
    const bytes2 = readFileSync(w2.dataPath, 'utf8');
    if (bytes1 !== bytes2 || w1.chainTip !== w2.chainTip) {
      throw new Error('export is NOT reproducible: two runs over the same records+timestamp differ.');
    }
    out(`[fixture-proof] (b) export is BYTE-REPRODUCIBLE (same records+timestamp → identical file + tip). PASS`);
    rmSync(work2, { recursive: true, force: true });

    // 4. TAMPER — edit a field in the written JSON-L; the verifier must DETECT it (RED).
    const lines = bytes1.split('\n').filter((l) => l.trim().length > 0);
    const parsed = JSON.parse(lines[0]);
    parsed.record.source.navUsd = '999999999.99'; // forge a NAV (or task) field in place
    // (the first ordered record is the nav-published one — occurredAt sorts it first)
    lines[0] = JSON.stringify(parsed);
    const tamperedPath = path.join(work, 'tampered.jsonl');
    writeFileSync(tamperedPath, lines.join('\n') + '\n', 'utf8');
    const tampered = await verifyExportFile(tamperedPath, w1.manifestPath);
    if (tampered.ok) throw new Error('TAMPER NOT DETECTED — a modified field passed the verifier (revert regression!).');
    out(
      `[fixture-proof] (c) in-place TAMPER DETECTED — ok=false, firstBrokenSeq=${tampered.firstBrokenSeq}, ` +
        `class=${tampered.tamperClass}. PASS`,
    );

    // 5. CLI MASK-IMMUNE EXIT — the real audit-verify CLI exits 0 on the clean file, non-zero on the
    // tampered file (the exit derived from the result, never hard-coded).
    const cleanExit = runVerifyCli(w1.dataPath);
    const tamperExit = runVerifyCli(tamperedPath);
    if (cleanExit !== 0) throw new Error(`audit-verify CLI did NOT exit 0 on the clean file (exit ${cleanExit}).`);
    if (tamperExit === 0) throw new Error(`audit-verify CLI exited 0 on the TAMPERED file (mask regression!).`);
    out(`[fixture-proof] (d) audit-verify CLI MASK-IMMUNE — clean exit ${cleanExit}, tampered exit ${tamperExit}. PASS`);

    out('');
    out('[fixture-proof] FIXTURE EXPORT PIPELINE PROVEN: clean=GREEN, reproducible, tamper=RED, CLI mask-immune.');
    return 0;
  } finally {
    rmSync(work, { recursive: true, force: true });
  }
}

main()
  .then((code) => process.exit(code))
  .catch((err: unknown) => {
    process.stderr.write(`[fixture-proof] ${err instanceof Error ? err.message : String(err)}\n`);
    process.exit(1);
  });
