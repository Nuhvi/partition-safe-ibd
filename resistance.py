#!/usr/bin/env python3
"""Diagrams and table for the partition-resistance bound (resistance.md).

    G(T) = mean difficulty over [t0, now] / D(t0)

The flat-bar rule accepts a candidate iff its work since the checkpoint is at
least the constant-difficulty work, so a fork holding a share `s` of believable
hash passes iff `s >= 1/G(T)`.  The maximum safe staleness is the first `T` where
`G(T) = 1/s`.

Usage:  python3 resistance.py
"""
import math

from finality import load, BTC, X_NOW, WORK, YEAR

SHARES = (0.005, 0.01, 0.02, 0.05, 0.10, 0.20, 0.33, 0.49)
CASES = ((0.005, "forks (median ~0.5%)"), (0.33, "67% honest"), (0.49, "51% honest"))
GROWTHS = (1.2, 1.5, 2.0, 10.0)


def D(t):
    lo, hi = 0, len(BTC)
    while lo < hi:
        mid = (lo + hi) // 2
        if BTC[mid][0] <= t:
            lo = mid + 1
        else:
            hi = mid
    return 10 ** BTC[lo - 1][1]


def work(lo, hi):
    total = 0.0
    for i in range(1, len(BTC)):
        x0, y0, h0, _ = BTC[i - 1]
        x1, y1, h1, _ = BTC[i]
        a, z = max(x0, lo), min(x1, hi)
        if z > a:
            total += (h1 - h0) * ((z - a) / (x1 - x0)) * WORK * 10 ** ((y0 + y1) / 2)
    return total


def G(L):
    """mean difficulty over [now-L, now] / D(now-L)."""
    t0 = X_NOW - L
    if t0 < 1.0:
        return None
    return work(t0, X_NOW) / (D(t0) * WORK / 600.0 * L * YEAR)


def cap(s, step=0.025, lmax=12.0):
    """First staleness where G >= 1/s, or None if never within lmax."""
    L = step
    while L <= lmax:
        g = G(L)
        if g is not None and g >= 1.0 / s:
            return L
        L += step
    return None


def cap_cf(s, gpy):
    """Closed form: solve (e^(kT)-1)/(kT) = 1/s."""
    k = math.log(gpy)
    lo, hi = 1e-3, 60.0
    for _ in range(200):
        m = (lo + hi) / 2
        gg = (math.exp(k * m) - 1) / (k * m) if k * m > 1e-9 else 1.0
        if gg < 1.0 / s:
            lo = m
        else:
            hi = m
    return (lo + hi) / 2


def main():
    print("flat-bar rule: max safe staleness = first T with G(T) = 1/s")
    print("  %-8s %-10s %s" % ("share s", "1/s", "cap"))
    for s in SHARES:
        c = cap(s)
        print("  %-8s %-10.0f %s" % (f"{100*s:g}%", 1 / s, f"{c:.2f} y" if c else ">12y"))

    try:
        plot()
    except ImportError:
        pass


def plot(path="diagrams/resistance_caps.png"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.2))

    # A: the growth functional and the 1/s bars
    Ls = np.arange(0.25, 12.01, 0.25)
    Gs = [G(L) for L in Ls]
    ax1.semilogy(Ls, Gs, lw=2, color="#2c3e50", label="G(T) = mean D / D(anchor)")
    ax1.set_yticks([1, 2, 5, 10, 20, 50, 100, 200, 500, 1000])
    ax1.set_yticklabels(["1", "2", "5", "10", "20", "50", "100", "200", "500", "1000"])
    ax1.set_xticks(range(0, 13, 2))
    colors = ("#2980b9", "#27ae60", "#e67e22", "#c0392b")
    for s, lab, col in zip((0.005, 0.05, 0.33, 0.49),
                           ("0.5% attacker", "5% attacker", "33%", "49%"), colors):
        ax1.axhline(1 / s, ls="--", lw=1, color=col)
        ax1.text(0.3, 1 / s * 1.08, lab, color=col, fontsize=8)
    ax1.set_xlabel("checkpoint staleness T (years)")
    ax1.set_ylabel("G(T) = mean difficulty / anchor difficulty")
    ax1.set_title("honest growth vs the attacker's bar\n(crossing = max safe staleness)")
    ax1.grid(which="both", alpha=0.2); ax1.legend(loc="lower right")

    # B: cap vs attacker share, empirical + closed form
    grid = np.logspace(math.log10(0.002), math.log10(0.6), 40)
    caps = [cap(s, step=0.05) or 12.0 for s in grid]
    ax2.plot([100 * s for s in grid], caps, lw=2.4, color="#2c3e50", label="BTC, last decade")
    for g, col in zip(GROWTHS, ("#95a5a6", "#7f8c8d", "#34495e", "#c0392b")):
        ys = [min(cap_cf(s, g), 24.0) for s in grid]
        ax2.plot([100 * s for s in grid], ys, ls=":", lw=1.2, color=col,
                 label=f"{g:g}x/yr growth")
    for s, lab in CASES:
        c = cap(s)
        if c:
            ax2.plot(100 * s, c, "o", color="#c0392b", ms=7)
            ax2.annotate(f"{lab}\n{c:.1f} y", (100 * s, c), textcoords="offset points",
                         xytext=(6, 6), fontsize=8, color="#c0392b")
    ax2.set_xscale("log"); ax2.set_yscale("log")
    ax2.set_xticks([0.5, 1, 2, 5, 10, 20, 33, 49])
    ax2.set_xticklabels(["0.5", "1", "2", "5", "10", "20", "33", "49"])
    ax2.set_yticks([1, 2, 3, 5, 10, 20])
    ax2.set_yticklabels(["1", "2", "3", "5", "10", "20"])
    ax2.set_xlabel("attacker share of believable hash rate (%)")
    ax2.set_ylabel("max safe staleness (years)")
    ax2.set_title("how stale you can be, vs attacker share")
    ax2.grid(which="both", alpha=0.2); ax2.legend(loc="upper right", fontsize=8)

    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)
    print(f"\nwrote {path}")


if __name__ == "__main__":
    main()
