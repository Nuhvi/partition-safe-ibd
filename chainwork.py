#!/usr/bin/env python3
"""Report and figures for the work-since-anchor rule (see README §2).

The statistic, calibration and decision live in finality.py; this module only
prints the tables and draws diagrams/chainwork_grid.png.

Usage:  python3 chainwork.py [W ...]     (default 2 4 8)
"""
import math
import sys

from finality import (BTC, X_NOW, H_NOW, WORK, HASHPRICE, usd, load, fit,
                      work_between, trend_work, q_at, q_samples, band_raw,
                      band, band_ci, floor_work, envelope_report)

QS = (0.5, 1.0, 2.0, 4.0, 6.0, 10.0)
WS = [float(a) for a in sys.argv[1:]] or [2.0, 4.0, 8.0]


def main():
    print("chainwork statistic q = log10(work since anchor) - log10(trend integral)")
    print("one-sided band on q, isotonic-calibrated; floor = one block at anchor difficulty")
    print()

    print("=== bands (dex, raw -> isotonic) ===")
    print("%-6s %s" % ("W", "".join("%-13s" % f"h={h:g}" for h in QS)))
    for W in WS:
        cells = []
        for h in QS:
            raw = band_raw(W, h)
            g = band(W, h)
            cells.append(f"{raw:.2f}->{g:.2f}" if raw is not None else "n/a")
        print("%-6s %s" % (f"{W:g}y", "".join("%-13s" % c for c in cells)))

    print("\n=== support and band interval (bootstrap 5-95%%) ===")
    print("%-6s %-5s %-5s %-9s %-16s %s" % ("W", "h", "n", "band", "interval", "verdict"))
    for W in WS:
        for h in (0.5, 1, 2, 4, 10):
            n = len(q_samples(W, h))
            ci = band_ci(W, h)
            verdict = "ok" if n >= 8 else "thin"
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

    print("\n=== false positives on the true chain (calibrated band) ===")
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
    print("%-6s %-5s %-14s %-14s" % ("W", "h", "interval work", "network-days"))
    for W in (4.0,):
        for h in (0.5, 1, 2, 4):
            e = X_NOW - h
            model = fit(e, W, BTC)
            cw = max(trend_work(model, e, X_NOW) / 10 ** band(W, h), floor_work(e))
            print("%-6s %-5g %-14s %-14.1f"
                  % (f"{W:g}y", h, f"${usd(cw):,.0f}", cw / (H_NOW * 86400)))
    print("\nfor scale: 1 day of Bitcoin's present hash rate = $%s"
          % f"{usd(H_NOW * 86400):,.0f}")
    print("\n" + envelope_report())

    try:
        fig_grid()
    except ImportError:
        pass


def fig_grid(W=4.0, Ss=(0.5, 1, 2, 3, 4, 6, 8),
             starts=(2018, 2020, 2022, 2024, 2026), path="diagrams/chainwork_grid.png"):
    """The start grid: worst-case fork margin and the true chain.

    A fork is judged only when its sampled series spans the whole anchor->start
    interval; otherwise the cell is left blank (that anchor cannot see it).
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    series = {c: load(c) for c in ("BCH", "BSV", "XEC")}
    bandg = np.full((len(Ss), len(starts)), np.nan)
    forkg = np.full_like(bandg, np.nan)
    trueg = np.full_like(bandg, np.nan)
    for i, S in enumerate(Ss):
        b = band(W, S)
        for j, cal in enumerate(starts):
            x0 = cal - 2009.0
            anchor = x0 - S
            model = fit(anchor, W, BTC)
            if not model or anchor - W < 1.0 or S <= 0:
                continue
            bandg[i, j] = b
            tr = trend_work(model, anchor, x0)
            wt = work_between(anchor, x0, BTC)
            trueg[i, j] = (math.log10(wt) - math.log10(tr) + b) if wt > 0 else np.nan
            margins = []
            for c, pts in series.items():
                if pts[0][0] > anchor:          # series does not reach the anchor
                    continue
                w = work_between(anchor, x0, pts)
                if w > 0:
                    margins.append(math.log10(w) - math.log10(tr) + b)
            if margins:
                forkg[i, j] = -max(margins)     # detection margin; worst = hardest to catch

    fig, axes = plt.subplots(1, 3, figsize=(17, 5.2))
    for ax, G, title, cmap in (
            (axes[0], bandg, f"band half-width (dex), W={W:g}y", "viridis"),
            (axes[1], forkg, "worst fork detection margin = band − q  (>0 = caught)", "RdYlGn"),
            (axes[2], trueg, "true chain margin, >0 = passes its own band", "RdYlGn")):
        vmin, vmax = (None, None) if cmap == "viridis" else (-3, 3)
        im = ax.imshow(G, cmap=cmap, aspect="auto", origin="lower", vmin=vmin, vmax=vmax)
        for i in range(len(Ss)):
            for j in range(len(starts)):
                if not math.isnan(G[i, j]):
                    ax.text(j, i, f"{G[i,j]:.1f}", ha="center", va="center", fontsize=7)
                elif not math.isnan(bandg[i, j]):
                    ax.text(j, i, "no fork", ha="center", va="center", fontsize=6, color="#555")
        ax.set_xticks(range(len(starts))); ax.set_xticklabels(starts)
        ax.set_yticks(range(len(Ss))); ax.set_yticklabels(Ss)
        ax.set_xlabel("node start year"); ax.set_ylabel("checkpoint staleness (years)")
        ax.set_title(title, fontsize=10)
        fig.colorbar(im, ax=ax, fraction=0.046)
    fig.suptitle("Start grid on the work-since-anchor rule")
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
