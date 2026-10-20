#!/usr/bin/env python3
"""Phi over the whole history from selected checkpoints.

The 5%-safe band is 0.05 < Phi <= 1.  The 5% path stays inside it; the 10%
path dips below 0.10 in 2018-2020.

Outputs figures/estimated_work_history.png.
"""
import model as M
import figs
from figs import BLUE, GREEN, INK, ORANGE, PURPLE, RED

NOW = M.BTC.t1
POINTS = ((2016, BLUE), (2018, ORANGE), (2020, GREEN),
          (2022, PURPLE), (2024, RED))


def anchor(year):
    i = min(range(len(M.BTC.rows)),
            key=lambda i: abs(M.BTC.x(M.BTC.t[i]) - (year - 2009)))
    return M.BTC.t[i]


def year_of(t):
    return 2009 + M.BTC.x(t)


def fig():
    fig, ax = figs.plt.subplots(figsize=(12.5, 5.2))
    ax.fill_between([year_of(t) for t in M.BTC.t], 0.05, 1.0,
                    color=figs.SAFE, alpha=0.7, zorder=0,
                    label="5%-safe band")
    ax.axhline(0.05, color=INK, lw=1.0, ls=":", label="5%")
    ax.axhline(0.10, color=INK, lw=1.0, ls="--", label="10%")
    ax.axhline(1.0, color=INK, lw=1.0, ls="-", label="honest limit")

    for yr, c in POINTS:
        t0 = anchor(yr)
        Ts = [k * (NOW - t0) / 240 for k in range(0, 241)]
        xs = [year_of(t0 + T) for T in Ts]
        ys = [M.phi_est(t0, T) for T in Ts]
        ax.plot(xs, ys, color=c, lw=1.8, zorder=3, label=str(yr))

    ax.set_yscale("log")
    ax.set_ylim(0.03, 3)
    ax.set_yticks([0.03, 0.05, 0.1, 0.3, 1, 3])
    ax.set_yticklabels(["0.03", "0.05", "0.1", "0.3", "1", "3"])
    ax.set_xlim(2010, 2027)
    ax.set_xlabel("year")
    ax.set_ylabel("Phi = bar / honest work")
    ax.set_title("Phi over time: 5% is safe; 10% is not in 2016-20\n"
                 "Phi = estimated-work bar / honest work; a share s is safe when Phi > s; "
                 "the honest chain is live when Phi <= 1")
    ax.legend(fontsize=8, loc="upper right", ncol=2)
    ax.grid(alpha=0.25)
    ax.text(0.01, 0.03,
            "5% line: never crossed = 5% safe\n"
            "10% line: crossed in 2016-20 = 10% not",
            transform=ax.transAxes, va="bottom", fontsize=7.5,
            bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="0.7",
                      alpha=0.9))
    figs.save(fig, "estimated_work_history.png")


def main():
    fig()


if __name__ == "__main__":
    main()
