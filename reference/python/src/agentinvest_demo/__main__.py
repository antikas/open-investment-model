"""``python -m agentinvest_demo`` entry — runs the end-to-end analytics demo CLI.

Invoking the package (``python -m agentinvest_demo``) runs the task; this avoids the runpy
double-import warning that ``python -m agentinvest_demo.phase2_demo`` would raise (the module is
already imported by the package ``__init__``).
"""

from __future__ import annotations

from agentinvest_demo.phase2_demo import main

if __name__ == "__main__":
    raise SystemExit(main())
