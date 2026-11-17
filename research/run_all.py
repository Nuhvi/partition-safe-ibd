#!/usr/bin/env python3
"""Refresh the data and run the model figures used by ../README.md.

By default the script appends the latest header and price samples to the data
files, then rebuilds the figures.  No model parameter changes and no refit.
Use --offline to rebuild the figures from the stored data only.
"""
import argparse
import runpy
import sys

import refresh

MODULES = ("estimated_hashrate", "estimated_work_history",
           "estimated_work_backtest", "cost_5pct")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--offline", action="store_true",
                   help="use the stored data; do not fetch new samples")
    a = p.parse_args(argv)

    rc = 0
    if a.offline:
        print("data: offline, using the stored samples")
    else:
        print("data: refresh from mempool.space and blockchain.info")
        try:
            rc = refresh.main()
        except Exception as e:  # a stale file must not stop the figures
            rc = 1
            print(f"data: refresh failed ({e}); using the stored samples",
                  file=sys.stderr)

    for mod in MODULES:
        print(f"\n================ {mod} ================")
        sys.stdout.flush()
        runpy.run_module(mod, run_name="__main__")
    print("\nfigures in research/figures/")
    return rc


if __name__ == "__main__":
    sys.exit(main())
