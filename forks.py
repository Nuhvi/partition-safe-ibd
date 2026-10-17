#!/usr/bin/env python3
"""Collective non-BTC SHA256d hash rate, relative to Bitcoin.

The hash an attacker can bring to a partition attack is bounded by the SHA256d
hash that is not on Bitcoin — if they abandon every other chain.  This measures
that from the cached series (BCH, BSV, XEC) and reports the **work-weighted**
share, which is what the work-since-anchor rule compares against: hash that was
around during a high-hash period counts for more than the same hash in a quiet
period.

Usage:  python3 forks.py
"""
import math
import sys

from finality import load, BTC, X_NOW

FORKS = ("BCH", "BSV", "XEC")
SERIES = {c: load(c) for c in FORKS}


def difficulty_at(pts, t):
    """Difficulty of a sampled chain at time t (last sample at or before t)."""
    lo, hi = 0, len(pts)
    while lo < hi:
        mid = (lo + hi) // 2
        if pts[mid][0] <= t:
            lo = mid + 1
        else:
            hi = mid
    return 0.0 if lo == 0 else 10 ** pts[lo - 1][1]


def share_at(t):
    base = difficulty_at(BTC, t)
    if base <= 0:
        return 0.0
    return sum(difficulty_at(SERIES[c], t) for c in FORKS) / base


def share_series(step=0.05):
    lo = max(s[0][0] for s in SERIES.values())
    out, t = [], lo
    while t <= X_NOW:
        s = share_at(t)
        if s > 0:
            out.append((t, s))
        t += step
    return out


def main():
    ss = share_series()
    print("non-BTC SHA256d share of Bitcoin hash rate (BCH + BSV + XEC)")
    print("  %-14s %-10s" % ("year", "share"))
    by_year = {}
    for x, s in ss:
        by_year.setdefault(int(2009 + x), []).append(s)
    for y in sorted(by_year):
        v = sorted(by_year[y])
        print("  %-14d %-10s  (peak %.2f%%)" % (y, f"{100*v[len(v)//2]:.2f}%", 100*v[-1]))
    vals = sorted(s for _, s in ss)
    print("\n  n=%d  median=%.2f%%  peak=%.2f%%"
          % (len(vals), 100 * vals[len(vals) // 2], 100 * vals[-1]))

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
    ax.set_xlabel("years since genesis"); ax.set_ylabel("share of Bitcoin hash rate (%, log)")
    ax.set_title("Non-BTC SHA256d hash rate (BCH + BSV + XEC) as a share of Bitcoin")
    ax.grid(which="both", alpha=0.25)
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)
    print(f"\nwrote {path}")


if __name__ == "__main__":
    main()
