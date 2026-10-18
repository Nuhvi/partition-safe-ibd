#!/usr/bin/env python3
"""Exp 1 - the shape of the rule: Phi(T), the safe band, and the staleness window.

For a fixed compile-time checkpoint t0 the node's threshold is

    bar(T) = THETA * Dhat(t0,T) * 2**32

and the honest chain carries W_h(T) since t0, so

    Phi(T) = bar / W_h = THETA * (Dhat/D0) / (G(T) * T/600)

with G(T) = mean difficulty over [t0,t0+T] / D0.  The honest chain finalizes iff
Phi <= 1; an s-attacker is kept out iff Phi > s.  Hence the *safe band*

    s < Phi(T) <= 1                                     (correct finalisation)

which for growing difficulty is a window in staleness:
  too fresh   -> Phi > 1  (the honest chain has not yet done THETA blocks)
  too stale   -> Phi <= s (the fork has had time to do THETA blocks too)

Outputs figures/window.png and figures/window_vs_share.png.
"""
import math

import figs
import model as M
from figs import BLUE, GREEN, INK, ORANGE, PURPLE, RED, GREY

SHARES = (0.001, 0.01, 0.1, 0.34)
ANCHORS = (2014, 2016, 2019, 2022, 2024)
EST = "exp-2y-cap2x"


def anchor_at(year):
    i = min(range(len(M.BTC.rows)), key=lambda i: abs(M.BTC.x(M.BTC.t[i]) - (year - 2009)))
    return M.BTC.t[i]


def fmt(T):
    if T is None:
        return "never"
    if T < 3600:
        return f"{T/60:.0f}m"
    if T < 86400 * 3:
        return f"{T/3600:.1f}h"
    if T < 86400 * 365:
        return f"{T/86400:.1f}d"
    return f"{T/86400/365:.1f}y"


def phi_curve(t0, est, Ts):
    out = []
    for T in Ts:
        w = M.BTC.work(t0, t0 + T)
        out.append(M.bar(t0, T, est) / w if w > 0 else float("inf"))
    return out


def oracle_curve(t0, Ts):
    """Phi with a perfect estimator (Dhat = true current difficulty)."""
    out = []
    for T in Ts:
        w = M.BTC.work(t0, t0 + T)
        out.append(M.THETA * M.BTC.D(t0 + T) * M.WORK / w if w > 0 else float("inf"))
    return out


def main():
    # ---- figure A: Phi(T) with the safe band ------------------------------
    fig, (ax, ax2) = figs.plt.subplots(1, 2, figsize=(12.5, 5.0))
    Ts = [3600 * 2 ** (k / 4) for k in range(0, 61)]           # 2h .. ~8y
    cols = [BLUE, GREEN, ORANGE, RED, PURPLE]
    for yr, c in zip(ANCHORS, cols):
        t0 = anchor_at(yr)
        Ts_c = [T for T in Ts if t0 + T <= M.BTC.t1]
        ys = phi_curve(t0, EST, Ts_c)
        ax.plot([T / 86400 for T in Ts_c], ys, color=c, lw=2, label=f"{yr} checkpoint")
    ax.axhspan(0.001, 1, color=figs.SAFE, zorder=0)
    ax.axhline(1, color=INK, lw=1.2)
    ax.axhline(0.01, color=RED, ls="--", lw=1.2)
    ax.text(0.09, 1.25, "Phi > 1: honest chain too young, nothing finalises",
            fontsize=8, color=GREY)
    ax.text(0.09, 0.012, "Phi <= 1% : a 1% fork would pass", fontsize=8, color=RED)
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_ylim(1e-4, 1e3)
    ax.set_xlim(0.08, 3000)
    ax.set_xlabel("checkpoint staleness T (days)")
    ax.set_ylabel("Phi = required work / honest work")
    ax.set_title(f"A. the safe band  s < Phi <= 1  (rule: {EST}, THETA={M.THETA})")
    ax.legend(loc="lower left", fontsize=8)

    # ---- figure B: window ends vs attacker share, one anchor --------------
    t0 = anchor_at(2022)
    Ts_b = [3600 * 2 ** (k / 8) for k in range(0, 121)]
    Ts_b = [T for T in Ts_b if t0 + T <= M.BTC.t1]
    ys = phi_curve(t0, EST, Ts_b)
    ax2.plot([T / 86400 for T in Ts_b], ys, color=INK, lw=2.4, label="Phi(T)")
    ax2.axhspan(0.0005, 1, color=figs.SAFE, zorder=0)
    ax2.axhline(1, color=INK, lw=1.2)
    for s, c in zip(SHARES, [BLUE, GREEN, ORANGE, RED]):
        ax2.axhline(s, color=c, ls="--", lw=1.1)
        ax2.text(Ts_b[0] / 86400 * 1.05, s * 1.08, f"{100*s:g}%", color=c, fontsize=8)
    ax2.set_xscale("log"); ax2.set_yscale("log")
    ax2.set_ylim(5e-4, 1e3); ax2.set_xlim(Ts_b[0] / 86400, Ts_b[-1] / 86400)
    ax2.set_xlabel("checkpoint staleness T (days)")
    ax2.set_ylabel("Phi")
    ax2.set_title(f"B. one checkpoint ({figs.ymd(t0)}): the window\n"
                  "below 1: finalises; below a share: that attacker passes")
    ax2.legend(loc="lower left", fontsize=8)
    figs.save(fig, "window.png")

    # ---- table: window ends ----------------------------------------------
    print(f"\nwindow ends by attacker share, rule={EST}, THETA={M.THETA}")
    print("%-10s %-9s %-9s %-9s %s" % ("checkpoint", "T_lo", "T_hi(1%)",
                                        "T_hi(34%)", "T_hi/T_lo (1%)"))
    for yr in ANCHORS:
        t0 = anchor_at(yr)
        lo = M.finalize_time(t0, 1.0, EST)
        hi1 = M.finalize_time(t0, 0.01, EST)
        hi34 = M.finalize_time(t0, 0.34, EST)
        ratio = (hi1 / lo) if (hi1 and lo) else float("nan")
        print("%-10s %-9s %-9s %-9s %.1f" % (figs.ymd(t0), fmt(lo), fmt(hi1),
                                             fmt(hi34), ratio))


if __name__ == "__main__":
    main()
