#!/usr/bin/env python3
"""5% attacker: energy cost vs block rewards foregone.

Assumptions: 25 J/TH and $0.05/kWh, capex excluded.  The 5% share of the
network's annual energy is the work cost; the 5% share of annual block rewards
is the opportunity cost.  The difference is the profit foregone.  The bar
requires more than 5% of network work, so this 5% spend cannot create it.
"""
import bisect
import json

import model as M
import figs
from figs import GREEN, ORANGE

Y = M.YEAR
NOW = M.BTC.t1
SHARE = 0.05
J_PER_TH = 25.0
USD_PER_KWH = 0.05
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


def annual_stats(t0):
    t1 = min(t0 + Y, NOW)
    n = 80
    ts = [t0 + k * (t1 - t0) / n for k in range(n + 1)]
    h = sum(M.actual_hashrate(t) for t in ts) / len(ts)
    # 1 EH/s = 1e6 TH/s; 25 J/TH = 25 MW per EH/s; 8760 h; $0.05/kWh
    energy = SHARE * h * 1e6 * J_PER_TH * 8760.0 / 1000.0 * USD_PER_KWH / 1e9
    rev = SHARE * sum(reward(t) * price_at(t) * 144 * 365
                      for t in ts) / len(ts) / 1e9
    return energy, rev


def table():
    print("5% attacker, USD/year (billions); 25 J/TH, $0.05/kWh, capex excluded")
    print("%-6s %10s %12s %10s" % ("year", "energy", "rewards", "profit"))
    te = tr = 0.0
    rows = []
    for yr in range(2016, 2026):
        e, r = annual_stats(anchor(yr))
        te += e
        tr += r
        rows.append((yr, e, r, r - e))
        print("%-6d %9.3fB %11.3fB %9.3fB" % (yr, e, r, r - e))
    print("%-6s %9.3fB %11.3fB %9.3fB" % ("total", te, tr, tr - te))
    return rows


def fig():
    rows = table()
    years = [r[0] for r in rows]
    e = [r[1] for r in rows]
    net = [r[3] for r in rows]

    fig, ax = figs.plt.subplots(figsize=(12.0, 5.4))
    ax.bar(years, e, color=GREEN, label="energy cost (25 J/TH, $0.05/kWh)")
    ax.bar(years, net, bottom=e, color=ORANGE,
           label="foregone profit (rewards - energy)")
    ax.set_ylim(0, 0.9)
    ax.set_xlabel("checkpoint year")
    ax.set_ylabel("USD billions/year")
    ax.set_title("5% attacker: energy cost + foregone profit = rewards foregone; "
                 "the bar needs >5% of network work")
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(alpha=0.25, axis="y")
    figs.save(fig, "cost_5pct.png")


def main():
    fig()


if __name__ == "__main__":
    main()
