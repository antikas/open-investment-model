#!/usr/bin/env bash
# dbt-build.sh — run the canonical-data dbt pipeline in the WSL2/local
# uv env. Invoked by scripts/dbt-build.mjs (which handles the Windows->WSL2
# hop and forwards dbt args). Kept as a real script file so the command survives
# the Node -> wsl -> bash boundary without quote mangling.
#
# Env in (set by dbt-build.mjs, with defaults here for direct invocation):
#   REFERENCE_ROOT_WSL      absolute WSL2/local path to reference/ (default: derived)
#   AGENTINVEST_DUCKDB_PATH the duckdb FILE path on ext4; when unset,
#                           defaulted to a checkout-keyed ext4 path (see below)
# Args: forwarded to `dbt` (default: build).
set -euo pipefail

export PATH="$HOME/.local/bin:$PATH"

# Resolve reference/ root: explicit env, else two dirs up from this script.
if [ -z "${REFERENCE_ROOT_WSL:-}" ]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  REFERENCE_ROOT_WSL="$(cd "$SCRIPT_DIR/.." && pwd)"
fi
PYTHON_DIR="$REFERENCE_ROOT_WSL/python"
DBT_DIR="$REFERENCE_ROOT_WSL/dbt"

# The uv project environment lands on WSL2-native ext4, NOT the
# 9p /mnt/d repo mount. The Python+dbt SOURCE stays in the repo (9p) and is read
# at parse; the heavy site-packages import I/O (dbt-core + the duckdb adapter +
# ~485 macros) runs from ext4 — the cold `dbt --version` drops from ~22s (9p) to
# ~4s (ext4), under the <30s clean-checkout budget.
#
# The path is keyed on THIS checkout's repo root: two
# checkouts/worktrees get distinct venvs, so a concurrent checkout / CI run cannot
# share-and-clobber one venv. Still on ext4 under the same agentinvest parent —
# the perf win is preserved. An explicit UV_PROJECT_ENVIRONMENT (set by
# the caller, e.g. a native-Linux CI runner) still wins. See lib/agentinvest-venv-path.sh.
LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib"
# shellcheck source=lib/agentinvest-venv-path.sh
. "$LIB_DIR/agentinvest-venv-path.sh"
REPO_ROOT_WSL="$(cd "$REFERENCE_ROOT_WSL/.." && pwd)"
agentinvest_set_venv_env "$REPO_ROOT_WSL"

# The duckdb database file on WSL2-native ext4 — NOT the 9p /mnt/d mount.
# Keyed on THIS checkout's repo root: two checkouts/worktrees get distinct duckdb
# files, so a concurrent checkout / CI run cannot collide on duckdb's single-writer
# file lock (the same shared-state class the venv keying above closes; the SAME
# repo-root token keys both). Still on ext4 under the same agentinvest parent — the
# ext4 placement is preserved. An explicit AGENTINVEST_DUCKDB_PATH still wins. See
# lib/agentinvest-venv-path.sh.
agentinvest_set_duckdb_env "$REPO_ROOT_WSL"

export DBT_PROFILES_DIR="$DBT_DIR"

# Default subcommand is `build`.
DBT_ARGS=("$@")
if [ "${#DBT_ARGS[@]}" -eq 0 ]; then
  DBT_ARGS=(build)
fi

