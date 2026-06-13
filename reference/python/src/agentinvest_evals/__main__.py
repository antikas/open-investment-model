"""Package entry: `python -m agentinvest_evals` runs the eval harness.

Delegates to `runner.main`, which runs the intra-domain eval with the declared
deterministic baseline selector and exits non-zero on a bar miss (CI-gate-ready).

On every exit path this entry prints a machine-readable result sentinel to stdout
(``EVALS_RESULT: PASS|FAIL rc=N``), mirroring ``phase2_demo``'s
``PHASE2_DEMO_RESULT:`` line. The floor gate (``scripts/evals-run.sh``) reads the
outcome from THIS line, not from the process exit code — in this WSL2 launch
environment ``uv run`` masks every non-zero child exit to 0 (invocation-form
dependent), so the exit code is not a trustworthy success oracle; stdout, which
``uv run`` cannot eat, is. The sentinel is ADDITIVE: ``runner.main`` keeps its
integer return contract and its byte-identical report (the in-process tests score
``runner.main`` directly and are untouched), and this module still does
``raise SystemExit(rc)`` so a direct invocation keeps its exit-code contract too.

The eval numbers and the PASS/FAIL verdict logic are unchanged — only the
success-signal plumbing is made mask-immune by emitting the verdict on stdout.
"""

from __future__ import annotations

from agentinvest_evals.runner import main

# The machine-readable result line, printed on the harness's final stdout line on
# EVERY exit path. ``rc == 0`` -> PASS; any non-zero -> FAIL. The floor gate parses
# this rather than the (maskable) ``uv run`` exit code. Mirrors
# ``phase2_demo.RESULT_SENTINEL_PREFIX``.
RESULT_SENTINEL_PREFIX = "EVALS_RESULT:"


def _emit_result_sentinel(rc: int) -> None:
    """Print the machine-readable result line the floor gate parses.

    Flushed so it survives a buffered pipe through the uv / wsl launch layers. This
    is the channel the gate reads the outcome from, since the process exit code is
    masked by ``uv run`` in the launch environment.
    """
    outcome = "PASS" if rc == 0 else "FAIL"
    print(f"{RESULT_SENTINEL_PREFIX} {outcome} rc={rc}", flush=True)


def _entry() -> int:
    """Run the harness, then emit the result sentinel on every exit path.

    Wraps :func:`runner.main` so the ``EVALS_RESULT:`` line is printed whatever
    happens (a clean pass, a bar miss, a malformed/one-sided set, an argparse
    ``SystemExit``, or any unexpected crash), because the floor gate reads the
    outcome from that stdout line rather than the process exit code (which
    ``uv run`` masks in the WSL2 launch environment). The integer return value is
    unchanged — the eval numbers and the verdict logic are byte-identical.
    """
    try:
        rc = main()
    except SystemExit as exc:  # argparse --help/usage exits via SystemExit; surface its code.
        rc = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
        _emit_result_sentinel(rc)
        raise
    except BaseException:  # any unexpected crash must NOT be silently greened by the masked exit.
        _emit_result_sentinel(1)
        raise
    _emit_result_sentinel(rc)
    return rc


if __name__ == "__main__":
    raise SystemExit(_entry())
