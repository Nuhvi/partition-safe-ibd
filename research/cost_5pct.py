#!/usr/bin/env python3
"""What a 5% attacker costs per year: work cost + foregone profit."""
import bisect
import json

import model as M
import figs
from figs import GREEN, INK, ORANGE

Y = M.YEAR
NOW = M.BTC.t1
SHARE = 0.05
PRICES = [(p["x"], p["y"]) for p in
          json.load(open("data/btc_price_raw.json"))["values"] if p["y"] > 0]
PT = [p[0] for p in PRICES]


def anchor(year):
    i = min(range(len(M.BTC.rows)),
            key=lambda i: abs(M.BTC.x(M.BTC.t[i]) - (year - 2009)))
    return M.BTC.t[i]


def height_at(t):
    tt, hh = M.BTC.t, M.BTC.h
    i = max(0, min(bisect.bisect_right(tt, t) - 1, len(tt) - 2))
    f = (t - tt[i]) / (tt[i + 1] - tt[i]) if tt[i + 1] > tt[i] else 0.0
    return hh[i] + f * (hh[i + 1] - hh[i])


def reward(t):
    return 50.0 / (2 ** int(height_at(t) // 210000))


def price_at(t):
    i = max(0, min(bisect.bisect_right(PT, t) - 1, len(PRICES) - 1))
    return PRICES[i][1]


def hp(t):
    return reward(t) * price_at(t) / M.BTC.w(t)


def annual_work_cost(t0):
    """5% of the network's annual hash cost at the cheapest hash price."""
    ts = [t0 + i * 86400 for i in range(0, int((NOW - t0) / 86400) + 1)] + [NOW]
    mn = min(hp(t) for t in ts)
    return SHARE * (M.BTC.w(t0) / 600.0) * Y * mn / 1e9


def annual_rewards(t0):
    """5% of the block rewards at the checkpoint, USD/year."""
    return SHARE * reward(t0) * price_at(t0) * 144 * 365 / 1e9


def table():
    print("5% attacker, USD/year (billions)")
    print("%-6s %10s %12s %10s" % ("year", "work", "rewards", "net"))
    tw = tr = 0.0
    rows = []
    for yr in range(2016, 2026):
        t0 = anchor(yr)
        w, r = annual_work_cost(t0), annual_rewards(t0)
        tw += w
        tr += r
        rows.append((yr, w, r, r - w))
        print("%-6d %9.3fB %11.3fB %9.3fB" % (yr, w, r, r - w))
    print("%-6s %9.3fB %11.3fB %9.3fB"
          % ("total", tw, tr, tr - tw))
    return rows


def fig():
    rows = table()
    years = [r[0] for r in rows]
    w = [r[1] for r in rows]
    net = [r[3] for r in rows]

    fig, ax = figs.plt.subplots(figsize=(12.0, 5.4))
    ax.bar(years, w, color=GREEN, label="work cost (energy/hash)")
    ax.bar(years, net, bottom=w, color=ORANGE,
           label="foregone profit (rewards - work)")
    ax.set_ylim(0, 0.9)
    ax.set_xlabel("checkpoint year")
    ax.set_ylabel("USD billions/year")
    ax.set_title("5% attacker: work + foregone profit; the bar needs >5% of network work")
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(alpha=0.25, axis="y")
    figs.save(fig, "cost_5pct.png")


def main():
    fig()


if __name__ == "__main__":
    main()
