#!/usr/bin/env python3
"""Exp 4 - the protection horizon.

For every checkpoint and share s, the first staleness at which a fork of share s
clears the bar, T_hi(t0,s).  The median over the checkpoints that clear inside the
data is how long the rule holds; the 10th percentile is the unlucky case; and the
share that never clears is censoring, so a cell with a high censored share is not
a real median.

Outputs figures/horizon.png.
"""
import figs
import model as M
from figs import GREY, INK, ORANGE, PURPLE

RULES = {
    "flat": M.fixed_rule("flat"),
    "exp-2y-cap2x": M.fixed_rule("exp-2y-cap2x"),
    "age": M.age_bar,
    "ols-4y+2sd": M.fixed_rule("ols-4y+2sd"),
}
SGRID = (0.001, 0.003, 0.01, 0.03, 0.1, 0.2, 0.34, 0.49)
ANCHORS = [r[1] for r in M.BTC.rows if M.BTC.x(r[1]) >= M.FIRST]


def fmt(T):
    if T is None:
        return "never"
    if T > 86400 * 60:
        return f"{T/86400/365:.1f}y"
    if T > 86400:
        return f"{T/86400:.0f}d"
    return f"{T/3600:.0f}h"


def horizons():
    """{rule: {s: [T_hi or None per anchor]}} - computed once, used twice."""
    return {rule: {s: [M.finalize_time(t0, s, bar_fn) for t0 in ANCHORS]
                   for s in SGRID}
            for rule, bar_fn in RULES.items()}


def horizon_table(data):
    n = len(ANCHORS)
    print("protection horizon T_hi(t0,s): first staleness at which a fork of share s")
    print(f"clears the bar.  All {n} 2014+ checkpoints.  Each cell is the median")
    print("[10th pct] over the checkpoints that clear inside the data, and the share")
    print("that never does.  A high censored share means the cell is not a real median.\n")
    print("%-13s %s" % ("rule", "".join("%-24s" % f"s={100*s:g}%" for s in SGRID)))
    for rule, per_s in data.items():
        cells = []
        for s in SGRID:
            ts = per_s[s]
            ok = sorted(t for t in ts if t)
            cens = n - len(ok)
            if not ok:
                cells.append("never (%d%%)" % round(100 * cens / n))
                continue
            med = ok[len(ok) // 2]
            p10 = ok[int(0.1 * (len(ok) - 1))]
            cells.append(f"{fmt(med)} [{fmt(p10)}] {100*cens/n:.0f}%")
        print("%-13s %s" % (rule, "".join("%-24s" % c for c in cells)))


def fig_horizon(data):
    fig, ax = figs.plt.subplots(figsize=(10, 5.4))
    cols = {"flat": GREY, "exp-2y-cap2x": INK, "age": PURPLE, "ols-4y+2sd": ORANGE}
    for rule, per_s in data.items():
        xs, med, p10 = [], [], []
        for s in SGRID:
            ts = sorted(t for t in per_s[s] if t)
            if not ts:
                continue
            xs.append(100 * s)
            med.append(ts[len(ts) // 2] / 86400)
            p10.append(ts[int(0.1 * (len(ts) - 1))] / 86400)
        ax.plot(xs, med, color=cols[rule], lw=2, marker="o", ms=4, label=f"{rule} (median)")
        ax.plot(xs, p10, color=cols[rule], lw=1, ls=":", marker=".")
    ax.set_xscale("log"); ax.set_yscale("log")
    figs.plain_log(ax, "x", [0.1, 1, 10, 50])
    figs.plain_log(ax, "y", [1, 3, 10, 30, 100, 300, 1000])
    ax.set_xlabel("attacker share of honest hash rate (%)")
    ax.set_ylabel("checkpoint age at which the fork passes (days)")
    ax.set_title("protection horizon: how long the checkpoint stays safe "
                 "(solid = median of the checkpoints that clear, dotted = 10th pct)")
    ax.legend(fontsize=8)
    figs.save(fig, "horizon.png")


def main():
    data = horizons()
    horizon_table(data)
    fig_horizon(data)


if __name__ == "__main__":
    main()
