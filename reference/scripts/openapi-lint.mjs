#!/usr/bin/env node
/**
 * Spectral lint gate for the agentINVEST bd09 OpenAPI surface.
 *
 * WHAT IT DOES. `openapi-spec-validator` (the Python surface) checks the spec is
 * STRUCTURALLY a valid OpenAPI 3.1 document. This gate runs Spectral's built-in
 * `spectral:oas` STYLE/QUALITY ruleset (via reference/.spectral.yaml, whose every
 * exception is tied to a Restate emitter quirk — see the comments there) against:
 *
 *   1. the committed CAPTURED-FIXTURE spec (python/tests/fixtures/bd09-openapi.captured.json)
 *      — the deterministic, server-free CI gate. This fixture is the genuine NORMALISED
 *      Restate emitter output captured from the live bd09 service (never hand-trimmed to
 *      hide a defect); a Python test (test_openapi_lint_fixture.py) asserts it still
 *      validates as 3.1 + carries the typed envelope, so it cannot silently drift from
 *      the real surface.
 *   2. the LIVE spec, IF the substrate is up and bd09 is registered — fetched from the
 *      Restate admin API and normalised via the SAME surface normaliser, then linted.
 *      Corroborates that the real, currently-emitted spec lints clean too. Skipped
 *      (not failed) when the substrate / bd09 is unreachable.
 *
 * MASK-IMMUNE SUCCESS ORACLE. The PASS/FAIL is derived STRUCTURALLY from
 * Spectral's OWN machine-readable results, not from a wrapped `pnpm`/`uv` exit that a
 * shell could mask. For each target Spectral writes its findings as JSON to a file
 * (`--format json --output`); this script PARSES that file and PASSes a target iff
 * (a) the results file exists and parses as a JSON array AND (b) it contains ZERO
 * error-severity (severity 0) findings. Spectral's process exit code (non-zero on an
 * error-severity finding) is checked as a SECONDARY corroboration only. The gate
 * prints a single sentinel `OPENAPI_LINT_RESULT: PASS|FAIL` derived from the parsed
 * results across every target — that sentinel is the oracle, not this script's own
 * exit (which mirrors it).
 *
 * Run (from reference/):  node scripts/openapi-lint.mjs   (or: pnpm openapi:lint)
 */
import { spawnSync } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REFERENCE_ROOT = path.resolve(__dirname, '..');
const REPO_ROOT = path.resolve(REFERENCE_ROOT, '..');
const RULESET = path.join(REFERENCE_ROOT, '.spectral.yaml');
const FIXTURE = path.join(
  REFERENCE_ROOT,
  'python',
  'tests',
  'fixtures',
  'bd09-openapi.captured.json',
);
const SPECTRAL_BIN = path.join(
  REFERENCE_ROOT,
  'node_modules',
  '.bin',
  process.platform === 'win32' ? 'spectral.cmd' : 'spectral',
);

const ADMIN_URL = process.env.RESTATE_ADMIN_URL ?? 'http://localhost:9070';
const BD09_SERVICE = 'bd09';
const isWin = process.platform === 'win32';
const WSL_DISTRO = process.env.RESTATE_WSL_DISTRO ?? 'Ubuntu-24.04';

// Work dir UNDER the reference root (not the OS tmp) so the path is reachable both
// from the Windows-side Spectral process AND the WSL-side Python normaliser via the
// /mnt mount (mirrored networking) — avoids the %TEMP%-vs-/tmp split. Cleaned up on exit.
const work = mkdtempSync(path.join(REFERENCE_ROOT, '.oim141-spectral-'));

function log(line) {
  process.stderr.write(`[openapi-lint] ${line}\n`);
}

/**
 * Lint one spec file with Spectral and derive PASS/FAIL from Spectral's OWN JSON
 * results (mask-immune): parse the results file, count error-severity findings.
 * Returns { ok, errorCount, warnCount, exit, findings }.
 */
function lintSpec(specPath, label) {
  const outFile = path.join(work, `spectral-${label}.json`);
  const res = spawnSync(
    SPECTRAL_BIN,
    ['lint', specPath, '--ruleset', RULESET, '--format', 'json', '--output', outFile],
    // shell:true on Windows so the .cmd shim resolves; the args are repo-internal
    // paths (no user input), so no injection surface.
    { encoding: 'utf8', shell: isWin },
  );
  // PRIMARY oracle: Spectral's structured results, not the wrapped exit code.
  if (!existsSync(outFile)) {
    log(`${label}: Spectral wrote no results file — treating as FAIL (stderr: ${res.stderr?.trim()})`);
    return { ok: false, errorCount: -1, warnCount: -1, exit: res.status, findings: [] };
  }
  let findings;
  try {
    findings = JSON.parse(readFileSync(outFile, 'utf8'));
  } catch (err) {
    log(`${label}: Spectral results did not parse as JSON — FAIL (${err.message})`);
    return { ok: false, errorCount: -1, warnCount: -1, exit: res.status, findings: [] };
  }
  if (!Array.isArray(findings)) {
    log(`${label}: Spectral results were not an array — FAIL`);
    return { ok: false, errorCount: -1, warnCount: -1, exit: res.status, findings: [] };
  }
  const errorCount = findings.filter((f) => f.severity === 0).length;
  const warnCount = findings.filter((f) => f.severity === 1).length;
  // SECONDARY corroboration: Spectral exits non-zero iff it found an error-severity result.
  const exitAgrees = (errorCount > 0) === (res.status !== 0);
  if (!exitAgrees) {
    log(
      `${label}: WARNING — Spectral exit (${res.status}) disagrees with parsed error count ` +
        `(${errorCount}); trusting the parsed results (the mask-immune oracle).`,
    );
  }
  const ok = errorCount === 0;
  log(
    `${label}: ${ok ? 'CLEAN' : 'FAIL'} — ${errorCount} error(s), ${warnCount} warning(s) ` +
      `(spectral exit ${res.status})`,
  );
  if (!ok) {
    for (const f of findings.filter((x) => x.severity === 0)) {
      log(`    ERROR ${f.code} @ ${(f.path ?? []).join('.')}: ${f.message}`);
    }
  }
  return { ok, errorCount, warnCount, exit: res.status, findings };
}

