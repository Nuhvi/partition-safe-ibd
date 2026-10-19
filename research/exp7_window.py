#!/usr/bin/env python3
"""Exp 7 - how the fit window changes the power-law trend.

The estimator fits log10(work per block) on log10(age) over a trailing window and
extrapolates it.  The window is the one free choice: short windows adapt to the
current regime but give noisy slopes; long windows are stable but slow to react.
This figure shows the effect.

(a-c) the trend fired from three checkpoints, for windows of 2, 3, 4, 5, 6, 8
      years and for the whole history with and without the 2012-13 ASIC era.
      Only the trend is drawn (bands omitted) so the window's effect on the
      *slope* is what you see.

(d)   the resulting estimator error, 2014+ checkpoints, 2 years ahead: the 5th
      percentile (the low tail - the unsafe side) and the median (over-shoot =
      delay) as the window changes.  The low tail is what picks the window.

Outputs figures/plaw_window.png.
"""
import math

import figs
import model as M
from figs import INK, RED, PURPLE

WINS = [2, 3, 4, 5, 6, 8, "all", "skip"]        # "all" = whole history, "skip" = 2014+ only
CP_YEARS = (2017, 2020, 2023)
ANCH = [r[1] for r in M.BTC.rows if M.BTC.x(r[1]) >= M.FIRST]


def year_of(t):
    return 2009 + M.BTC.x(t)


def anchor(year):
    i = min(range(len(M.BTC.rows)), key=lambda i: abs(M.BTC.x(M.BTC.t[i]) - (year - 2009)))
    return M.BTC.t[i]


def rowset(t0, win):
    if win == "skip":
        return [r for r in M.BTC.rows
                if r[2] > 0 and M.BTC.x(r[1]) >= M.FIRST and r[1] <= t0]
    return M.plaw_window_rows(t0, None if win == "all" else win)


def fit(t0, win):
    """Anchored slope and max residual over the chosen window."""
    return M.plaw_fit(t0, rowset(t0, win))


def trend(t0, T, win):
    f = fit(t0, win)
    if f is None:
        return M.BTC.w(t0)
    y0, x0, p, r = f
    return 10 ** (y0 + p * math.log10(M.BTC.x(t0 + T) / M.BTC.x(t0)))


def est(t0, T, win):
    f = fit(t0, win)
    if f is None:
        return M.BTC.w(t0)
    y0, x0, p, r = f
    return 10 ** (y0 + p * math.log10(M.BTC.x(t0 + T) / M.BTC.x(t0)) + r)


def quant(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * (len(xs) - 1)))]


def fig():
    fig, axes = figs.plt.subplots(2, 2, figsize=(13.5, 9.2))
    cmap = figs.plt.get_cmap("viridis")
    num = [w for w in WINS if isinstance(w, int)]
    styles = {w: (cmap(i / (len(num) - 1)), "-", f"{w} y") for i, w in enumerate(num)}
    styles["all"] = (RED, "--", "all history")
    styles["skip"] = (PURPLE, ":", "all since 2014 (skip ASIC)")

    for ax, yr in zip(axes.flat[:3], CP_YEARS):
        t0 = anchor(yr)
        ax.plot([year_of(t) for t in M.BTC.t], M.BTC.d, color=INK, lw=1.5, zorder=5,
                label="actual difficulty")
        for w in WINS:
            if not rowset(t0, w):
                continue
            Ts = [(M.BTC.t1 - t0) * k / 60 for k in range(0, 61)]
            xs = [year_of(t0 + T) for T in Ts]
            ys = [trend(t0, T, w) / M.WORK for T in Ts]
            c, ls, lab = styles[w]
            ax.plot(xs, ys, color=c, ls=ls, lw=2.6 if w == 4 else 1.4, label=lab)
            ax.plot([year_of(t0)], [M.BTC.D(t0)], "o", color=c, ms=4, zorder=6)
        ax.set_yscale("log")
        ax.set_xlim(2011, 2027)
        ax.set_ylim(1e5, 1e16)
        figs.plain_log(ax, "y", [1e6, 1e9, 1e12, 1e15])
        ax.set_xlabel("year")
        ax.set_ylabel("difficulty")
        ax.set_title(f"trend fired from a {yr} checkpoint, by fit window")
        ax.legend(fontsize=6.5, loc="lower right", ncol=3)

    # ---- D: low tail and median vs window, 2y ahead, 2014+ ---------------
    ax = axes.flat[3]
    xs = list(range(len(WINS)))
    p5s, meds = [], []
    for w in WINS:
        e = [math.log10(est(t0, 2 * M.YEAR, w) / M.BTC.w(t0 + 2 * M.YEAR))
             for t0 in ANCH if t0 + 2 * M.YEAR < M.BTC.t1]
        p5s.append(quant(e, 0.05)); meds.append(quant(e, 0.5))
    ax.plot(xs, meds, "o-", color=INK, label="median (over-shoot = delay)")
    ax.plot(xs, p5s, "s-", color=RED, label="5th pct (low tail — the unsafe side)")
    ax.axhspan(-2.0, -0.47, color="#fdecea", zorder=0)
    ax.axhline(-0.47, color=RED, ls=":", lw=1)
    ax.text(len(WINS) - 1, -0.44, "34% tolerance (−0.47)", ha="right", va="bottom",
            color=RED, fontsize=8)
    ax.axhline(0, color=INK, lw=0.8)
    ax.set_xticks(xs)
    ax.set_xticklabels([f"{w} y" if isinstance(w, int) else ("all" if w == "all" else "≥2014")
                        for w in WINS], fontsize=9)
    ax.set_xlabel("fit window")
    ax.set_ylabel("log10(ŵ/w_true) at 2 y  (dex)")
    ax.set_title("error vs window, 2014+ checkpoints, 2 years ahead")
    ax.legend(fontsize=8, loc="lower left")
    figs.save(fig, "plaw_window.png")


def table():
    print("2y-ahead error by fit window (2014+ checkpoints): p5 / median")
    for w in WINS:
        e = [math.log10(est(t0, 2 * M.YEAR, w) / M.BTC.w(t0 + 2 * M.YEAR))
             for t0 in ANCH if t0 + 2 * M.YEAR < M.BTC.t1]
        lab = f"{w} y" if isinstance(w, int) else ("all history" if w == "all" else "all >=2014")
        print(f"  {lab:12s} p5 {quant(e,.05):+.2f}  median {quant(e,.5):+.2f}  (n={len(e)})")


if __name__ == "__main__":
    fig()
    table()
