#!/usr/bin/env node
/**
 * dbt-build.mjs (OIM-102) — run the canonical-data dbt pipeline.
 *
 * Runs `dbt build` (seed + run + test) for the agentINVEST canonical data layer
 * at reference/dbt/, on the duckdb dev backend. The dbt toolchain lives in the
 * reference/python/ uv env (dbt-duckdb in the `dbt` dependency group).
 *
 * Platform split (same as the cross-language smoke, OIM-101): on Windows the
 * dbt/uv layer runs INSIDE WSL2 (the financial-data Python ecosystem is
 * Linux-native; the duckdb file lands on WSL2-native ext4). On Mac/Linux it runs
 * locally. Either way:
 *
 *   1. the duckdb DATABASE FILE is created on ext4 (P-R2) — NOT on the 9p
 *      /mnt/d repo mount (a duckdb locking/perf hazard). The path is an explicit
 *      AGENTINVEST_DUCKDB_PATH override, else a CHECKOUT-KEYED ext4 default that
 *      dbt-build.sh computes from this checkout's repo root (OIM-110 cycle-2:
 *      `~/.local/share/agentinvest/duckdb/canonical-<token>.duckdb`), so
 *      concurrent checkouts / CI do not collide on duckdb's single-writer lock;
 *   2. DBT_PROFILES_DIR is set to reference/dbt/ so a fresh checkout resolves
 *      the committed profiles.yml with no ~/.dbt/profiles.yml;
 *   3. the dbt *source* stays in the repo; only the materialised db file is on
 *      ext4 (gitignored).
 *
 * Args after `--` are forwarded to dbt (e.g. `node scripts/dbt-build.mjs -- --select staging`).
 *
 * Run:  node scripts/dbt-build.mjs   (from reference/)  or  pnpm dbt:build
 */
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REFERENCE_ROOT = path.resolve(__dirname, '..');
const isWin = process.platform === 'win32';
const WSL_DISTRO = process.env.RESTATE_WSL_DISTRO ?? 'Ubuntu-24.04';

const dbtArgs = process.argv.slice(2);

function log(line) {
  process.stderr.write(`[dbt-build] ${line}\n`);
}

function toWslPath(winAbs) {
  // X:\path\to\repo -> /mnt/x/path/to/repo
  return '/mnt/' + winAbs[0].toLowerCase() + winAbs.slice(2).replace(/\\/g, '/');
}

/**
 * Delegate to scripts/dbt-build.sh inside the uv env. The real shell logic lives
 * in the .sh file (a tracked script), so the command survives the Node -> wsl ->
 * bash argv boundary without quote mangling. We pass:
 *   - REFERENCE_ROOT_WSL  so the .sh resolves python/ + dbt/ as WSL2 paths;
 *   - the duckdb ext4 path (P-R2) if the caller overrode it via env;
 *   - dbt args (default `build`) forwarded straight through.
 */
function run() {
  const dbtArgsDesc = dbtArgs.length > 0 ? dbtArgs.join(' ') : 'build';
  let cmd;
  let args;
  const passEnv = { ...process.env, WSL_UTF8: '1' };

  if (isWin) {
    const refWsl = toWslPath(REFERENCE_ROOT);
    const scriptWsl = `${refWsl}/scripts/dbt-build.sh`;
    cmd = 'wsl';
    // -e bash <script> <args...> ; REFERENCE_ROOT_WSL passed via env to the distro.
    args = ['-d', WSL_DISTRO, '-e', 'bash', scriptWsl, ...dbtArgs];
    // WSLENV exports the named Windows env vars into the WSL2 process. An
    // explicit UV_PROJECT_ENVIRONMENT override is forwarded too (OIM-107); when
    // unset, dbt-build.sh defaults it to the ext4 path inside WSL2.
    passEnv.REFERENCE_ROOT_WSL = refWsl;
    const extra =
      (process.env.AGENTINVEST_DUCKDB_PATH ? ':AGENTINVEST_DUCKDB_PATH' : '') +
      (process.env.UV_PROJECT_ENVIRONMENT ? ':UV_PROJECT_ENVIRONMENT' : '');
    passEnv.WSLENV = `REFERENCE_ROOT_WSL${extra}:${process.env.WSLENV ?? ''}`;
  } else {
    const scriptNative = path.join(REFERENCE_ROOT, 'scripts', 'dbt-build.sh');
    cmd = 'bash';
    args = [scriptNative, ...dbtArgs];
    passEnv.REFERENCE_ROOT_WSL = REFERENCE_ROOT;
  }

  log(`running: dbt ${dbtArgsDesc}`);
  log(`duckdb file lands on WSL2-native ext4 (P-R2) — checkout-keyed default under $HOME/.local/share/agentinvest/duckdb/`);
  const child = spawn(cmd, args, { stdio: 'inherit', env: passEnv });
  child.on('exit', (code) => process.exit(code ?? 1));
  child.on('error', (err) => {
    log(`ERROR: ${err.message}`);
    process.exit(1);
  });
}

run();
