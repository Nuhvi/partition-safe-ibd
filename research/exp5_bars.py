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
    """The setup: a trusted spine to t0, two continuations from t0 (honest chain
    and an s-share fork), and the node's clock."""
    from matplotlib.patches import Rectangle

    fig, ax = figs.plt.subplots(figsize=(11.5, 4.2))
    ax.set_xlim(0, 100); ax.set_ylim(0, 6.8)
    ax.axis("off")

    x0, x1, x2 = 8, 44, 94          # spine start, checkpoint t0, t_now
    bw, bh = 2.4, 0.5               # block size
    y_hn, y_sp, y_fk = 5.5, 4.2, 2.5

    def chain(xa, xb, y, gap, color):
        x = xa
        while x + bw <= xb + 1e-9:
            ax.add_patch(Rectangle((x, y - bh / 2), bw, bh, facecolor=color,
                                   edgecolor="white", lw=0.7, zorder=3))
            x += bw + gap

    chain(x0, x1, y_sp, 0.7, INK)
    ax.text((x0 + x1) / 2, y_sp - bh / 2 - 0.3,
            "trusted header spine — hard-coded at compile time",
            ha="center", va="top", color=INK, fontsize=10, weight="bold")

    chain(x1, x2, y_hn, 1.1, GREEN)
    ax.text((x1 + x2) / 2, y_hn + bh / 2 + 0.3,
            "honest chain — the whole network, work $W_h$",
            ha="center", va="bottom", color=GREEN, fontsize=10, weight="bold")

    chain(x1, x2, y_fk, 5.6, ORANGE)
    ax.text((x1 + x2) / 2, y_fk - bh / 2 - 0.3,
            "fork seen while partitioned — share $s$, work $s\\,W_h$",
            ha="center", va="top", color=ORANGE, fontsize=10, weight="bold")

    ax.plot(x1, y_sp, "o", color=RED, ms=9, zorder=6)
    ax.text(x1 + 0.6, y_sp - 0.95, "checkpoint $t_0$\n(difficulty $D_0$)",
            ha="left", va="top", color=RED, fontsize=9)

    ax.plot([x2, x2], [1.15, 6.15], color=GREY, ls=(0, (5, 3)), lw=1.3, zorder=1)
    ax.text(x2 + 0.8, 6.15, "$t_{\\mathrm{now}}$", ha="left", va="top",
            color=GREY, fontsize=10)

    ax.annotate("", xy=(x2, 1.35), xytext=(x1, 1.35),
                arrowprops=dict(arrowstyle="<->", color=GREY, lw=1.6))
    ax.text((x1 + x2) / 2, 1.02, "$T = t_{\\mathrm{now}} - t_0$   (the node's clock)",
            ha="center", va="top", color=GREY, fontsize=9)

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
