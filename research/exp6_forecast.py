#!/usr/bin/env python3
"""Exp 6 - does the difficulty trendline actually predict the future?

The recommended rule rides on one forecast: extrapolate the trailing 3-year
difficulty growth rate to guess the difficulty the node wakes up into,

    Dhat(t0, T) = D0 * g**(T/1y),      g = (D(t0) / D(t0 - 3y))**(1/3)

Panels A and B put that forecast against the future data it is trying to
predict, rather than reporting it as an abstract error distribution.

(a) forecast vs realised, in the wild.  The realised BTC difficulty curve with
    the 3-year growth line fired from four checkpoints; on a log axis the
    forecast is a straight ray, and the vertical gap to the realised curve is
    the forecast error the rule has to tolerate.

(b) predicted vs realised, pool of checkpoints.  Every historical checkpoint
    (2011+) x staleness gives a (Dhat, D_true) pair.  Points live on the
    diagonal when the forecast is good; the diagonal bands y = x/s mark the
    margin the rule demands per attacker.  A point below the lower band means
    the forecast under-shot by more than 1/s - the unsafe direction - while a
    point above the upper band only delays finalization.

Outputs figures/forecast.png.
"""
import math

import figs
import model as M
from figs import BLUE, GREEN, INK, ORANGE, PURPLE, RED, GREY

EST = "exp-3y"
WIN = 3.0                                   # the estimator's trailing window, years
FCAST_YEARS = (2014, 2017, 2020, 2023)      # panel A: 3y rays that tile the timeline
FCAST_HORIZON = 3 * M.YEAR
ANCH = [r[1] for r in M.BTC.rows if M.BTC.x(r[1]) >= M.FIRST]   # panel B: every period
HORIZONS = [(30, "o"), (90, "s"), (365, "^"), (730, "D")]       # days, marker


def anchor(year):
    i = min(range(len(M.BTC.rows)), key=lambda i: abs(M.BTC.x(M.BTC.t[i]) - (year - 2009)))
    return M.BTC.t[i]


def year_of(t):
    return 2009 + M.BTC.x(t)


def quant(sorted_xs, q):
    if not sorted_xs:
        return float("nan")
    return sorted_xs[min(len(sorted_xs) - 1, int(q * (len(sorted_xs) - 1)))]


def collect():
    """{T_seconds: sorted log10(Dhat/Dtrue)} over every checkpoint."""
    out = {d * 86400: [] for d, _ in HORIZONS}
    for t0 in ANCH:
        for T in out:
            if t0 + T > M.BTC.t1:
                continue
            dhat = M.ESTIMATORS[EST](t0, T)
            dt = M.BTC.D(t0 + T)
            if dhat > 0 and dt > 0:
                out[T].append(math.log10(dhat / dt))
    for T in out:
        out[T].sort()
    return out


