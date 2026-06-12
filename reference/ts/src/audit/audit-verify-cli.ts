/**
 * `pnpm audit-verify <file>` — the tamper-detecting verifier CLI (OIM-151 part 4).
 *
 * Reads a JSON-L audit export, recomputes the SHA-256 hash chain, and reports whether the chain is
 * intact. On a tampered chain it names the FIRST broken `seq` + the tamper class + a human reason,
 * and exits NON-ZERO. On a clean chain it prints the verified tip + count and exits 0.
 *
 * MASK-IMMUNE EXIT. The exit code is DERIVED from the verification result (`ok` → 0; tampered → 1) —
 * never hard-coded. A loosened recompute that returned `ok` on a tampered chain would make the
 * tamper tests (and a real audit) go GREEN that should be RED; the tests pin this.
 *
 * MANIFEST. If a manifest sidecar (`<base>.manifest.json`) sits beside the data file, it is read and
 * its claimed `chainTip` is cross-checked against the recomputed tip (the forged-tip detection).
 *
 * HONEST BOUNDARY (v0.1). The verifier catches an in-place EDIT to a stored record. It does NOT
 * detect a fully RE-CHAINED forgery (a file holder re-folding a forged record set from the public
 * genesis seed) — that is the S3 object-lock immutability of v0.2. Tamper-EVIDENCE, not prevention.
 */
import path from 'node:path';
import { existsSync } from 'node:fs';
import { verifyExportFile } from './verifier.js';

const CLI = 'audit-verify';

function out(line = ''): void {
  process.stdout.write(`${line}\n`);
}
function err(line = ''): void {
  process.stderr.write(`${line}\n`);
}

const HELP = `${CLI} — verify a hash-chained audit-journal export (OIM-151 v0.1)

USAGE
  pnpm audit-verify <export.jsonl> [--manifest <manifest.json>]

WHAT IT DOES
  Reads the JSON-L export, recomputes the SHA-256 hash chain from the records, and DETECTS
  tampering: a modified field, an inserted/deleted/reordered line, a broken link, or a forged
  manifest tip. Names the first broken seq + the tamper class. Exits NON-ZERO on a tampered chain
  (mask-immune — the exit is derived from the result), 0 on a clean chain.

OPTIONS
  --manifest <path>   The manifest sidecar (default: <export>.manifest.json beside the data file,
                      if it exists). The manifest's claimed tip is cross-checked (forged-tip catch).
  -h, --help          Show this help.

HONEST BOUNDARY (v0.1)
  Catches an in-place EDIT to a stored record. Does NOT detect a fully re-chained forgery (a file
  holder re-folding a forged record set from the public genesis seed) or a deleted file — that is
  the S3 object-lock immutability of v0.2. Tamper-EVIDENCE, not tamper-PREVENTION.`;

/** Derive the default manifest path beside the data file (<base>.manifest.json), if it exists. */
function defaultManifestFor(dataPath: string): string | null {
  const dir = path.dirname(dataPath);
  const base = path.basename(dataPath).replace(/\.jsonl$/i, '');
  const candidate = path.resolve(dir, `${base}.manifest.json`);
  return existsSync(candidate) ? candidate : null;
}

async function main(): Promise<number> {
  const args = process.argv.slice(2);
  if (args.length === 0 || args.includes('-h') || args.includes('--help')) {
    out(HELP);
    return args.length === 0 ? 2 : 0;
  }

  const manIdx = args.indexOf('--manifest');
  const explicitManifest = manIdx >= 0 && manIdx + 1 < args.length ? args[manIdx + 1] : null;
  // The first positional (non-flag) arg is the data file. Exclude the manifest VALUE index only
  // when --manifest is actually present (manIdx >= 0) — otherwise manIdx+1 === 0 would wrongly
  // exclude the first positional.
  const manifestValueIdx = manIdx >= 0 ? manIdx + 1 : -1;
  const dataPath = args.find((a, i) => !a.startsWith('-') && i !== manifestValueIdx);
  if (!dataPath) {
    err(`${CLI}: no export file given. Run '${CLI} --help'.`);
    return 2;
  }
  if (!existsSync(dataPath)) {
    err(`${CLI}: export file not found: ${dataPath}`);
    return 2;
  }

  const manifestPath = explicitManifest ?? defaultManifestFor(dataPath);

  out(`[${CLI}] verifying ${dataPath}${manifestPath ? ` (manifest ${manifestPath})` : ''}...`);
  const result = await verifyExportFile(dataPath, manifestPath);

  if (result.ok) {
    out('');
    out(`[${CLI}] CHAIN VERIFIED — ${result.entryCount} record(s), no in-chain tampering detected.`);
    out(`  recomputed tip: ${result.recomputedTip}`);
    if (result.manifestPresent && result.manifestTip) {
      // Manifest present + the tip verified (else result.ok would be false): a fully-clean pass.
      out(`  manifest tip:   ${result.manifestTip} (matches — tip anchor verified)`);
    }
    // Surface any advisories. The no-manifest warning means this is NOT a fully-clean pass: the
    // tip-anchor class went unchecked, so a tip-append/truncation could not be detected.
    for (const w of result.warnings) {
      out('');
      out(`[${CLI}] WARNING — ${w}`);
    }
    if (result.warnings.length > 0) {
      out(`  supply the manifest sidecar (--manifest <file>) to verify the tip anchor too.`);
    }
    // Mask-immune: exit derived from result.ok.
    return 0;
  }

  err('');
  err(`[${CLI}] CHAIN TAMPERING DETECTED.`);
  err(`  first broken seq: ${result.firstBrokenSeq}`);
  err(`  tamper class:     ${result.tamperClass}`);
  err(`  reason:           ${result.reason}`);
  if (result.recomputedTip) err(`  recomputed tip:   ${result.recomputedTip}`);
  if (result.manifestTip) err(`  manifest tip:     ${result.manifestTip}`);
  for (const w of result.warnings) {
    err('');
    err(`[${CLI}] WARNING — ${w}`);
  }
  // Mask-immune: exit derived from result.ok (a tampered chain is a non-zero exit).
  return 1;
}

main()
  .then((code) => process.exit(code))
  .catch((e: unknown) => {
    const msg = e instanceof Error ? e.message : String(e);
    process.stderr.write(`${CLI}: ${msg}\n`);
    process.exit(1);
  });
