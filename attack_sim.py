#!/usr/bin/env python3
"""Block-level attacker under real Bitcoin retarget rules.

chainwork.py prices the *band edge*: Wtr/10^band work over the elapsed interval.
This checks that price under the rules a node actually enforces — difficulty is
pinned by the retarget path from the anchor (every 2016 blocks, factor clamped to
4x), so the fork cannot choose its difficulty freely.

It extends the trusted anchor with a fork holding hash share `f` of the dominant
chain, honest timestamps (the time a block is actually found), and the real
retarget, then reports whether the rule accepts the fork at the node's clock and
what the fork cost in work.

Usage:  python3 attack_sim.py [trials]
"""
import math
import random
import sys

from finality import (BTC, X_NOW, WORK, usd, fit, band, trend_work, floor_work)

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

    for h in H_S:
        e = X_NOW - h
        model = fit(e, W, btc)
        d0 = 10 ** [p for p in btc if p[0] <= e][-1][1]
        wtr = trend_work(model, e, X_NOW)
        bq = band(W, h)
        floor = floor_work(e)
        closed = max(wtr / 10 ** bq, floor)
        print(f"h={h:g}y  anchor D0={d0:.3g}  band={bq:.2f} dex  "
              f"closed-form interval cost ${usd(closed):,.0f}")
        print("  %-6s %-12s %-9s %-9s" % ("f", "work $", "pass", "blocks"))
        for f in F_S:
            cws = 0
            workv = []
            for i in range(TRIALS):
                _, w_rel = mine(f, d0, h * 31557600.0,
                                random.Random(7 * i + int(f * 1000) + int(h * 10)))
                w = w_rel * WORK * d0
                q = math.log10(w) - math.log10(wtr) if w > 0 else -99
                cws += (q >= -bq and w >= floor)
                workv.append(w)
            print("  %-6.3g %-12s %-9s %-9.0f" %
                  (f, f"${usd(sum(workv) / TRIALS):,.0f}",
                   f"{cws / TRIALS:.0%}",
                   sum(workv) / TRIALS / (WORK * d0)))
        print()

    print("reading: the fork must hold a hash share large enough that the work it "
          "produces over the interval clears the band; below that share the rule "
          "rejects it at every trial.")


if __name__ == "__main__":
    main()