/** Is the shared Restate admin reachable AND bd09 registered? */
async function bd09Reachable() {
  try {
    const r = await fetch(`${ADMIN_URL}/services/${BD09_SERVICE}/openapi`, {
      signal: AbortSignal.timeout(3000),
    });
    return r.ok;
  } catch {
    return false;
  }
}

/**
 * Fetch the live bd09 spec, normalise it via the SAME Python surface normaliser
 * (so the lint target is the genuine emitter output, normalised exactly as the
 * surface serves it), and write it to a temp file. Returns the path, or null if
 * the normalise step is unavailable. Reuse-safe: read-only, spawns nothing on
 * the shared substrate.
 */
function captureLiveNormalised() {
  const outPath = path.join(work, 'bd09-live-normalised.json');
  // The path the Python process writes to: the WSL /mnt mount on Windows, the
  // native path on Linux. The Windows-side node then reads outPath (same file).
  const pyOut = isWin ? toWsl(outPath) : outPath;
  const py =
    'import json;' +
    'from agentinvest_tools.openapi_surface import fetch_service_openapi, normalise_emitter_quirks, validate_openapi_spec;' +
    "spec=fetch_service_openapi('bd09');" +
    'validate_openapi_spec(spec);' +
    'norm=normalise_emitter_quirks(spec);' +
    `open(${JSON.stringify(pyOut)},'w').write(json.dumps(norm));` +
    "print('OK')";
  let res;
  if (isWin) {
    const wslRef = toWsl(REFERENCE_ROOT);
    const repo = toWsl(REPO_ROOT);
    const prelude =
      `export PATH="$HOME/.local/bin:$PATH"; ` +
      `tr -d '\\r' < ${wslRef}/scripts/lib/agentinvest-venv-path.sh > /tmp/agentinvest-venv-path.sh; ` +
      `. /tmp/agentinvest-venv-path.sh; agentinvest_set_venv_env '${repo}'; cd ${wslRef}/python`;
    res = spawnSync(
      'wsl',
      ['-d', WSL_DISTRO, '--', 'bash', '-lc', `${prelude} && uv run python -c ${shq(py)}`],
      { encoding: 'utf8', env: { ...process.env, WSL_UTF8: '1' } },
    );
  } else {
    res = spawnSync(
      'bash',
      [
        '-lc',
        `export PATH="$HOME/.local/bin:$PATH" && cd ${REFERENCE_ROOT}/python && uv run python -c ${shq(py)}`,
      ],
      { encoding: 'utf8' },
    );
  }
  if (res.status !== 0 || !existsSync(outPath)) {
    log(`live normalise unavailable (${res.stderr?.trim() ?? 'no output'}); linting the fixture only.`);
    return null;
  }
  return outPath;
}

function toWsl(p) {
  return '/mnt/' + p[0].toLowerCase() + p.slice(2).replace(/\\/g, '/');
}
function shq(s) {
  return `'${s.replace(/'/g, `'\\''`)}'`;
}

async function main() {
  if (!existsSync(SPECTRAL_BIN)) {
    log(`Spectral CLI not found at ${SPECTRAL_BIN}. Run \`pnpm install\` (adds @stoplight/spectral-cli).`);
    finish(false);
    return;
  }
  if (!existsSync(FIXTURE)) {
    log(`captured-fixture spec missing at ${FIXTURE} — cannot run the deterministic CI gate.`);
    finish(false);
    return;
  }

  const targets = [];

  // 1. The deterministic CI gate — the committed captured fixture.
  log(`linting the captured fixture: ${FIXTURE}`);
  targets.push({ label: 'fixture', result: lintSpec(FIXTURE, 'fixture') });

  // 2. The live spec, IF reachable (corroboration; reuse-safe read-only).
  if (await bd09Reachable()) {
    log('shared Restate admin reachable + bd09 registered — also linting the LIVE spec.');
    const livePath = captureLiveNormalised();
    if (livePath) {
      targets.push({ label: 'live', result: lintSpec(livePath, 'live') });
    }
  } else {
    log('shared Restate admin / bd09 not reachable — linting the fixture only (CI-safe; live skipped).');
  }

  const allClean = targets.every((t) => t.result.ok);
  log('');
  log('summary:');
  for (const t of targets) {
    log(
      `  ${t.label}: ${t.result.ok ? 'CLEAN' : 'FAIL'} ` +
        `(${t.result.errorCount} error, ${t.result.warnCount} warn)`,
    );
  }
  finish(allClean);
}

function finish(pass) {
  try {
    rmSync(work, { recursive: true, force: true });
  } catch {
    /* best-effort */
  }
  // The sentinel IS the oracle; this script's exit mirrors it.
  process.stdout.write(`OPENAPI_LINT_RESULT: ${pass ? 'PASS' : 'FAIL'}\n`);
  process.exit(pass ? 0 : 1);
}

main().catch((err) => {
  log(`ERROR: ${err.message}`);
  finish(false);
});
