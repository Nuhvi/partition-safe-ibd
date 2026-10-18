#!/usr/bin/env python3
"""Exp 3 - the backtest the brief asks for.

"how often would the formula have denied the actual best chain from finalizing,
 and how often would it have let a fork through?"

For every historical compile-time checkpoint (2011+) and every staleness T we
evaluate

    Phi(t0,T) = THETA * Dhat(t0,T) * 2**32 / W_honest(t0, t0+T)

  * honest denied     when Phi > 1     (the real chain fails the bar)
  * fork of share s passes when Phi <= s

and report both rates as a function of T, per estimator, plus a heatmap of Phi
over (checkpoint year, staleness) for the recommended estimator.

Outputs figures/availability.png, figures/security.png, figures/phi_heatmap.png.
"""
import math

import figs
import model as M
from figs import BLUE, GREEN, GREY, INK, ORANGE, PURPLE, RED

SHARES = (0.001, 0.01, 0.05, 0.10, 0.34)
ANCH_YEARS = [2011 + 0.25 * k for k in range(0, 62)]     # quarterly checkpoints
TS = [d * 86400 for d in
      (0.5, 1, 2, 3, 5, 7, 14, 21, 30, 45, 60, 90, 120, 180, 270, 365, 540, 730, 1095, 1460)]
EST = "exp-2y-cap2x"
REC = "flatbar"
CURATED = ("flat", "exp-2y-cap2x", "flatbar", "ols-4y+2sd")


def anchor(year):
    i = min(range(len(M.BTC.rows)), key=lambda i: abs(M.BTC.x(M.BTC.t[i]) - (year - 2009)))
    return M.BTC.t[i]


def phi(t0, T, est):
    w = M.BTC.work(t0, t0 + T)
    return M.bar(t0, T, est) / w if w > 0 else float("inf")


def grid(est):
    """[(year, T, phi)] over the anchor x staleness grid."""
    out = []
    for yr in ANCH_YEARS:
        t0 = anchor(yr)
        for T in TS:
            if t0 + T > M.BTC.t1:
                continue
            out.append((yr, T, phi(t0, T, est)))
    return out


def rates(rows):
    """{T: (n, avail_frac, {s: sec_frac})}."""
    out = {}
    for yr, T, p in rows:
        n, av, sec = out.setdefault(T, [0, 0, {s: 0 for s in SHARES}])
        out[T][0] += 1
        out[T][1] += (p <= 1.0)
        for s in SHARES:
            out[T][2][s] += (p <= s)
    return {T: (n, av / n, {s: v / n for s, v in sec.items()})
            for T, (n, av, sec) in out.items() if n}