cd "$PYTHON_DIR"
# Mask-immunity: in this WSL2 launch env `uv run`
# intermittently masks a non-zero child exit to 0 (invocation-form-dependent —
# `bash -lc '… && uv run …'` masks because the `&&` stops `uv run` being the
# exec'd leaf), so the `uv run` exit code is NOT a trustworthy success oracle for a
# dbt build failure. We therefore do NOT `exec uv run` and trust its exit; instead
# we run it capturing the output, tee it to the caller's stderr (the dbt log
# stays fully visible), and derive success from dbt's OWN completion signal — the
# canonical, mask-immune line dbt prints to stdout (`Completed successfully` on a
# clean build; `Completed with N error(s)` / a `*** Error` / `Database Error` /
# `Compilation Error` / a non-zero `ERROR=` in the `Done.` summary on a failure).
# uv can mask the exit code but it cannot eat dbt's stdout; only the success-signal
# plumbing is made mask-immune. Pin uv's project dir explicitly (--directory
# "$PYTHON_DIR"), not just the cwd above, so a glitched invocation can NEVER fall
# back to the repo-root cwd and write a stray pyproject.toml/uv.lock there (leak-guard).
#
# Capture BOTH dbt streams (2>&1): dbt prints the clean-completion line + the
# `Done.` summary to stdout, but a Compilation/Database Error banner to stderr — we
# want every dbt signal visible to the parse. The merged stream is tee'd to the
# caller's stderr (always inherited; non-blocking — unlike a write to /dev/tty,
# which can block in a detached/CI context even when a pty exists), so the operator
# still sees the full live dbt log, while a copy is captured for the parse.
#
# CRITICAL: the capture is wrapped so `set -e` can NEVER abort the
# script on the assignment line. If `uv run` exits non-zero, a bare
# `VAR="$(uv run … )"` under `set -e` dies on the assignment with `uv run`'s OWN
# (maskable, untrustworthy) exit code BEFORE the parse runs — re-coupling the gate
# to the exit code we are trying to stop trusting. `|| true` on the pipeline makes
# the capture total, so the parse below ALWAYS runs and the gate's exit ALWAYS
# derives from dbt's own output. (`set -o pipefail` is deliberately NOT set, for
# the same reason: it would surface the maskable `uv run` exit through the pipe.)
DBT_OUTPUT="$( { uv run --directory "$PYTHON_DIR" --group dbt dbt "${DBT_ARGS[@]}" --project-dir "$DBT_DIR" --profiles-dir "$DBT_DIR" 2>&1 || true; } | tee /dev/stderr )"

# Strip ANSI colour codes so the parse matches dbt's words regardless of the
# coloured wrapper dbt prints around `Completed successfully` / the summary.
DBT_PLAIN="$(printf '%s\n' "$DBT_OUTPUT" | sed -E 's/\x1b\[[0-9;]*m//g')"

# Success is derived from dbt's OWN completion signal, in two confirming parts:
#   (1) dbt printed its clean-completion line `Completed successfully`; AND
#   (2) the structured `Done. … ERROR=N …` summary reports ERROR=0.
# Any failure marker, a non-zero ERROR=, or the ABSENCE of the clean-completion
# line (a crash before dbt could complete) -> exit non-zero. No false green.
#
# NB: dbt prefixes every log line with a timestamp (`HH:MM:SS  Completed …`), so
# the matches are deliberately UNANCHORED. And every `grep` in a command-
# substitution is guarded with `|| true`: a no-match `grep` exits 1, which under
# `set -e` would otherwise kill the script on the assignment line (a false red).
if printf '%s\n' "$DBT_PLAIN" | grep -Eq '(Completed with [0-9]+ error|Database Error|Compilation Error|Runtime Error|Dependency Error|Parsing Error|\*+ +Error)'; then
  echo "dbt-build.sh: dbt reported a build FAILURE (failure marker in dbt output) — exiting non-zero." >&2
  exit 1
fi

# The structured Done. summary, if present: `… Done. PASS=.. WARN=.. ERROR=N ..`.
DONE_LINE="$(printf '%s\n' "$DBT_PLAIN" | grep -E 'Done\. .*ERROR=' | tail -n 1 || true)"
if [ -n "$DONE_LINE" ]; then
  ERROR_COUNT="$(printf '%s\n' "$DONE_LINE" | sed -nE 's/.*ERROR=([0-9]+).*/\1/p')"
  if [ -n "$ERROR_COUNT" ] && [ "$ERROR_COUNT" -ne 0 ]; then
    echo "dbt-build.sh: dbt summary reports ERROR=$ERROR_COUNT — exiting non-zero." >&2
    exit 1
  fi
fi

# Require the canonical clean-completion line. Its ABSENCE means dbt did not reach
# a clean completion (it crashed / errored before printing it) — treat as failure,
# never silently greened (the masked `uv run` exit is not trustworthy here).
if ! printf '%s\n' "$DBT_PLAIN" | grep -Eq 'Completed successfully'; then
  echo "dbt-build.sh: dbt did not print 'Completed successfully' (no clean completion) — exiting non-zero." >&2
  exit 1
fi

# Clean completion + ERROR=0 -> the build genuinely succeeded.
exit 0
