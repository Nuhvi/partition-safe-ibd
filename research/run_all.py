#!/usr/bin/env python3
"""Run every experiment in order.  Needs matplotlib (see the repo .venv)."""
import runpy
import sys

for mod in ("exp1_window", "exp2_estimator", "exp3_backtest",
            "exp4_forks", "exp5_bars", "exp6_forecast"):
    print(f"\n================ {mod} ================")
    sys.stdout.flush()
    runpy.run_module(mod, run_name="__main__")
print("\nall figures in research/figures/")
