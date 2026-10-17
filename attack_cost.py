#!/usr/bin/env python3
"""What a forged chain costs when the trusted checkpoints are stale.

The finality rule in the README passes a chain when

    (a) its tip is recent / its work rate matches the trend, and
    (b) its difficulty is not more than `band` dex below the trusted trend.

A forger only has to sit at the *bottom edge* of that band, so the cost is set by
the band's lower edge, not by the dominant chain's hash rate.  The wider the band
grows with staleness, the cheaper the forgery.

Bands go through m_band(), which applies the model's own monotone guard over the
full staleness grid ("a band cannot shrink as the model ages").  Calling
calibrate() with a single h silently skips that guard and understates the band at
large h, which inflates the attack costs; the raw single-h value is printed
alongside so the difference stays visible.

Usage:  python3 attack_cost.py [staleness_years] [usd_per_TH_per_day]
"""
import datetime
import math
import sys

from analyze import load, fit, predict, denom, calibrate, m_band, YEAR

H_STALE = float(sys.argv[1]) if len(sys.argv) > 1 else 10.0   # years
HASHPRICE = float(sys.argv[2]) if len(sys.argv) > 2 else 0.04  # USD per TH/s per day
WORK = 2 ** 32            # hashes per unit of difficulty per block
TH_DAY = 1e12 * 86400     # hashes per (TH/s * day)
WS = (2.0, 3.0, 4.0, 5.0, 8.0)


def usd(hashes):
    return hashes / TH_DAY * HASHPRICE


def ymd(ts):
    return datetime.datetime.fromtimestamp(ts, datetime.UTC).strftime("%Y-%m-%d")


def decade_work(pts, lo, hi):
    """Actual chainwork of the sampled chain between two heights."""
    total = 0.0
    for i in range(1, len(pts)):
        _, y0, h0, _ = pts[i - 1]
        _, y1, h1, _ = pts[i]
        a, z = max(h0, lo), min(h1, hi)
        if z <= a:
            continue
        total += (z - a) * WORK * 10 ** ((y0 + y1) / 2)
    return total


def trend_work(model, lo, hi):
    """Chainwork implied by the fitted trend line over [lo, hi] (years)."""
    a, b = model["a"], model["b"]
    integ = 10 ** a * (hi ** (b + 1) - lo ** (b + 1)) / (b + 1)  # difficulty * years
    return integ * YEAR * WORK / 600


def main():
    btc = load("BTC")
    x_now = btc[-1][0]
    d_tip = 10 ** btc[-1][1]
    h_net = d_tip * WORK / 600
    e = x_now - H_STALE
    anchor = [p for p in btc if p[0] <= e][-1]
    actual = decade_work(btc, anchor[2], btc[-1][2])

    print(f"trusted checkpoints end {ymd(anchor[3])} "
          f"(h={anchor[2]}, x={e:.2f} y since genesis)")
    print(f"candidate tip {ymd(btc[-1][3])} (h={btc[-1][2]}); "
          f"BTC difficulty {d_tip:.3g}, network {h_net / 1e18:.0f} EH/s")
    print(f"USD anchor: ${HASHPRICE:g} per TH/s per day "
          f"({1000 * HASHPRICE:g} $/PH/day); {TH_DAY:.3g} hashes/TH-day")
    print()

    hdr = ("W", "band(raw)", "band(guard)", "Dmin/BTC", "Hmin(%net)",
           "1 block", "1 day", "cum work", "BTC pass")
    print("%-5s %-9s %-11s %-9s %-11s %-9s %-9s %-9s %s" % hdr)
    for W in WS:
        model = fit(e, W, btc)
        if not model:
            print("W=%-3gy  fit failed" % W)
            continue
        raw = calibrate(W, [H_STALE], btc)[H_STALE]
        m = m_band(W, H_STALE, btc)
        pred = predict(model, x_now)
        den = denom(model, x_now)
        band_raw, band = raw * den, m * den
        if math.isnan(band):
            print("W=%-3gy  no calibration window reaches h=%gy" % (W, H_STALE))
            continue
        d_min = 10 ** (pred - band)
        h_min = d_min * WORK / 600
        passes = "yes" if btc[-1][1] - pred >= -band else "NO"
        print("%-5s %-9.2f %-11.2f %-9.3g %-11.4g %-9.0f %-9.0f %-9.3g %s"
              % (f"{W:g}y", band_raw, band, d_min / d_tip, h_min / h_net * 100,
                 usd(d_min * WORK), usd(h_min * 86400),
                 usd(trend_work(model, e, x_now) / 10 ** band), passes))

    print()
    print(f"reference: Bitcoin's own chainwork over the stale {H_STALE:g}y "
          f"({ymd(anchor[3])} -> {ymd(btc[-1][3])})")
    print(f"           {actual:.3e} hashes = ${usd(actual):,.0f}")


if __name__ == "__main__":
    main()
