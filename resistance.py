#!/usr/bin/env python3
"""Diagrams and tables for the partition-resistance bound (resistance.md).

    G(T) = mean difficulty over [t0, now] / D(t0)

The flat-bar rule accepts a candidate iff its work since the checkpoint is at
least the constant-difficulty work, so a fork holding a share `s` of believable
hash passes iff `s >= 1/G(T)`.  The maximum safe staleness is the first `T` where
`G(T) = 1/s`.

Also reported: (a) how often the *honest* chain fails the bar (G < 1), and
(b) forks that split *after* the checkpoint, which carry the real shared work up
to their split and therefore pass far more easily.

Usage:  python3 resistance.py
"""
import math

from finality import load, work_between, BTC, X_NOW, WORK, YEAR

SHARES = (0.005, 0.01, 0.02, 0.05, 0.10, 0.20, 0.33, 0.49)
CASES = ((0.005, "forks (median ~0.5%)"), (0.34, "peak (BCH 2017)"), (0.49, "51% honest"))
GROWTHS = (1.2, 1.5, 2.0, 10.0)
BCH_FORK = 8.574          # 2017-08-01, years since genesis


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


def _w(lo, hi, pts):
    if pts is BTC:
        return work(lo, hi)
    total = 0.0
    for i in range(1, len(pts)):
        x0, y0, h0, _ = pts[i - 1]
        x1, y1, h1, _ = pts[i]
        a, z = max(x0, lo), min(x1, hi)
        if z > a:
            total += (h1 - h0) * ((z - a) / (x1 - x0)) * WORK * 10 ** ((y0 + y1) / 2)
    return total


def G(L, now=X_NOW):
    """mean difficulty over [now-L, now] / D(now-L)."""
    t0 = now - L
    if t0 < 1.0:
        return None
    return work(t0, now) / (D(t0) * WORK / 600.0 * L * YEAR)


def cap(s, step=0.025, lmax=12.0):
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
    if k < 1e-3:
        return float("inf")
    lo, hi = 1e-3, 60.0
    for _ in range(200):
        m = (lo + hi) / 2
        gg = (math.exp(k * m) - 1) / (k * m)
        if gg < 1.0 / s:
            lo = m
        else:
            hi = m
    return (lo + hi) / 2


def honest_fail(L, step=0.25):
    """Fraction of historical anchors of staleness L at which the honest chain is below the bar."""
    n = bad = 0
    e = 1.0 + L
    while e <= X_NOW:
        g = G(L, now=e)
        if g is not None:
            n += 1
            bad += g < 1
        e += step
    return bad, n


def late_split_ratio(t0, t1, chain):
    """Candidate = honest work up to the fork + the fork's own work after it."""
    tf = min(max(BCH_FORK, t0), t1)
    w = _w(t0, tf, BTC) + _w(tf, t1, load(chain))
    bar = D(t0) * WORK / 600.0 * (t1 - t0) * YEAR
    return w / bar


def main():
    print("flat-bar rule: max safe staleness = first T with G(T) = 1/s")
    print("  %-8s %-10s %s" % ("share s", "1/s", "cap"))
    for s in SHARES:
        c = cap(s)
        print("  %-8s %-10.0f %s" % (f"{100*s:g}%", 1 / s, f"{c:.2f} y" if c else ">12y"))

    print("\nclosed form, T* vs growth rate (1.0x/yr never breaks)")
    print("  %-8s %s" % ("share s", "".join("%-9s" % f"{g:g}x/yr" for g in GROWTHS)))
    for s in (0.005, 0.02, 0.05, 0.33, 0.49):
        row = []
        for g in GROWTHS:
            c = cap_cf(s, g)
            row.append("inf" if c == float("inf") else (f"{c:.1f} y" if c < 59 else ">59 y"))
        print("  %-8s %s" % (f"{100*s:g}%", "".join("%-9s" % r for r in row)))

    print("\nhonest chain vs the bar: how often G < 1 (the node cannot finalize)")
    for L in (0.5, 1.0, 1.5, 2.0, 3.0):
        bad, n = honest_fail(L)
        print("  T=%-4g  %d/%d = %3.0f%%   (live tip G=%.3f %s)"
              % (L, bad, n, 100 * bad / max(n, 1), G(L), "fail" if G(L) < 1 else "pass"))

    print("\nlate splits: a fork that splits after the checkpoint carries the shared work")
    print("  %-18s %-10s %-8s" % ("checkpoint", "tip", "BCH/bar"))
    for t0, t1 in ((2015.0, 2018.25), (2016.0, 2018.25), (2017.0, 2018.25),
                   (2017.25, 2018.25), (2017.5, 2018.25)):
        r = late_split_ratio(t0 - 2009, t1 - 2009, "BCH")
        print("  %-18s %-10s %.3gx  %s" % (t0, t1, r, "PASS" if r >= 1 else "fail"))

    try:
        plot()
    except ImportError:
        pass


