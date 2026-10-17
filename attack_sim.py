#!/usr/bin/env python3
"""Block-level attacker under real Bitcoin retarget rules.

attack_cost.py and chainwork.py price the *band edge*: one block at the edge
difficulty for the tip-difficulty rule, Wtr/10^band work for the chainwork rule.
Both assume the attacker may choose the tip difficulty.  A node that validates
the candidate as a Bitcoin chain does not allow that — difficulty is pinned by
the retarget path from the anchor (every 2016 blocks, factor clamped to 4x), and
the attacker has to live with it.

This extends the trusted anchor with a fork holding hash share `f` of the
dominant chain, honest timestamps (the time a block is actually found), and the
real retarget, then asks which of the two rules a node would accept at its own
clock, and what the fork cost in work.

Usage:  python3 attack_sim.py [trials]
"""
import math
import random
import sys

from analyze import load, fit, predict, denom, m_band
from finality import (BTC, X_NOW, WORK, usd, band, trend_work, floor_work,
                      anchor_difficulty)

TRIALS = int(sys.argv[1]) if len(sys.argv) > 1 else 200
BLOCK = 600.0
EPOCH = 2016
F_S = (0.05, 0.1, 0.2, 0.3, 0.5, 0.75, 1.0)
H_S = (0.5, 1.0, 2.0)
W = 4.0


def mine(f, d0, T, rng):
    """Mine from the anchor for T seconds at hash share f.  Returns (d_tip, work)."""
    d = 1.0                     # difficulty in units of d0
    t = 0.0
    epoch_start = 0.0
    nb = 0
    work = 0.0                  # accumulated work in units of d0*2^32 (per block)
    while t < T:
        t += rng.expovariate(1.0 / (BLOCK / f) / d)   # mean 600*d/f
        if t >= T:
            break
        nb += 1
        work += d
        if nb == EPOCH:
            actual = max(1.0, t - epoch_start)
            d *= min(4.0, max(0.25, (EPOCH * BLOCK) / actual))
            epoch_start = t
            nb = 0
    return d, work


def main():
    btc = BTC
    print("block-level attacker: real retarget (2016 blocks, 4x clamp), honest timestamps")
    print("node uses its own clock; 'pass' = the rule accepts the fork at t_now\n")
    print("closed-form costs (band edge, ignoring retarget path):")
    print("  %-5s %-14s %-14s %-14s" % ("h", "tip band", "tip 1 block", "cw interval"))
    for h in H_S:
        e = X_NOW - h
        model = fit(e, W, btc)
        bd = m_band(W, h, btc) * denom(model, X_NOW)
        d_edge = 10 ** (predict(model, X_NOW) - bd)
        print("  %-5g %-14s %-14s %-14s" % (h, f"{bd:.2f} dex",
              f"${usd(d_edge * WORK):,.0f}",
              f"${usd(trend_work(model, e, X_NOW) / 10 ** band(W, h)):,.0f}"))

    for h in H_S:
        e = X_NOW - h
        model = fit(e, W, btc)
        d0 = 10 ** [p for p in btc if p[0] <= e][-1][1]
        d_tr = 10 ** predict(model, X_NOW)
        wtr = trend_work(model, e, X_NOW)
        bd = m_band(W, h, btc) * denom(model, X_NOW)
        bq = band(W, h)
        floor = floor_work(e)
        print(f"\nh={h:g}y  trend D={d_tr:.3g}  anchor D0={d0:.3g}  "
              f"tip band={bd:.2f} dex  cw band={bq:.2f} dex")
        print("  %-6s %-9s %-12s %-11s %-11s %-11s" %
              ("f", "D_tip/D0", "work $", "tip pass", "cw pass", "blocks"))
        for f in F_S:
            tips = cws = 0
            workv, dtip = [], []
            for i in range(TRIALS):
                d_rel, w_rel = mine(f, d0, h * 31557600.0,
                                    random.Random(7 * i + int(f * 1000) + int(h * 10)))
                d_tip = d_rel * d0
                w = w_rel * WORK * d0
                r = math.log10(d_tip / d_tr)
                q = math.log10(w) - math.log10(wtr) if w > 0 else -99
                tips += (r >= -bd)
                cws += (q >= -bq and w >= floor)
                workv.append(w)
                dtip.append(d_rel)
            print("  %-6.3g %-9.3g %-12s %-11s %-11s %-11.0f" %
                  (f, sum(dtip) / TRIALS, f"${usd(sum(workv) / TRIALS):,.0f}",
                   f"{tips / TRIALS:.0%}", f"{cws / TRIALS:.0%}",
                   sum(workv) / TRIALS / (WORK * d0)))

    print("\nreading: the tip-difficulty rule is evaluated with the difficulty the "
          "retarget path actually produced, not one the attacker picked.  Where the\n"
          "closed form said 'one block', the fork must instead hold a hash share "
          "close enough to the dominant chain to make the difficulty match.")


if __name__ == "__main__":
    main()