def main():
    data = {est: rates(grid(est)) for est in M.ESTIMATORS}
    days = [T / 86400 for T in TS]

    # ---- availability -----------------------------------------------------
    fig, ax = figs.plt.subplots(figsize=(10.5, 5.2))
    cols = {"flat": GREY, "flatbar": "#148f77", "exp-2y": BLUE, "exp-1y": "#5dade2",
            "exp-2y-cap2x": INK, "ols-4y": ORANGE, "ols-4y+2sd": PURPLE,
            "max(100,flat)": "#c0392b"}
    labels = {"flat": "flat (no growth)",
              "exp-2y-cap2x": "fixed 100 blocks",
              "flatbar": "age bar (T/600 blocks)", "ols-4y+2sd": "OLS trend + 2 sd"}
    for est, d in data.items():
        if est not in CURATED:
            continue
        ys = [100 * (1 - d[T][1]) if T in d else float("nan") for T in TS]
        ax.plot(days, ys, color=cols[est], lw=2.2, marker="o", ms=3,
                label=labels.get(est, est))
    ax.set_xscale("log"); ax.set_ylim(-3, 103)
    figs.plain_log(ax, "x", [1, 10, 100, 1000])
    ax.set_xlabel("checkpoint age T (days)")
    ax.set_ylabel("checkpoints that DENY the true chain (%)")
    ax.set_title("availability: how often the rule refuses to finalize real Bitcoin\n"
                 "(lower is better)")
    ax.legend(fontsize=8, ncol=2)
    figs.save(fig, "availability.png")

    # ---- security ---------------------------------------------------------
    fig, ax = figs.plt.subplots(figsize=(10.5, 5.2))
    PLOT_SHARES = (0.001, 0.01, 0.10, 0.34)
    scols = {0.001: BLUE, 0.01: GREEN, 0.10: ORANGE, 0.34: RED}
    for est, ls in ((EST, "-"), (REC, ":")):
        d = data[est]
        for s in PLOT_SHARES:
            ys = [100 * d[T][2][s] if T in d else float("nan") for T in TS]
            ax.plot(days, ys, color=scols[s], lw=2, marker="o", ms=3, ls=ls,
                    label=f"{100*s:g}%  ({'fixed 100' if est == EST else 'age bar'})")
    ax.set_xscale("log"); ax.set_ylim(-3, 103)
    figs.plain_log(ax, "x", [1, 10, 100, 1000])
    ax.set_xlabel("checkpoint age T (days)")
    ax.set_ylabel("checkpoints where a fork of share s PASSES (%)")
    ax.set_title("security: fixed 100-block bar (solid) vs age-proportional bar (dotted); "
                 "lower is better")
    ax.legend(fontsize=8, ncol=2)
    figs.save(fig, "security.png")

    # ---- heatmap of Phi ---------------------------------------------------
    rows = grid(REC)
    yidx = {yr: i for i, yr in enumerate(ANCH_YEARS)}
    tidx = {T: j for j, T in enumerate(TS)}
    H = [[float("nan")] * len(TS) for _ in ANCH_YEARS]
    for yr, T, p in rows:
        if T in tidx:
            H[yidx[yr]][tidx[T]] = p
    import numpy as np
    A = np.array(H)
    fig, ax = figs.plt.subplots(figsize=(11, 5.6))
    im = ax.imshow(np.log10(A), aspect="auto", origin="lower", cmap="RdYlGn_r",
                   vmin=-3, vmax=3)
    ax.set_xticks(range(len(TS))); ax.set_xticklabels([f"{d/86400:g}" for d in TS],
                                                      rotation=90, fontsize=7)
    ax.set_yticks(range(0, len(ANCH_YEARS), 4))
    ax.set_yticklabels([f"{ANCH_YEARS[i]:.0f}" for i in range(0, len(ANCH_YEARS), 4)])
    ax.set_xlabel("checkpoint age T (days)"); ax.set_ylabel("checkpoint year")
    ax.set_title(f"Phi, rule={REC}: red = nothing finalizes (Phi>1), "
                 "green = finalizes, dark green = fork territory")
    fig.colorbar(im, ax=ax, fraction=0.035, label="Phi (log scale)")
    figs.save(fig, "phi_heatmap.png")

    # ---- tables -----------------------------------------------------------
    print(f"\navailability: %% of checkpoints denying the true chain")
    print("%-8s %s" % ("T", "".join("%-7s" % f"{d:g}d" for d in (1, 7, 30, 90, 365, 730, 1460))))
    for est in M.ESTIMATORS:
        d = data[est]
        print("%-8s %s" % (est, "".join(
            "%-7s" % (f"{100*(1-d[T][1]):.0f}%" if T in d else "-")
            for T in (86400, 7*86400, 30*86400, 90*86400, 365*86400, 730*86400, 1460*86400))))

    print("\nsecurity: % of checkpoints where a fork of share s passes")
    SCOL = (86400, 7*86400, 30*86400, 90*86400, 365*86400, 730*86400, 1460*86400)
    print("%-12s %-6s %s" % ("estimator", "s", "".join("%-7s" % f"{d/86400:g}d" for d in SCOL)))
    for est in M.ESTIMATORS:
        d = data[est]
        for s in SHARES:
            print("%-12s %-6s %s" % (est, f"{100*s:g}%", "".join(
                "%-7s" % (f"{100*d[T][2][s]:.0f}%" if T in d else "-")
                for T in SCOL)))
        print()


if __name__ == "__main__":
    main()
