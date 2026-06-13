# shellcheck shell=bash
# agentinvest-venv-path.sh — the SSOT for the checkout-safe ext4
# shared-state paths: the uv venv AND the duckdb store. Sourced by the launchers
# (dbt-build.sh, evals-run.sh) and inlined by the .mjs Python-endpoint launch;
# NOT executed directly.
#
# WHY THIS EXISTS. Placing the uv venv on WSL2-native ext4 (~5× faster cold
# import, ~22s→~4s) at a FIXED, $HOME-keyed singleton
# (`$HOME/.local/share/agentinvest/venv`) shares that path across every
# checkout/worktree of the repo under one $HOME — including isolated git worktrees
# and CI matrix jobs. Two checkouts that pin different dependency sets (which
# happens the moment a branch lands heavier deps while another checkout is older)
# share one venv: `uv sync` from one mutates the venv the other is mid-run
# against. That is a live concurrent-checkout / CI collision hazard, not a
# hypothetical.
#
# THE SAME CLASS — the duckdb store. The canonical dbt store is a single duckdb
# FILE on the same ext4 parent (`…/agentinvest/duckdb/canonical.duckdb`). duckdb
# is SINGLE-WRITER-PER-FILE: two concurrent checkouts/worktrees (or a CI matrix)
# both running `dbt build` against one fixed `canonical.duckdb` collide on the
# file lock — exactly the same shared-state class the venv keying closes. Keying
# the venv but leaving the duckdb a $HOME singleton only half-closes the entry
# condition. This helper keys BOTH on the checkout identity.
#
# THE FIX. Key each shared-state path on the CHECKOUT IDENTITY (the absolute repo
# root path), so each checkout/worktree gets its own venv AND its own duckdb file:
#
#     $HOME/.local/share/agentinvest/venv-<token>
#     $HOME/.local/share/agentinvest/duckdb/canonical-<token>.duckdb
#
# where <token> is a short, stable hash of the resolved absolute repo-root path
# (the SAME token for both, from the SAME repo root — one keying scheme). Two
# checkouts at different paths -> two tokens -> distinct venv + distinct duckdb ->
# no collision. A re-run from the same checkout -> the same token -> reuse
# (idempotent, fast, the build is incremental over the same file). Both still
# live on ext4 under the same `…/agentinvest/` parent (the duckdb keeps its own
# `duckdb/` subdir), so the perf win and the ext4 placement are
# preserved untouched — it is the ext4 *placement* that buys the speed and avoids
# the 9p locking hazard, not the singleton-ness of the path.
#
# OVERRIDE. An
# explicit `UV_PROJECT_ENVIRONMENT` / `AGENTINVEST_DUCKDB_PATH` set by the caller
# wins — a native-Linux CI runner can point either at an in-repo / per-job path,
# exactly as before. This helper only computes the DEFAULT when the caller did
# not set one; it never overrides an explicit value.

# A short, stable token from the absolute repo-root path. Prefer sha256sum
# (coreutils, present on every WSL2/Linux runner); fall back to cksum if absent.
# The SAME token keys the venv and the duckdb so one checkout's state is one
# consistent keyed family.
agentinvest_repo_token() {
  local repo_root="$1"
  if command -v sha256sum >/dev/null 2>&1; then
    printf '%s' "$repo_root" | sha256sum | cut -c1-12
  else
    printf '%s' "$repo_root" | cksum | cut -d' ' -f1
  fi
}

# Resolve the agentINVEST ext4 venv path for THIS checkout. Echoes the path.
# Arg 1: the absolute repo-root path to key on (resolved, no trailing slash).
agentinvest_venv_path() {
  local repo_root="$1"
  local parent="${AGENTINVEST_VENV_PARENT:-$HOME/.local/share/agentinvest}"
  printf '%s/venv-%s' "$parent" "$(agentinvest_repo_token "$repo_root")"
}

# Resolve the agentINVEST ext4 duckdb FILE path for THIS checkout. Echoes the
# path. Arg 1: the absolute repo-root path to key on (resolved, no trailing
# slash). Keyed on the SAME token as the venv, kept on ext4 under the same
# `…/agentinvest/duckdb/` parent (NOT the 9p /mnt/d mount).
agentinvest_duckdb_path() {
  local repo_root="$1"
  local parent="${AGENTINVEST_VENV_PARENT:-$HOME/.local/share/agentinvest}"
  printf '%s/duckdb/canonical-%s.duckdb' "$parent" "$(agentinvest_repo_token "$repo_root")"
}

# Set UV_PROJECT_ENVIRONMENT for THIS checkout, honouring an explicit caller value.
# Arg 1: the absolute repo-root path to key on.
# Leaves an existing UV_PROJECT_ENVIRONMENT untouched (the override path);
# otherwise defaults it to the checkout-keyed ext4 path above, and mkdir -p's the
# parent so uv can create the venv.
agentinvest_set_venv_env() {
  local repo_root="$1"
  if [ -z "${UV_PROJECT_ENVIRONMENT:-}" ]; then
    UV_PROJECT_ENVIRONMENT="$(agentinvest_venv_path "$repo_root")"
  fi
  export UV_PROJECT_ENVIRONMENT
  mkdir -p "$(dirname "$UV_PROJECT_ENVIRONMENT")"
}

# Set AGENTINVEST_DUCKDB_PATH for THIS checkout, honouring an explicit caller
# value. Arg 1: the absolute repo-root path to key on.
# Leaves an existing AGENTINVEST_DUCKDB_PATH untouched (the override
# path — a CI runner or an isolated checkout can pin its own file); otherwise
# defaults it to the checkout-keyed ext4 path above, and mkdir -p's the parent so
# dbt/duckdb can create the file. This is the launcher-side keying authority; the
# profiles.yml env_var() default is only the fallback for a bare `dbt` run that
# did not go through a launcher.
agentinvest_set_duckdb_env() {
  local repo_root="$1"
  if [ -z "${AGENTINVEST_DUCKDB_PATH:-}" ]; then
    AGENTINVEST_DUCKDB_PATH="$(agentinvest_duckdb_path "$repo_root")"
  fi
  export AGENTINVEST_DUCKDB_PATH
  mkdir -p "$(dirname "$AGENTINVEST_DUCKDB_PATH")"
}
