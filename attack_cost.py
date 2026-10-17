#!/usr/bin/env python3
"""What a forged chain costs when the trusted checkpoints are stale.

The finality rule in the README passes a chain when

    (a) its tip is recent / its work rate matches the trend, and
    (b) its difficulty is not more than `band` dex below the trusted trend.

A forger only has to sit at the *bottom edge* of that band, so the cost is set by
the band's lower edge, not by the dominant chain's hash rate.  The wider the band
grows with staleness, the cheaper the forgery.  This script puts numbers on that
for a default staleness of 10 years.

It reuses fit/denom/calibrate from analyze.py (which is importable without
matplotlib).

Usage:  python3 attack_cost.py [staleness_years] [usd_per_TH_per_day]
"""
import math
import sys

from analyze import load, fit, predict, denom, calibrate, YEAR

H_STALE = float(sys.argv[1]) if len(sys.argv) > 1 else 10.0   # years
HASHPRICE = float(sys.argv[2]) if len(sys.argv) > 2 else 0.04  # USD per TH/s per day
TARGET = 600.0            # seconds per block
WORK = 2 ** 32            # hashes per unit of difficulty per block
TH_DAY = 1e12 * 86400     # hashes per (TH/s * day)
WS = (2.0, 3.0, 4.0, 5.0, 8.0)


def hashes_to_usd(hashes):
    return hashes / TH_DAY * HASHPRICE


def decade_work(pts, lo, hi):
    """Actual chainwork of the sampled chain between two times, from its heights."""
    total = 0.0
    for i in range(1, len(pts)):
        x0, y0, h0, _ = pts[i - 1]
        x1, y1, h1, _ = pts[i]
        a, z = max(h0, lo), min(h1, hi)
        if z <= a:
            continue
        total += (z - a) * WORK * 10 ** ((y0 + y1) / 2)
    return total


def fit_work(model, lo, hi):
    """Chainwork implied by the fitted trend line over [lo, hi] (years)."""
    a, b = model["a"], model["b"]
    # 10^(a + b log10 x) = 10^a * x^b  (x in years)
    integ = 10 ** a * (hi ** (b + 1) - lo ** (b + 1)) / (b + 1)  # difficulty * years
    return integ * YEAR * WORK / TARGET


def main():
    btc = load("BTC")
    x_now = btc[-1][0]
    d_tip = 10 ** btc[-1][1]
    h_net = d_tip * WORK / TARGET
    e = x_now - H_STALE
    h_lo = next(p[2] for p in btc if p[0] >= e)
    actual_decade = decade_work(btc, h_lo, btc[-1][2])

    print(f"trusted checkpoints end at year {2009 + e:.1f} "
          f"(x = {e:.2f} y since genesis)")
    print(f"candidate tip at year {2009 + x_now:.1f}; "
          f"BTC difficulty {d_tip:.3g}, network {h_net / 1e18:.0f} EH/s")
    print(f"USD anchor: ${HASHPRICE:g} per TH/s per day "
          f"({1000 * HASHPRICE:g} $/PH/day), {TH_DAY:.3g} hashes per TH-day")
    print()

    for W in WS:
        model = fit(e, W, btc)
        if not model:
            print(f"W={W:g}y: fit failed")
            continue
        m = calibrate(W, [H_STALE], btc)[H_STALE]
        pred = predict(model, x_now)
        band = m * denom(model, x_now)
        tag = f"W={W:g}y  fit n={model['n']:3d} slope b={model['b']:5.2f}  " \
              f"trend at tip = 10^{pred:.2f}"
        if math.isnan(band):
            print(tag + "  -> no calibration window reaches h="
                  f"{H_STALE:g}y; band undefined")
            continue
        d_min = 10 ** (pred - band)
        h_min = d_min * WORK / TARGET
        resid_btc = btc[-1][1] - pred
        print(tag)
        print(f"      band = {band:.2f} dex (x{10 ** band:.3g})   "
              f"D_min = {d_min:.3g} ({d_min / d_tip:.3g}x the real tip)")
        print(f"      hash rate for 10-min tips at D_min = {h_min / 1e18:.3g} EH/s "
              f"({h_min / h_net:.2%} of Bitcoin)")
        print(f"      does the *real* BTC chain pass? {resid_btc >= -band} "
              f"(its residual is {resid_btc:+.2f} dex)")
        print(f"      cost, one block at D_min          ${hashes_to_usd(d_min * WORK):,.0f}")
        print(f"      cost, 1 day of 10-min tips        ${hashes_to_usd(h_min * 86400):,.0f}"
              f"   (1 week ${hashes_to_usd(h_min * 7 * 86400):,.0f})")
        honest_work = fit_work(model, e, x_now)
        print(f"      cost, cumulative work from anchor ${hashes_to_usd(honest_work / 10 ** band):,.0f}"
              f"   (truth would be ${hashes_to_usd(actual_decade):,.0f})")
        print()

    print(f"reference: Bitcoin's own chainwork over the stale {H_STALE:g}y = "
          f"{actual_decade:.3e} hashes = ${hashes_to_usd(actual_decade):,.0f}")


if __name__ == "__main__":
    main()
