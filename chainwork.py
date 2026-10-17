#!/usr/bin/env python3
"""Chainwork-since-the-checkpoint as the node statistic (Phase 2 redesign).

The tip-difficulty rule in analyze.py grades a *point* and can be cleared with a
single block (attack_cost.py, README §6).  This module grades the *work actually
done over the elapsed interval* instead:

    trusted anchor      (height h0, time t0, difficulty D0, cumulative work C0)
    candidate tip       (height h1, time t1, cumulative work C1)
    node clock          t_now                       (NOT the candidate's headers)
    elapsed             T = t_now - t0
    observed work       dC = C1 - C0
    trend work          Wtr = integral of (D_tr * 2^32 / 600) over [t0, t_now]
    statistic           q = log10(dC) - log10(Wtr)

The trend difficulty D_tr is the same power law fit as analyze.py.  Finality
requires

    q >= -band(W, h)          one-sided: a chain may have more work, not less
    dC >= floor(t0)           hard floor: at least one block at the anchor's own
                              difficulty, so an absurdly wide band can never
                              accept a chain that has not grown at all

`band` is calibrated on q for the true chain, with the model's monotone guard
(non-decreasing in h).  Elapsed time comes from the node's clock, so header
timestamps only enter through the work they certify.

Usage:  python3 chainwork.py [W ...]     (default 2 4 8)
"""
import math
import random
import sys

from analyze import load, fit, predict, YEAR

WORK = 2 ** 32
TARGET = 600.0            # seconds per block
TH_DAY = 1e12 * 86400     # hashes per (TH/s * day)
HASHPRICE = 0.04          # USD per TH/s per day; scales linearly
MIN_SUPPORT = 8           # refuse to trust a band built from fewer windows
QS = (0.5, 1.0, 2.0, 4.0, 6.0, 10.0)
WS = [float(a) for a in sys.argv[1:]] or [2.0, 4.0, 8.0]
BTC = load("BTC")
X_NOW = BTC[-1][0]
H_NOW = 10 ** BTC[-1][1] * WORK / TARGET


def usd(hashes):
    return hashes / TH_DAY * HASHPRICE


def work_between(lo, hi, pts=None):
    """Chainwork (hashes) of the sampled chain between two times (years)."""
    pts = pts or BTC
    total = 0.0
    for i in range(1, len(pts)):
        x0, y0, h0, _ = pts[i - 1]
        x1, y1, h1, _ = pts[i]
        if x1 < lo or x0 > hi:
            continue
        a, z = max(x0, lo), min(x1, hi)
        if z <= a:
            continue
        total += (h1 - h0) * ((z - a) / (x1 - x0)) * WORK * 10 ** ((y0 + y1) / 2)
    return total


def trend_work(model, lo, hi):
    """Chainwork implied by the fitted trend line over [lo, hi] (years)."""
    a, b = model["a"], model["b"]
    return WORK / TARGET * YEAR * 10 ** a / (b + 1) * (hi ** (b + 1) - lo ** (b + 1))


def q_at(W, h, e, pts=None):
    """q for the chain that forked at trend-fit end `e` and is `h` years newer."""
    pts = pts or BTC
    model = fit(e, W, pts)
    if not model or e + h > pts[-1][0]:
        return None
    act = work_between(e, e + h, pts)
    tr = trend_work(model, e, e + h)
    return None if act <= 0 or tr <= 0 else math.log10(act) - math.log10(tr)


def q_samples(W, h):
    """(test calendar year, q) for every fit window at this staleness."""
    out, e = [], 1.0 + W
    while e <= X_NOW - h:
        q = q_at(W, h, e)
        if q is not None:
            out.append((2009.0 + e + h, q))
        e += 0.5
    return sorted(out)


def band_raw(W, h, q=0.05):
    """One-sided band = magnitude of the lower `q` quantile of the true chain."""
    vals = sorted(v for _, v in q_samples(W, h))
    return None if not vals else max(0.0, -vals[int(q * (len(vals) - 1))])


def band(W, h, grid_max=10.0, step=0.5):
    """Guarded band: non-decreasing in h (a band cannot shrink as it ages)."""
    hs = sorted({round(i * step, 6) for i in range(int(round(grid_max / step)) + 1)
                 if i * step <= h} | {h})
    run = 0.0
    for hh in hs:
        b = band_raw(W, hh)
        if b is not None:
            run = max(run, b)
    return run


def band_ci(W, h, trials=2000, seed=0):
    """Bootstrap 5–95 % interval for the one-sided band."""
    vals = [v for _, v in q_samples(W, h)]
    n = len(vals)
    if n < 2:
        return None
    rng = random.Random(seed)
    bs = []
    for _ in range(trials):
        s = sorted(vals[rng.randrange(n)] for _ in range(n))
        bs.append(max(0.0, -s[int(0.05 * (n - 1))]))
    bs.sort()
    return bs[int(0.05 * (trials - 1))], bs[int(0.95 * (trials - 1))]


def anchor_difficulty(e):
    """Trusted chain's difficulty at the anchor (nearest sample at or before e)."""
    row = [p for p in BTC if p[0] <= e]
    return 10 ** row[-1][1]


def floor_work(e):
    """Hard floor: one block at the anchor's own difficulty."""
    return WORK * anchor_difficulty(e)