def fig_forecast():
    fig, (axA, axB) = figs.plt.subplots(1, 2, figsize=(13.2, 5.4))

    # ---- A: realised difficulty with 3-year forecast rays -----------------
    axA.plot([year_of(t) for t in M.BTC.t], M.BTC.d, color=INK, lw=1.8,
             label="actual BTC difficulty", zorder=3)
    cols = (BLUE, GREEN, ORANGE, PURPLE)
    for yr, c in zip(FCAST_YEARS, cols):
        t0 = anchor(yr)
        Ts = [FCAST_HORIZON * k / 60 for k in range(0, 61)]
        xs = [year_of(t0 + T) for T in Ts]
        ys = [M.ESTIMATORS[EST](t0, T) for T in Ts]
        axA.plot(xs, ys, color=c, lw=2, ls="--",
                 label=f"3 y forecast from {yr}")
        axA.plot([year_of(t0)], [M.BTC.D(t0)], "o", color=c, ms=5, zorder=4)
    axA.annotate("over-shoot = safe\n(only delays finalization)",
                 xy=(2015.2, 3e12), xytext=(2011.4, 3e14), fontsize=8, color=GREY,
                 ha="left", va="center",
                 arrowprops=dict(arrowstyle="->", color=GREY, lw=1))
    axA.annotate("slight under-shoot,\nstill inside 34% margin",
                 xy=(2025.8, 1.3e14), xytext=(2019.9, 8e10), fontsize=8, color=GREY,
                 ha="left", va="center",
                 arrowprops=dict(arrowstyle="->", color=GREY, lw=1,
                                 connectionstyle="arc3,rad=-0.15"))
    axA.set_yscale("log")
    axA.set_xlim(2011, 2027)
    axA.set_ylim(1e3, 1e15)
    figs.plain_log(axA, "y", [1e3, 1e6, 1e9, 1e12, 1e15])
    axA.set_xlabel("year")
    axA.set_ylabel("difficulty")
    axA.set_title("A. the 3-year growth line vs what actually happened\n"
                  "(dashed = forecast, black = realised; gap = forecast error)")
    axA.legend(fontsize=8, loc="lower right")

    # ---- B: predicted vs realised, with the 1/s margin bands --------------
    pts = []
    for t0 in ANCH:
        for T, mk in HORIZONS:
            Ts = T * 86400
            if t0 + Ts > M.BTC.t1:
                continue
            dhat = M.ESTIMATORS[EST](t0, Ts)
            dt = M.BTC.D(t0 + Ts)
            if dhat > 0 and dt > 0:
                pts.append((dhat, dt, T, mk))
    lo, hi = 1e4, 1e15
    xs = [math.log10(lo), math.log10(hi)]
    axB.plot(xs, xs, color=GREY, lw=1.2, label="perfect forecast (D̂ = Dtrue)")
    for s, c, lab in ((0.34, RED, "34% attacker: D̂ = 0.34·Dtrue"),
                      (0.01, GREEN, "1% attacker: D̂ = 0.01·Dtrue")):
        # the forecast must stay *above* s*Dtrue, i.e. below this line; the
        # region above it is an under-shoot by more than 1/s - the unsafe side.
        axB.plot(xs, [x + math.log10(1 / s) for x in xs], color=c, ls=":",
                 lw=1.3, label=lab + " (above = unsafe)")
    cmap = figs.plt.get_cmap("viridis")
    for T, mk in HORIZONS:
        g = [p for p in pts if p[2] == T]
        axB.scatter([math.log10(p[0]) for p in g], [math.log10(p[1]) for p in g],
                    marker=mk, s=16, color=cmap(HORIZONS.index((T, mk)) / (len(HORIZONS) - 1)),
                    edgecolor="white", linewidth=0.3, alpha=0.8,
                    label=f"{T} d", zorder=3)
    axB.set_xlim(xs); axB.set_ylim(xs)
    figs.plain_log(axB, "x", [1e3, 1e6, 1e9, 1e12, 1e15])
    figs.plain_log(axB, "y", [1e3, 1e6, 1e9, 1e12, 1e15])
    axB.set_xlabel("forecast difficulty  D̂")
    axB.set_ylabel("realised difficulty at t0 + T")
    axB.set_title("B. forecast vs realised, every historical checkpoint\n"
                  "(above a dotted line under-shoots by >1/s — the unsafe side)")
    axB.legend(fontsize=8, loc="upper left")

    figs.save(fig, "forecast.png")


def table():
    data = collect()
    print("forecast error log10(Dhat/Dtrue), rule=%s, %d checkpoints" % (EST, len(ANCH)))
    print("%-7s %-6s %-8s %-8s %-8s %-10s %-10s"
          % ("T", "n", "p5", "p50", "p95", ">100x low", ">3x low"))
    for T in sorted(data):
        xs = data[T]
        if not xs:
            continue
        below1 = sum(1 for v in xs if v < -2.0) / len(xs)      # Dhat/Dtrue < 1/100
        below34 = sum(1 for v in xs if v < -math.log10(1 / 0.34)) / len(xs)
        print("%-7s %-6d %-8.2f %-8.2f %-8.2f %-10s %-10s"
              % (f"{T/86400:g}d", len(xs), quant(xs, 0.05), quant(xs, 0.5), quant(xs, 0.95),
                 f"{100*below1:.0f}%", f"{100*below34:.0f}%"))


if __name__ == "__main__":
    fig_forecast()
    table()
