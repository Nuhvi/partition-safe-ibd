#!/usr/bin/env python3
"""Exp 2 - can the node estimate the difficulty it wakes up into?

The rule needs Dhat(t0,T) ~ D_true(t0+T).  If the estimate is wrong by a factor
of about 1/s, the safe band s < Phi <= 1 closes: the bar can no longer be placed
between the honest chain and an s-attacker.  So the estimator's error is the
whole game.

For every historical checkpoint (2011+) and every staleness T we form
rho = Dhat / D_true and report its distribution as T grows.  The shaded lanes
are the tolerances log10(1/s) for s = 1% and s = 34%: an estimator whose error
stays inside a lane can separate the honest chain from that attacker.

Outputs figures/estimator.png.
"""
import math

import figs
import model as M
from figs import BLUE, GREEN, INK, ORANGE, PURPLE, RED, GREY

THETA = M.THETA
TS = [d * 86400 for d in
      (0.5, 1, 2, 3, 5, 7, 10, 15, 21, 30, 45, 60, 90, 120, 180, 270, 365, 540, 730, 1095)]
TS = [T for T in TS if T <= 3 * M.YEAR]


def quant(sorted_xs, q):
    if not sorted_xs:
        return float("nan")
    return sorted_xs[min(len(sorted_xs) - 1, int(q * (len(sorted_xs) - 1)))]


def anchors():
    return [r[1] for r in M.BTC.rows if M.BTC.x(r[1]) >= M.FIRST]


def collect(est):
    """{T: sorted list of log10(Dhat/Dtrue)}."""
    out = {T: [] for T in TS}
    for t0 in anchors():
        for T in TS:
            if t0 + T > M.BTC.t1:
                continue
            dhat = M.ESTIMATORS[est](t0, T)
            dt = M.BTC.D(t0 + T)
            if dhat > 0 and dt > 0:
                out[T].append(math.log10(dhat / dt))
    for T in out:
        out[T].sort()
    return out


def main():
    data = {est: collect(est) for est in M.ESTIMATORS}
    days = [T / 86400 for T in TS]

    fig, ax = figs.plt.subplots(figsize=(11, 5.6))
    ax.axhspan(0.002, 0.01, color="#fdecea", zorder=0)
    ax.axhline(1, color=INK, lw=1)
    for s, lab, c in ((0.01, "100x", GREEN), (0.34, "3x", RED)):
        tol = 1 / s
        ax.axhline(tol, color=c, ls="--", lw=1)
        ax.text(days[-1] * 0.98, tol * 1.06,
                f"{lab} low is the safe limit (a {100*s:g}% attacker)",
                color=c, fontsize=8, ha="right", va="bottom",
                bbox=dict(fc="white", ec="none", alpha=0.75))
    cols = {"flat": GREY, "flatbar": "#8e44ad", "exp-2y": BLUE, "exp-1y": "#5dade2",
            "exp-3y": "#148f77", "exp-4y": "#b03a2e", "exp-2y-cap2x": INK,
            "ols-4y": ORANGE, "ols-4y+2sd": PURPLE, "max(100,flat)": "#7f8c8d"}
    labels = {"flat": "flat (no growth)", "exp-2y": "growth, 2 y window",
              "exp-3y": "growth, 3 y", "exp-4y": "growth, 4 y",
              "exp-2y-cap2x": "2 y, capped 2x/yr", "ols-4y+2sd": "OLS 4 y + 2 sd"}
    PLOT = ("flat", "exp-2y", "exp-3y", "exp-4y", "exp-2y-cap2x", "ols-4y+2sd")
    for est, d in data.items():
        if est not in PLOT:
            continue
        med = [10 ** quant(d[T], 0.5) for T in TS]
        ax.plot(days, med, color=cols[est], lw=2, label=labels.get(est, est))
        lo = [10 ** quant(d[T], 0.05) for T in TS]
        hi = [10 ** quant(d[T], 0.95) for T in TS]
        ax.fill_between(days, lo, hi, color=cols[est], alpha=0.10)
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlim(days[0], days[-1]); ax.set_ylim(0.002, 200)
    figs.plain_log(ax, "x", [1, 10, 100, 1000])
    figs.plain_log(ax, "y", [0.01, 0.1, 1, 10, 100])
    ax.set_xlabel("checkpoint age T (days)")
    ax.set_ylabel("estimated / true current difficulty   (1 = perfect)")
    ax.set_title("estimator error: above 1 over-estimates (only delays finalization); "
                 "below 1 under-protects")
    ax.legend(ncol=2, fontsize=8, loc="upper left")
    figs.save(fig, "estimator.png")

    # ---- table -----------------------------------------------------------
    show = [86400, 7 * 86400, 30 * 86400, 90 * 86400, 365 * 86400, 2 * 365 * 86400]
    show = [T for T in show if T in data["flat"]]
    print("median log10(Dhat/Dtrue) [dex];  + = overshoot")
    print("%-12s %s" % ("estimator", "".join("%-9s" % f"{T/86400:g}d" for T in show)))
    for est, d in data.items():
        if est == "flatbar":
            continue
        cells = []
        for T in show:
            v = quant(d[T], 0.5)
            cells.append(f"{v:+.2f}")
        print("%-12s %s" % (est, "".join("%-9s" % c for c in cells)))
    print("\n5-95%% spread (dex) and the share s an estimator can still separate")
    print("%-12s %s" % ("estimator", "".join("%-9s" % f"{T/86400:g}d" for T in show)))
    for est, d in data.items():
        if est == "flatbar":
            continue
        cells = []
        for T in show:
            spread = quant(d[T], 0.95) - quant(d[T], 0.05)
            cells.append(f"{spread:.2f}")
        print("%-12s %s" % (est, "".join("%-9s" % c for c in cells)))


if __name__ == "__main__":
    main()
