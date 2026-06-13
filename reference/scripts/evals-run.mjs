#!/usr/bin/env node
/**
 * evals-run.mjs — run the eval harness.
 *
 * Runs the offline, deterministic, replay-stable golden-set runner
 * (`python -m agentinvest_evals`) for the agentINVEST eval substrate. The harness
 * lives in the reference/python/ uv env (the agentinvest_evals package); it has
 * no Restate and no dbt dependency, so it runs in the base venv.
 *
 * Platform split (same as dbt-build.mjs / the cross-language smoke): on Windows
 * the uv/Python layer runs INSIDE WSL2 (the financial-data Python ecosystem is
 * Linux-native; the venv lands on WSL2 ext4). On Mac/Linux it runs locally.
 *
 * Exit code is the harness's: 0 iff the selector accuracy >= the declared bar,
 * non-zero on a bar miss (CI-gate-ready) or a malformed/one-sided set.
 *
 * Args after `--` are forwarded to the harness (e.g. `pnpm evals -- --check-replay`).
 *
 * Run:  node scripts/evals-run.mjs   (from reference/)  or  pnpm evals
 */
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REFERENCE_ROOT = path.resolve(__dirname, '..');
const isWin = process.platform === 'win32';
const WSL_DISTRO = process.env.RESTATE_WSL_DISTRO ?? 'Ubuntu-24.04';

const harnessArgs = process.argv.slice(2);

function log(line) {
  process.stderr.write(`[evals-run] ${line}\n`);
}

function toWslPath(winAbs) {
  // X:\path\to\repo -> /mnt/x/path/to/repo
  return '/mnt/' + winAbs[0].toLowerCase() + winAbs.slice(2).replace(/\\/g, '/');
}

function run() {
  let cmd;
  let args;
  const passEnv = { ...process.env, WSL_UTF8: '1' };

  if (isWin) {
    const refWsl = toWslPath(REFERENCE_ROOT);
    const scriptWsl = `${refWsl}/scripts/evals-run.sh`;
    cmd = 'wsl';
    args = ['-d', WSL_DISTRO, '-e', 'bash', scriptWsl, ...harnessArgs];
    passEnv.REFERENCE_ROOT_WSL = refWsl;
    const extra = process.env.UV_PROJECT_ENVIRONMENT ? ':UV_PROJECT_ENVIRONMENT' : '';
    passEnv.WSLENV = `REFERENCE_ROOT_WSL${extra}:${process.env.WSLENV ?? ''}`;
  } else {
    const scriptNative = path.join(REFERENCE_ROOT, 'scripts', 'evals-run.sh');
    cmd = 'bash';
    args = [scriptNative, ...harnessArgs];
    passEnv.REFERENCE_ROOT_WSL = REFERENCE_ROOT;
  }

  log('running: python -m agentinvest_evals ' + harnessArgs.join(' '));
  const child = spawn(cmd, args, { stdio: 'inherit', env: passEnv });
  child.on('exit', (code) => process.exit(code ?? 1));
  child.on('error', (err) => {
    log(`ERROR: ${err.message}`);
    process.exit(1);
  });
}

run();
