#!/usr/bin/env python3
"""Exp 5 - two explanatory diagrams for the write-up.

concept.png  the setup: a trusted spine to t0, an honest chain and a fork from
             t0, the node's clock, and the bar.
bars.png     why a *fixed* bar is overtaken: both the honest chain and an
             s-fork accumulate work in proportion to the elapsed interval, so a
             constant bar (100 blocks) is crossed by the fork, while an
             age-proportional bar stays between the two.
"""
import figs
import model as M
from figs import BLUE, GREEN, INK, ORANGE, RED, GREY


def concept():
    fig, ax = figs.plt.subplots(figsize=(11, 4.4))
    ax.set_xlim(0, 100); ax.set_ylim(0, 7)
    ax.axis("off")

    # trusted spine
    ax.plot([2, 46], [4.6, 4.6], color=INK, lw=7, solid_capstyle="butt")
    for x in range(2, 47, 4):
        ax.plot([x, x], [4.0, 5.2], color=INK, lw=1.2)
    ax.text(24, 5.6, "trusted header spine  (hardcoded at compile time)",
            ha="center", color=INK, fontsize=10, weight="bold")
    ax.plot(46, 4.6, "o", color=RED, ms=9)
    ax.text(46, 3.7, "checkpoint  t0\n(difficulty D0)", ha="center", color=RED, fontsize=9)

    # honest chain
    for i in range(48, 97, 3):
        ax.plot([i, i], [5.6, 6.4], color=GREEN, lw=2)
    ax.plot([46, 96], [6.0, 6.0], color=GREEN, lw=1)
    ax.text(72, 6.7, "honest chain: full network, work W_h",
            ha="center", color=GREEN, fontsize=9, weight="bold")

    # fork
    for i in range(48, 97, 10):
        ax.plot([i, i], [2.6, 3.3], color=ORANGE, lw=2)
    ax.plot([46, 96], [2.95, 2.95], color=ORANGE, lw=1)
    ax.text(72, 2.0, "fork seen while partitioned: share s, work s * W_h",
            ha="center", color=ORANGE, fontsize=9, weight="bold")

    # T arrow
    ax.annotate("", xy=(96, 0.7), xytext=(46, 0.7),
                arrowprops=dict(arrowstyle="<->", color=GREY, lw=1.6))
    ax.text(71, 0.95, "T = t_now - t0   (the node's clock)",
            ha="center", color=GREY, fontsize=9)
    ax.plot(96, 0.7, "v", color=GREY, ms=6)
    ax.text(97, 0.6, "t_now", color=GREY, fontsize=9)

    ax.text(2, 1.6,
            "rule:  finalize the candidate iff its work since t0  >=  the bar\n"
            "       the bar is 100 blocks at the current difficulty, which the\n"
            "       node estimates from the spine",
            ha="left", va="center", fontsize=9, color=INK,
            bbox=dict(boxstyle="round", fc="#f4f6f7", ec=GREY))
    figs.save(fig, "concept.png")


def bars():
    # pick a recent-ish checkpoint with room to extrapolate
    i = min(range(len(M.BTC.rows)), key=lambda i: abs(M.BTC.x(M.BTC.t[i]) - (2021 - 2009)))
    t0 = M.BTC.t[i]
    w0 = M.BTC.w(t0)                     # work of one block at the checkpoint
    Ts = [3600 * 2 ** (k / 6) for k in range(0, 67)]
    Ts = [T for T in Ts if t0 + T <= M.BTC.t1]

    fig, ax = figs.plt.subplots(figsize=(10.5, 5.4))
    honest = [M.BTC.work(t0, t0 + T) / w0 for T in Ts]
    ax.plot([T / 86400 for T in Ts], honest, color=GREEN, lw=2.4,
            label="honest chain (full network)")
    for s, c in ((0.01, BLUE), (0.1, ORANGE), (0.34, RED)):
        ax.plot([T / 86400 for T in Ts], [s * w for w in honest], color=c, lw=1.6,
                label=f"fork with {100*s:g}% of the hash rate")
    ax.plot([T / 86400 for T in Ts], [M.fixed_bar(t0, T, "flat") / w0 for T in Ts],
            color=INK, lw=2.4, ls="--", label="fixed bar: 100 blocks")
    ax.plot([T / 86400 for T in Ts], [M.age_bar(t0, T) / w0 for T in Ts],
            color="#8e44ad", lw=2.4, label="age bar: one block per 10 min of age")
    ax.set_xscale("log"); ax.set_yscale("log")
    figs.plain_log(ax, "x", [0.1, 1, 10, 100])
    figs.plain_log(ax, "y", [10, 100, 1000, 10000])
    ax.set_xlabel("checkpoint age T (days)")
    ax.set_ylabel("work since checkpoint, in blocks at checkpoint difficulty")
    ax.set_title(f"checkpoint {figs.ymd(t0)}: the fixed bar is crossed by the "
                 "fork; the age bar stays between fork and honest")
    ax.legend(fontsize=8, loc="lower right", ncol=2)
    ax.set_ylim(8, 40000)
    figs.save(fig, "bars.png")


if __name__ == "__main__":
    concept()
    bars()
