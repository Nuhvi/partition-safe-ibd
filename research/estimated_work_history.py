#!/usr/bin/env python3
"""Phi over the whole history from selected checkpoints.

The network-share lines are honest-work lines:
    s network -> s/(1-s) of honest work.
So 5% network = 0.0526 and 10% network = 0.1111 on this axis.

The thin dark line is the worst of all sampled 2016+ checkpoints; the dashed
line is the median-law version of that worst anchor.

Outputs figures/estimated_work_history.png.
"""
import math

import model as M
import figs
from figs import BLUE, GREEN, INK, ORANGE, PURPLE, RED

NOW = M.BTC.t1
POINTS = ((2016, BLUE), (2018, ORANGE), (2020, GREEN),
          (2022, PURPLE), (2024, RED))
H5 = M.network_share_to_honest(0.05)
H10 = M.network_share_to_honest(0.10)


def anchor(year):
    i = min(range(len(M.BTC.rows)),
            key=lambda i: abs(M.BTC.x(M.BTC.t[i]) - (year - 2009)))
    return M.BTC.t[i]


def year_of(t):
    return 2009 + M.BTC.x(t)


def scan(phi=M.phi_est):
    """Worst Phi, its anchor and T, and the number of sampled anchors."""
    best = (float("inf"), None, None)
    n = 0
    for r in M.BTC.rows:
        t0 = r[1]
        if year_of(t0) < 2016 or t0 >= NOW - 86400:
            continue
        n += 1
        for k in range(1, 80):
            T = (NOW - t0) * k / 80
            p = phi(t0, T)
            if p < best[0]:
                best = (p, t0, T)
    return best + (n,)


def fig():
    worst, wt0, wT, n = scan()
    med_min, _, _, _ = scan(M.phi_est_median)
    t24 = anchor(2024)
    phi24 = M.phi_est_median(t24, NOW - t24)
    edge = worst / (1.0 + worst)

    fig, ax = figs.plt.subplots(figsize=(12.5, 5.2))
    ax.fill_between([year_of(t) for t in M.BTC.t], H5, 1.0,
                    color=figs.SAFE, alpha=0.7, zorder=0,
                    label="5%-safe band")
    ax.axhline(H5, color=INK, lw=1.0, ls=":", label="5% network")
    ax.axhline(H10, color=INK, lw=1.0, ls="--", label="10% network")
    ax.axhline(1.0, color=INK, lw=1.0, ls="-", label="honest limit")

    for yr, c in POINTS:
        t0 = anchor(yr)
        Ts = [k * (NOW - t0) / 240 for k in range(1, 241)]
        xs = [year_of(t0 + T) for T in Ts]
        ys = [M.phi_est(t0, T) for T in Ts]
        ax.plot(xs, ys, color=c, lw=1.7, zorder=3, label=str(yr))

    # worst sampled anchor
    Ts = [k * (NOW - wt0) / 240 for k in range(1, 241)]
    ax.plot([year_of(wt0 + T) for T in Ts],
            [M.phi_est(wt0, T) for T in Ts],
            color=INK, lw=2.0, zorder=4,
            label=f"worst anchor {year_of(wt0):.2f}")
    ax.plot([year_of(wt0 + wT)], [worst], "o", color=INK, ms=5, zorder=6)
    # median-law version of the same anchor
    ax.plot([year_of(wt0 + T) for T in Ts],
            [M.phi_est_median(wt0, T) for T in Ts],
            color=INK, lw=1.0, ls="--", zorder=2,
            label="median law (worst anchor)")

    ax.set_yscale("log")
    ax.set_ylim(0.03, 3)
    ax.set_yticks([0.03, H5, H10, 0.3, 1, 3])
    ax.set_yticklabels(["0.03", "0.0526", "0.1111", "0.3", "1", "3"])
    ax.set_xlim(2010, math.ceil(year_of(NOW)))
    ax.set_xlabel("year")
    ax.set_ylabel("Phi = bar / honest work")
    ax.set_title("Phi over time: 5% network is safe; 10% network is not in "
                 "2016-20\nbottom law; worst of "
                 f"{n} sampled checkpoints: {year_of(wt0):.2f}, "
                 f"Phi={worst:.4f} (max network {100*edge:.2f}%); "
                 "5% line = 5.26% of honest work, 10% line = 11.11%")
    ax.legend(fontsize=7.5, loc="upper right", ncol=2)
    ax.grid(alpha=0.25)
    note = " (above the honest limit)" if phi24 > 1.0 else ""
    ax.text(0.01, 0.03,
            f"all {n} sampled 2016+ checkpoints: min Phi = {worst:.4f} "
            f"({year_of(wt0):.2f})\n"
            f"max network edge = {100*edge:.2f}%; 5% line = 0.0526 "
            f"({100*(edge/0.05 - 1):.1f}% margin)\n"
            f"median law: min Phi = {med_min:.3f}; "
            f"2024 anchor now = {phi24:.2f}{note}",
            transform=ax.transAxes, va="bottom", fontsize=7.2,
            bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="0.7",
                      alpha=0.9))
    print(f"worst Phi {worst:.5f} at {year_of(wt0):.2f}; "
          f"max network {100*edge:.2f}%")
    print(f"median law: min Phi {med_min:.5f}; "
          f"2024 anchor now {phi24:.3f}")
    figs.save(fig, "estimated_work_history.png")


def main():
    fig()


if __name__ == "__main__":
    main()
