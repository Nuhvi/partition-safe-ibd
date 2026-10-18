#!/usr/bin/env python3
"""Exp 6 - a self-calibrating power-law band.

Idea: fit the difficulty power law to the trailing 4 years before a checkpoint
t0, then draw the trend forward.  The margin the band needs is not imported from
anywhere - it is the margin the *same line* needed, looking backwards, to contain
the data it was fitted to (the largest residual of the fit).  Projected forward,
the band asks: does the future wander further off the line than the past did?

For each checkpoint we plot (a) the all-history power-law trend, (b) that trend
lifted by its own past max-residual - the "band it would need to fit its own
data", and (c) the realised difficulty.  The write-up's threshold is the error
tolerance 1/s, so the band only has to reach s*Dtrue, not Dtrue; the printed
table gives coverage with that allowance.

Outputs figures/plaw_band.png.
"""
import math

import figs
import model as M
from figs import BLUE, GREEN, INK, ORANGE, PURPLE

POINTS = (2014, 2017, 2020, 2023)
COLS = (BLUE, GREEN, ORANGE, PURPLE)
ANCH = [r[1] for r in M.BTC.rows if M.BTC.x(r[1]) >= M.FIRST]


def year_of(t):
    return 2009 + M.BTC.x(t)


def fit_past(t0):
    """Anchored power law over all history <= t0.  Returns (pred_log10, max_resid)."""
    x0 = math.log10(M.BTC.x(t0))
    y0 = math.log10(M.BTC.D(t0))
    num = den = 0.0
    res = 0.0
    rows = [r for r in M.BTC.rows
            if M.BTC.x(r[1]) >= M.PLAW_FLOOR
            and (t0 - M.PLAW_WIN * M.YEAR) <= r[1] <= t0 and r[2] > 0]
    for r in rows:
        x = math.log10(M.BTC.x(r[1]))
        y = math.log10(r[2])
        num += (x - x0) * (y - y0)
        den += (x - x0) ** 2
    p = num / den if den > 0 else 0.0
    for r in rows:
        x = math.log10(M.BTC.x(r[1]))
        y = math.log10(r[2])
        res = max(res, abs(y - (y0 + p * (x - x0))))
    return (lambda T: y0 + p * math.log10(M.BTC.x(t0 + T) / M.BTC.x(t0))), p, res


def fig():
    fig, ax = figs.plt.subplots(figsize=(11, 5.6))
    ax.plot([year_of(t) for t in M.BTC.t], M.BTC.d, color=INK, lw=1.8,
            label="actual BTC difficulty", zorder=5)

    for yr, c in zip(POINTS, COLS):
        i = min(range(len(M.BTC.rows)), key=lambda i: abs(M.BTC.x(M.BTC.t[i]) - (yr - 2009)))
        t0 = M.BTC.t[i]
        pred, p, resid = fit_past(t0)
        Ts = [(M.BTC.t1 - t0) * k / 60 for k in range(0, 61)]
        xs = [year_of(t0 + T) for T in Ts]
        ys = [10 ** pred(T) for T in Ts]
        ax.plot(xs, ys, color=c, lw=1.8, ls="--", zorder=3,
                label=f"fit to history ≤ {yr} (slope {p:.0f})")
        ax.fill_between(xs, ys, [y * 10 ** resid for y in ys], color=c, alpha=0.13,
                        lw=0)
        ax.plot(xs, [y * 10 ** resid for y in ys], color=c, lw=1.0, ls=":", alpha=0.9)
        ax.plot([year_of(t0)], [M.BTC.D(t0)], "o", color=c, ms=5, zorder=6)

    ax.plot([], [], color=INK, lw=1.0, ls=":", label="band = each fit's own max past residual")
    ax.set_yscale("log")
    ax.set_xlim(2011, 2027)
    ax.set_ylim(1e3, 3e16)
    figs.plain_log(ax, "y", [1e3, 1e6, 1e9, 1e12, 1e15])
    ax.set_xlabel("year")
    ax.set_ylabel("difficulty")
    ax.set_title("a power law fitted to the trailing 4 years, lifted by the margin that same\n"
                 "fit needed to contain its own data, projected forward")
    ax.legend(fontsize=8, loc="upper left")
    figs.save(fig, "plaw_band.png")


def table():
    print("coverage of the self-calibrated band (anchored fit, all prior history)")
    print("band = max past residual; covered if  forward need <= band + log10(1/s)")
    print("%-7s %-10s %-10s %-10s"%("T","s=1%","s=34%","need<=band"))
    for T in (90, 365, 730, 1095):
        cmax = {0.01: 0, 0.34: 0}; plain = 0; tot = 0
        for t0 in ANCH:
            if t0 + T * 86400 > M.BTC.t1:
                continue
            pred, p, resid = fit_past(t0)
            need = math.log10(M.BTC.D(t0 + T * 86400)) - pred(T * 86400)
            tot += 1
            plain += need <= resid
            for s in (0.01, 0.34):
                cmax[s] += need <= resid + math.log10(1 / s)
        print("%-7s %-10s %-10s %-10s" % (f"{T}d", f"{100*cmax[0.01]/tot:.0f}%",
              f"{100*cmax[0.34]/tot:.0f}%", f"{100*plain/tot:.0f}%"))


if __name__ == "__main__":
    fig()
    table()
