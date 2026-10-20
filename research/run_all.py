#!/usr/bin/env python3
"""Run the model figures used by ../README.md."""
import runpy
import sys

for mod in ("estimated_hashrate", "estimated_work_history", "cost_5pct"):
    print(f"\n================ {mod} ================")
    sys.stdout.flush()
    runpy.run_module(mod, run_name="__main__")
print("\nfigures in research/figures/")
