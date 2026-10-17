#!/usr/bin/env python3
"""Collective non-BTC SHA256d hash rate, relative to Bitcoin.

Measured on a common window grid so both sides are compared over the *same*
wall-clock period, **fork-aware** (a chain counts only after it diverged) and
from **work over the window** rather than the raw difficulty ratio — at a fork
the difficulty is inherited, which makes the ratio read 100 %, and BCH/BSV
shared a chain until Nov 2018, which makes a naive sum double-count.

Usage:  python3 forks.py
"""
import math

from finality import load, work_between, BTC, X_NOW

FORKS = ("BCH", "BSV", "XEC")
FORKH = {"BCH": 478558, "BSV": 556766, "XEC": 661648}
SERIES = {c: load(c) for c in FORKS}
FORKT = {c: next(p[0] for p in SERIES[c] if p[2] >= FORKH[c]) for c in FORKS}



STEP_GRID = [p[0] for p in SERIES["BCH"]]      # BCH's own ~4-month windows


def share_at(t):
    """Non-BTC share of BTC hash rate over the window containing t."""
    for a, b in zip(STEP_GRID, STEP_GRID[1:]):
        if a <= t <= b:
            return _share(a, b)
    return _share(STEP_GRID[-2], STEP_GRID[-1])

def _share(a, b):
    bw = work_between(a, b, BTC)
    if bw <= 0:
        return 0.0
    fw = sum(work_between(a, b, SERIES[c]) for c in FORKS
             if a + 1e-9 >= FORKT[c])
    return fw / bw


def share_series():
    return [((a + b) / 2, _share(a, b)) for a, b in zip(STEP_GRID, STEP_GRID[1:])]


def main():
    ss = share_series()
    print("non-BTC SHA256d share of Bitcoin hash rate (BCH + BSV + XEC, per ~4-month window)")
    by_year = {}
    for x, s in ss:
        by_year.setdefault(int(2009 + x), []).append(s)
    for y in sorted(by_year):
        v = sorted(by_year[y])
        print("  %-6d median %6.2f%%   peak %6.2f%%" % (y, 100 * v[len(v) // 2], 100 * v[-1]))
    vals = sorted(s for _, s in ss)
    print("  full history: median %.2f%%   peak %.2f%% (%d)"
          % (100 * vals[len(vals) // 2], 100 * vals[-1], 2009 + max(ss, key=lambda z: z[1])[0]))

    try:
        plot(ss)
    except ImportError:
        pass


def plot(ss, path="diagrams/fork_hash_share.png"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.semilogy([x for x, _ in ss], [100 * s for _, s in ss], lw=1.5, color="#c0392b")
    ax.set_yticks([0.01, 0.05, 0.1, 0.5, 1, 5, 10, 50])
    ax.set_yticklabels(["0.01", "0.05", "0.1", "0.5", "1", "5", "10", "50"])
    ax.set_xlabel("years since genesis")
    ax.set_ylabel("non-BTC share of Bitcoin hash rate (%)")
    ax.set_title("Non-BTC SHA256d hash rate (BCH + BSV + XEC) as a share of Bitcoin")
    ax.grid(which="both", alpha=0.2)
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)
    print(f"\nwrote {path}")


if __name__ == "__main__":
    main()
