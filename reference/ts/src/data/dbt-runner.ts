/**
 * dbt-runner — the agentINVEST canonical-data-layer driver (OIM-102).
 *
 * Runs the dbt canonical-data pipeline (`reference/dbt/`, duckdb dev backend) by
 * invoking the workspace-level `scripts/dbt-build.mjs` launcher, which handles
 * the Windows->WSL2 hop and lands the duckdb file on WSL2-native ext4 (P-R2).
 * The CLI's `seed` subcommand and the `bootstrap` data-half both call this — so
 * `seed` is now REAL (it runs `dbt build`), not a stub.
 *
 * The dbt toolchain lives in the Python uv env (dbt-duckdb in the `dbt`
 * dependency group); this TS module does not import dbt — it shells out to the
 * launcher, the same pattern OIM-101 used for the cross-language smoke. The
 * canonical-data layer is a dbt store, NOT an "agent" (ADR-0054 vocabulary).
 */
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

// reference/ root = three dirs up from ts/src/data/.
const HERE = path.dirname(fileURLToPath(import.meta.url));
const REFERENCE_ROOT = path.resolve(HERE, '..', '..', '..');
const DBT_LAUNCHER = path.join(REFERENCE_ROOT, 'scripts', 'dbt-build.mjs');

/**
 * Run `dbt <args>` (default `build`) via scripts/dbt-build.mjs. Resolves with
 * the process exit code; rejects only on spawn failure. Inherits stdio so the
 * dbt output streams to the operator.
 */
export function runDbt(args: string[] = ['build']): Promise<number> {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [DBT_LAUNCHER, ...args], {
      stdio: 'inherit',
      env: process.env,
    });
    child.on('exit', (code) => resolve(code ?? 1));
    child.on('error', (err) => reject(err));
  });
}
