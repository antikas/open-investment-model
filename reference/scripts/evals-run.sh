#!/usr/bin/env bash
# evals-run.sh (OIM-105) — run the Tranche-0 eval harness in the WSL2/local uv
# env. Invoked by scripts/evals-run.mjs (which handles the Windows->WSL2 hop and
# forwards args). Kept as a real script file so the command survives the
# Node -> wsl -> bash boundary without quote mangling (mirrors dbt-build.sh).
#
# The harness is the offline, deterministic, replay-stable golden-set runner; it
# exits non-zero on a bar miss (CI-gate-ready). Args (e.g. --check-replay) are
# forwarded to `python -m agentinvest_evals`.
#
# Env in (set by evals-run.mjs, with defaults here for direct invocation):
#   REFERENCE_ROOT_WSL  absolute WSL2/local path to reference/ (default: derived)
set -euo pipefail

export PATH="$HOME/.local/bin:$PATH"

# Resolve reference/ root: explicit env, else two dirs up from this script.
if [ -z "${REFERENCE_ROOT_WSL:-}" ]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  REFERENCE_ROOT_WSL="$(cd "$SCRIPT_DIR/.." && pwd)"
fi
PYTHON_DIR="$REFERENCE_ROOT_WSL/python"

# The uv project environment lands on WSL2-native ext4 (P-R1/OIM-107), NOT the
# 9p /mnt/d repo mount — same placement as dbt-build.sh. The harness has no dbt
# dependency, so the base venv (no --group dbt) is enough. The path is keyed on
# THIS checkout's repo root (OIM-110, P-MAJOR-2 fix) so a concurrent checkout / CI
# run does not share-and-clobber one venv; still on ext4 (OIM-107 perf preserved).
# An explicit UV_PROJECT_ENVIRONMENT still wins. See lib/agentinvest-venv-path.sh.
LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib"
# shellcheck source=lib/agentinvest-venv-path.sh
. "$LIB_DIR/agentinvest-venv-path.sh"
REPO_ROOT_WSL="$(cd "$REFERENCE_ROOT_WSL/.." && pwd)"
agentinvest_set_venv_env "$REPO_ROOT_WSL"

cd "$PYTHON_DIR"
# Mask-immunity (OIM-181, from OIM-115 P-NOTE-1): in this WSL2 launch env `uv run`
# intermittently masks a non-zero child exit to 0 (invocation-form-dependent —
# `bash -lc '… && uv run …'` masks because the `&&` stops `uv run` being the
# exec'd leaf), so the `uv run` exit code is NOT a trustworthy success oracle. We
# therefore do NOT `exec uv run` and trust its exit; instead we run it capturing
# the output, tee it to the operator's terminal (the harness report stays fully
# visible), and derive success from the harness's OWN stdout verdict sentinel
# (`EVALS_RESULT: PASS|FAIL rc=N`, emitted on every exit path by
# agentinvest_evals.__main__ — uv cannot eat stdout). The eval numbers + the
# PASS/FAIL verdict logic are unchanged; only the success-signal plumbing is made
# mask-immune. Pin uv's project dir explicitly (--directory "$PYTHON_DIR") so a
# glitched invocation can NEVER fall back to the repo-root cwd (OIM-107 leak-guard).
#
# `set -o pipefail` would let the (maskable) `uv run` exit leak through the pipe;
# we deliberately read the SENTINEL, not the pipe status, so the exit derives from
# the harness's own output.
#
# Visibility: BOTH harness streams are captured (2>&1 — the report is on stdout, an
# uncaught traceback would be on stderr; we want every signal visible to the parse)
# and tee'd to the caller's stderr (always inherited; non-blocking — unlike a write
# to /dev/tty, which can block in a detached/CI context even when a pty exists), so
# the operator still sees the full report while a copy is captured for the parse.
#
# CRITICAL (the OIM-181 fix): the capture is wrapped with `|| true` so `set -e` can
# NEVER abort the script on the assignment line. If `uv run` exits non-zero, a bare
# `VAR="$(uv run … )"` under `set -e` dies on the assignment with `uv run`'s OWN
# (maskable, untrustworthy) exit code BEFORE the sentinel parse runs — re-coupling
# the gate to the exit code we are trying to stop trusting. `|| true` makes the
# capture total, so the parse below ALWAYS runs and the gate's exit ALWAYS derives
# from the harness's own verdict sentinel.
EVALS_OUTPUT="$( { uv run --directory "$PYTHON_DIR" python -m agentinvest_evals "$@" 2>&1 || true; } | tee /dev/stderr )"

# Parse the LAST `EVALS_RESULT:` sentinel line. PASS -> exit 0; FAIL -> exit the
# sentinel's rc (non-zero). A MISSING sentinel (the harness crashed before any
# exit path could emit it, or the stream was lost) is treated as a FAILURE — never
# silently greened, because the masked `uv run` exit code is not trustworthy here.
# `|| true` guards the grep: a no-match grep exits 1, which under `set -e` would
# otherwise kill the script on this assignment.
SENTINEL_LINE="$(printf '%s\n' "$EVALS_OUTPUT" | grep -E '^EVALS_RESULT:[[:space:]]+(PASS|FAIL)[[:space:]]+rc=-?[0-9]+' | tail -n 1 || true)"
if [ -z "$SENTINEL_LINE" ]; then
  echo "evals-run.sh: no EVALS_RESULT sentinel in the harness output — treating as a FAILURE (the harness did not reach an exit path)." >&2
  exit 1
fi

VERDICT="$(printf '%s\n' "$SENTINEL_LINE" | sed -E 's/^EVALS_RESULT:[[:space:]]+(PASS|FAIL)[[:space:]]+rc=(-?[0-9]+).*/\1/')"
SENTINEL_RC="$(printf '%s\n' "$SENTINEL_LINE" | sed -E 's/^EVALS_RESULT:[[:space:]]+(PASS|FAIL)[[:space:]]+rc=(-?[0-9]+).*/\2/')"

if [ "$VERDICT" = "PASS" ]; then
  exit 0
fi
# FAIL: exit the harness's own rc (guaranteed non-zero on a FAIL; default to 1 if
# the rc were somehow 0/empty alongside a FAIL verdict — never green a FAIL).
if [ -z "$SENTINEL_RC" ] || [ "$SENTINEL_RC" -eq 0 ]; then
  exit 1
fi
exit "$SENTINEL_RC"
