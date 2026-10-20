#!/usr/bin/env python3
"""Actual hashrate vs the power-law estimate, 2010-2026."""
import datetime

import model as M
import figs
from figs import GREEN, INK, ORANGE

NOW = M.BTC.t1


def q(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * (len(xs) - 1)))] if xs else float("nan")


def table():
    ts = [r[1] for r in M.BTC.rows if 2016 <= M.BTC.x(r[1]) + 2009 <= 2026]
    rb = [M.estimated_hashrate(t) / M.actual_hashrate(t) for t in ts]
    rm = [M.estimated_hashrate(t, M.PRICE_A_MEDIAN, M.PRICE_N_MEDIAN) /
          M.actual_hashrate(t) for t in ts]
    print("H_est/H_actual, 2016+  bottom %.2f/%.2f/%.2f  median %.2f/%.2f/%.2f"
          % (q(rb, .05), q(rb, .5), q(rb, .95),
             q(rm, .05), q(rm, .5), q(rm, .95)))


def fig():
    ts = [r[1] for r in M.BTC.rows if 2010 <= M.BTC.x(r[1]) + 2009 <= 2026]
    xs = [datetime.datetime.fromtimestamp(t, datetime.UTC) for t in ts]
    hs = [M.actual_hashrate(t) for t in ts]
    hb = [M.estimated_hashrate(t) for t in ts]
    hm = [M.estimated_hashrate(t, M.PRICE_A_MEDIAN, M.PRICE_N_MEDIAN)
          for t in ts]

    fig, ax = figs.plt.subplots(figsize=(12.0, 5.6))
    ax.plot(xs, hs, color=INK, lw=2.2, label="actual hashrate (spine)")
    ax.plot(xs, hb, color=GREEN, lw=1.7, ls="--",
            label="power-law, bottom")
    ax.plot(xs, hm, color=ORANGE, lw=1.3, ls="-.",
            label="power-law, median")
    ax.set_yscale("log")
    ax.set_ylim(1e-13, 1e4)
    ax.set_yticks([1e-12, 1e-9, 1e-6, 1e-3, 1, 1e3])
    ax.set_yticklabels(["0.000000000001", "0.000000001", "0.000001",
                        "0.001", "1", "1,000"])
    ax.set_xlabel("date")
    ax.set_ylabel("hashrate (EH/s, log)")
    ax.set_title("actual hashrate vs the power-law estimate, 2010-2026")
    ax.legend(fontsize=8, loc="lower right")
    ax.grid(alpha=0.25)
    figs.save(fig, "estimated_hashrate.png")


def main():
    table()
    fig()


if __name__ == "__main__":
    main()
