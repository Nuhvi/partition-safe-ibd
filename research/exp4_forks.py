#!/usr/bin/env python3
"""Exp 4 - protection horizon, and what the rule says about real forks.

(a) Horizon: for every checkpoint and share s, the first staleness at which a
    fork of share s clears the bar, T_hi(t0,s).  Its median over checkpoints is
    how long the rule holds; the 10th percentile is the unlucky case.

(b) Real forks: BCH/BSV/XEC carry Bitcoin's genuine work up to their split, so
    their work since a checkpoint is  W_BTC(t0,split) + W_fork(split,now).  With
    a checkpoint younger than the split a real fork is far below the bar; with a
    checkpoint *older* than the split the shared prefix alone can clear it.

Outputs figures/horizon.png.
"""
import math

import figs
import model as M
from figs import BLUE, GREEN, GREY, INK, ORANGE, PURPLE, RED, SAFE

RULES = ("flat", "exp-2y-cap2x", "flatbar", "ols-4y+2sd")
SGRID = (0.001, 0.003, 0.01, 0.03, 0.1, 0.2, 0.34, 0.49)
FORK_STEP = 20160


def anchor(year):
    i = min(range(len(M.BTC.rows)), key=lambda i: abs(M.BTC.x(M.BTC.t[i]) - (year - 2009)))
    return M.BTC.t[i]


def horizon_table():
    anchors = [anchor(y) for y in (2012, 2014, 2016, 2018, 2020, 2022, 2024)]
    print("protection horizon: T_hi(t0,s) = first staleness where a fork of share")
    print("s clears the bar.  Median (10th pct) over checkpoints [2011+].\n")
    print("%-14s %s" % ("rule", "".join("%-16s" % f"s={100*s:g}%" for s in SGRID)))
    for est in RULES:
        cells = []
        for s in SGRID:
            ts = [M.finalize_time(t0, s, est) for t0 in anchors]
            ok = sorted(t for t in ts if t)
            if not ok:
                cells.append("never")
                continue
            med = ok[len(ok) // 2]
            p10 = ok[int(0.1 * (len(ok) - 1))]
            fmt = lambda T: (f"{T/86400/365:.1f}y" if T > 86400 * 60 else
                             (f"{T/86400:.0f}d" if T > 86400 else f"{T/3600:.0f}h"))
            cells.append(f"{fmt(med)} ({fmt(p10)})")
        print("%-14s %s" % (est, "".join("%-16s" % c for c in cells)))


def collect_forks():
    """For each (chain, checkpoint) -> (work/bar for flatbar, work/bar for exp-2y-cap2x)."""
    forks = {c: M.Chain(c) for c in ("BCH", "BSV", "XEC")}
    out = []
    for name, fc in forks.items():
        split = fc.t[0]
        for yr in (2015, 2016, 2017.2, 2017.35, 2017.6, 2018, 2019, 2020, 2021):
            t0 = anchor(yr)
            if t0 >= split:
                shared = 0.0
            else:
                shared = M.BTC.work(t0, split)
            own = fc.work(split, fc.t1)
            w = shared + own
            out.append((name, yr, t0, w, shared, own))
    return out


def fork_table():
    print("\nreal forks: candidate work / bar")
    print("%-5s %-9s %-8s %-12s %-12s %s" % ("fork", "checkpoint", "shared %",
                                              "flatbar", "100-block", "growth 3y"))
    for name, yr, t0, w, shared, own in collect_forks():
        fb = w / M.bar(t0, M.BTC.t1 - t0, "flatbar")
        b100 = w / M.bar(t0, M.BTC.t1 - t0, "flat")
        cap = w / M.bar(t0, M.BTC.t1 - t0, "exp-3y")
        print("%-5s %-9s %-8s %-12s %-12s %s"
              % (name, figs.ymd(t0), f"{100*shared/w:5.0f}%", f"{fb:.3g}", f"{b100:.3g}",
                 f"{cap:.3g}"))


def fig_horizon():
    fig, ax = figs.plt.subplots(figsize=(10, 5.4))
    cols = {"flat": GREY, "exp-2y-cap2x": INK, "flatbar": PURPLE, "ols-4y+2sd": ORANGE}
    anchors = [anchor(y) for y in
               (2011.25 + 0.5 * k for k in range(0, 32))]
    for est in RULES:
        xs, med, p10 = [], [], []
        for s in SGRID:
            ts = sorted(t for t in (M.finalize_time(t0, s, est) for t0 in anchors) if t)
            if not ts:
                continue
            xs.append(100 * s)
            med.append(ts[len(ts) // 2] / 86400)
            p10.append(ts[int(0.1 * (len(ts) - 1))] / 86400)
        ax.plot(xs, med, color=cols[est], lw=2, marker="o", ms=4, label=f"{est} (median)")
        ax.plot(xs, p10, color=cols[est], lw=1, ls=":", marker=".")
    ax.set_xscale("log"); ax.set_yscale("log")
    figs.plain_log(ax, "x", [0.1, 1, 10, 50])
    figs.plain_log(ax, "y", [1, 3, 10, 30, 100, 300, 1000])
    ax.set_xlabel("attacker share of honest hash rate (%)")
    ax.set_ylabel("checkpoint age at which the fork passes (days)")
    ax.set_title("protection horizon: how long the checkpoint stays safe "
                 "(solid = median checkpoint, dotted = 10th pct)")
    ax.legend(fontsize=8)
    figs.save(fig, "horizon.png")


def main():
    horizon_table()
    fork_table()
    fig_horizon()


if __name__ == "__main__":
    main()