def main():
    print("chainwork statistic q = log10(work since anchor) - log10(trend integral)")
    print("one-sided band on q, monotone-guarded; floor = one block at anchor difficulty")
    print()

    print("=== bands (dex) ===")
    print("%-6s %s" % ("W", "".join("%-13s" % f"h={h:g}" for h in QS)))
    for W in WS:
        cells = []
        for h in QS:
            raw = band_raw(W, h)
            g = band(W, h)
            n = len(q_samples(W, h))
            cells.append(f"{raw:.2f}->{g:.2f}" if raw is not None else "n/a")
        print("%-6s %s" % (f"{W:g}y", "".join("%-13s" % c for c in cells)))

    print("\n=== support and band interval (bootstrap 5-95%%; MIN_SUPPORT=%d) ===" % MIN_SUPPORT)
    print("%-6s %-5s %-5s %-9s %-16s %s" % ("W", "h", "n", "band", "interval", "verdict"))
    for W in WS:
        for h in (0.5, 1, 2, 4, 10):
            vals = q_samples(W, h)
            n = len(vals)
            ci = band_ci(W, h)
            verdict = "ok" if n >= MIN_SUPPORT else "THIN (do not trust)"
            ci_s = "-" if ci is None else f"[{ci[0]:.2f}, {ci[1]:.2f}]"
            print("%-6s %-5g %-5d %-9.2f %-16s %s"
                  % (f"{W:g}y", h, n, band(W, h), ci_s, verdict))

    print("\n=== walk-forward coverage (band from tests <= cutoff, scored after) ===")
    print("%-6s %-4s %-16s %-16s %-16s" % ("W", "h", "<=2016", "<=2018", "<=2020"))
    for W in WS:
        for h in (0.5, 1, 2, 4):
            rs = q_samples(W, h)
            row = []
            for c in (2016, 2018, 2020):
                cal = sorted(v for t, v in rs if t <= c)
                ev = [v for t, v in rs if t > c]
                if len(cal) < 3 or not ev:
                    row.append("-")
                    continue
                b = max(0.0, -cal[int(0.05 * (len(cal) - 1))])
                row.append(f"{sum(v >= -b for v in ev) / len(ev):.0%}({len(ev)}) b={b:.2f}")
            print("%-6s %-4g %-16s %-16s %-16s" % (f"{W:g}y", h, *row))

    print("\n=== false positives on the true chain (guarded band) ===")
    for W in WS:
        for h in (0.5, 1, 2, 4, 10):
            rs = q_samples(W, h)
            b = band(W, h)
            if not rs:
                continue
            fp = sum(1 for _, v in rs if v < -b)
            live = q_at(W, h, X_NOW - h)
            tag = "ok" if live >= -b else "FLAGGED"
            print("  W=%gy h=%-4g flagged %d/%d   band=%.2f   live q=%+.2f  %s"
                  % (W, h, fp, len(rs), b, live, tag))

    print("\n=== attacker cost at the band edge (%g $/TH/day) ===" % HASHPRICE)
    print("%-6s %-5s %-14s %-14s %-14s %-10s" %
          ("W", "h", "tip band", "tip 1 block", "cw band", "cw interval"))
    for W in (4.0,):
        for h in (0.5, 1, 2, 4):
            e = X_NOW - h
            model = fit(e, W, BTC)
            from analyze import denom, m_band
            bd = m_band(W, h, BTC) * denom(model, X_NOW)
            d_edge = 10 ** (predict(model, X_NOW) - bd)
            bq = band(W, h)
            tr = trend_work(model, e, X_NOW)
            cw = max(tr / 10 ** bq, floor_work(e))
            print("%-6s %-5g %-14s %-14s %-14s %-10s" %
                  (f"{W:g}y", h, f"{bd:.2f} dex", f"${usd(d_edge * WORK):,.0f}",
                   f"{bq:.2f} dex", f"${usd(cw):,.0f}"))
    print("\nfor scale: 1 day of Bitcoin's present hash rate = $%s"
          % f"{usd(H_NOW * 86400):,.0f}")

    try:
        plot()
    except ImportError:
        pass


def plot(path="diagrams/chainwork_band.png"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    hs = [0.5 * i for i in range(1, 21)]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    for W in WS:
        ax1.plot(hs, [band(W, h) for h in hs], marker="o", ms=3, label=f"W={W:g}y")
    ax1.set_xlabel("staleness h (years)"); ax1.set_ylabel("one-sided band (dex)")
    ax1.set_title("chainwork band vs staleness (guarded)")
    ax1.grid(alpha=0.25); ax1.legend()

    W = 4.0
    tips, cw = [], []
    for h in hs:
        e = X_NOW - h
        model = fit(e, W, BTC)
        from analyze import denom, m_band
        bd = m_band(W, h, BTC) * denom(model, X_NOW)
        tips.append(usd(10 ** (predict(model, X_NOW) - bd) * WORK))
        cw.append(usd(max(trend_work(model, e, X_NOW) / 10 ** band(W, h), floor_work(e))))
    ax2.semilogy(hs, tips, marker="o", ms=3, label="tip difficulty, one block")
    ax2.semilogy(hs, cw, marker="s", ms=3, label="chainwork over interval")
    ax2.set_xlabel("staleness h (years)"); ax2.set_ylabel("attacker cost (USD)")
    ax2.set_title(f"cost to sit at the band edge (W={W:g}y, ${HASHPRICE}/TH/day)")
    ax2.grid(which="both", alpha=0.25); ax2.legend()

    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)
    print(f"\nwrote {path}")


if __name__ == "__main__":
    main()