def plot(path="diagrams/resistance_caps.png"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    fig, ax = plt.subplots(2, 2, figsize=(13, 10))

    # A: honest growth (at the live tip) vs the attacker's bar
    Ls = np.arange(0.25, 12.01, 0.25)
    ax[0][0].semilogy(Ls, [G(L) for L in Ls], lw=2, color="#2c3e50",
                      label="G(T) = mean D / D(anchor)")
    ax[0][0].set_yticks([0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000])
    ax[0][0].set_yticklabels(["0.5", "1", "2", "5", "10", "20", "50", "100", "200", "500", "1000"])
    ax[0][0].axhline(1, color="#c0392b", lw=1)
    ax[0][0].text(4.2, 1.05, "honest chain fails below G=1", color="#c0392b", fontsize=8)
    for s, lab, col in zip((0.005, 0.05, 0.34, 0.49),
                           ("0.5% attacker", "5%", "peak 34%", "49%"),
                           ("#2980b9", "#27ae60", "#e67e22", "#8e44ad")):
        ax[0][0].axhline(1 / s, ls="--", lw=1, color=col)
        ax[0][0].text(0.3, 1 / s * 1.06, lab, color=col, fontsize=8)
    ax[0][0].set_xlabel("checkpoint staleness T (years)")
    ax[0][0].set_ylabel("G(T) = mean difficulty / anchor difficulty")
    ax[0][0].set_title("A. honest growth vs the attacker's bar\n(G at the live tip)")
    ax[0][0].grid(which="both", alpha=0.2); ax[0][0].legend(loc="lower right")

    # B: cap vs attacker share, empirical + closed form
    grid = np.logspace(math.log10(0.002), math.log10(0.6), 40)
    ax[0][1].plot([100 * s for s in grid], [cap(s, step=0.05) or 12.0 for s in grid],
                  lw=2.4, color="#2c3e50", label="BTC, last decade")
    for g, col in zip(GROWTHS, ("#95a5a6", "#7f8c8d", "#34495e", "#c0392b")):
        ax[0][1].plot([100 * s for s in grid], [min(cap_cf(s, g), 24.0) for s in grid],
                      ls=":", lw=1.2, color=col, label=f"{g:g}x/yr growth")
    for i, (s, lab) in enumerate(CASES):
        c = cap(s)
        if c:
            ax[0][1].plot(100 * s, c, "o", color="#c0392b", ms=7)
            ax[0][1].annotate(f"{lab}\n{c:.1f} y", (100 * s, c), textcoords="offset points",
                              xytext=(6, 6 + 16 * (i % 2)), fontsize=8, color="#c0392b")
    ax[0][1].set_xscale("log"); ax[0][1].set_yscale("log")
    ax[0][1].set_xticks([0.5, 1, 2, 5, 10, 20, 33, 49])
    ax[0][1].set_xticklabels(["0.5", "1", "2", "5", "10", "20", "33", "49"])
    ax[0][1].set_yticks([1, 2, 3, 5, 10, 20])
    ax[0][1].set_yticklabels(["1", "2", "3", "5", "10", "20"])
    ax[0][1].set_xlabel("attacker share of believable hash rate (%)")
    ax[0][1].set_ylabel("max safe staleness (years)")
    ax[0][1].set_title("B. how stale you can be, vs attacker share")
    ax[0][1].grid(which="both", alpha=0.2); ax[0][1].legend(loc="upper right", fontsize=8)

    # C: how often the honest chain is below the bar
    Ts = [0.5, 1.0, 1.5, 2.0, 3.0]
    fracs = [100 * honest_fail(T)[0] / max(honest_fail(T)[1], 1) for T in Ts]
    ax[1][0].bar([str(T) for T in Ts], fracs, color="#c0392b", width=0.6)
    for i, f in enumerate(fracs):
        ax[1][0].text(i, f + 0.2, f"{f:.0f}%", ha="center", fontsize=9)
    ax[1][0].set_xlabel("checkpoint staleness T (years)")
    ax[1][0].set_ylabel("% of historical anchors")
    ax[1][0].set_title("C. the honest chain fails the flat bar\n(fraction of anchors with G<1)")
    ax[1][0].grid(axis="y", alpha=0.2)

    # D: forks that split after the checkpoint
    ages = np.arange(0.0, 3.01, 0.125)
    tip = 2018.25 - 2009
    ratios = [late_split_ratio(tip - a, tip, "BCH") for a in ages]
    ax[1][1].semilogy(ages, ratios, "o-", ms=3, color="#c0392b", label="BCH vs the bar")
    ax[1][1].axhline(1, color="#2c3e50", ls="--", lw=1)
    ax[1][1].set_yticks([0.1, 0.5, 1, 5, 10, 50, 100])
    ax[1][1].set_yticklabels(["0.1", "0.5", "1", "5", "10", "50", "100"])
    ax[1][1].text(0.05, 1.15, "bar", color="#2c3e50", fontsize=8)
    ax[1][1].set_xlabel("years the checkpoint predates the split")
    ax[1][1].set_ylabel("candidate work / bar")
    ax[1][1].set_title("D. forks splitting after the checkpoint\n(carries shared honest work)")
    ax[1][1].grid(which="both", alpha=0.2); ax[1][1].legend()

    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)
    print(f"\nwrote {path}")


if __name__ == "__main__":
    main()
