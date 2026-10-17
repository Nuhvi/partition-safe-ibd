#!/usr/bin/env python3
"""Audit the band calibration in analyze.calibrate().

Three questions, all of which the README's "95 % band" claim depends on:

  1. How many independent fit windows actually back m(W, h)?  Small n means the
     95th percentile is a guess.
  2. Does the calibration survive out of sample?  calibrate() scores the same
     overlapping windows it was built from, so its coverage is true by
     construction.  Here m is fixed on windows before a cutoff and scored after.
  3. How often does it flag the *true* chain?  A band that rejects real Bitcoin
     is worse than no band, and there is a live instance at the tip.

Sections:
  A  window counts, raw and guarded m
  B  walk-forward coverage (calibrate before the cutoff, score after)
  C  false positives: historical rate and the current tip
  D  start-grid margins with worst-case instead of best-case fork

Usage:  python3 calibration_audit.py [W ...]      (default 2 4 8)
"""
import math
import sys

from analyze import load, fit, predict, denom, calibrate, m_band, next_btc, coverage_ratio

WS = [float(a) for a in sys.argv[1:]] or [2.0, 4.0, 8.0]
BTC = load("BTC")
X_NOW = BTC[-1][0]


def section(title):
    print("\n" + title + "\n" + "-" * len(title))


def main():
    section("A. calibration support")
    print("%-6s %-6s %-6s %-9s %-9s" % ("W", "h", "n", "m(raw)", "m(guard)"))
    for W in WS:
        for h in (0, 1, 2, 3, 4, 6, 8, 10):
            n = len(coverage_ratio(W, h, BTC))
            raw = calibrate(W, [h], BTC)[h]
            guard = m_band(W, h, BTC)
            print("%-6s %-6g %-6d %-9.2f %-9.2f"
                  % (f"{W:g}y", h, n, raw, guard))

    section("B. walk-forward coverage (m fixed on tests <= cutoff)")
    print("%-6s %-4s " % ("W", "h"), end="")
    cutoffs = (2014, 2016, 2018, 2020)
    for c in cutoffs:
        print("%-12s" % f"<={c}", end="")
    print("nominal")
    for W in WS:
        for h in (0, 1, 2, 3):
            rs = coverage_ratio(W, h, BTC)
            if not rs:
                continue
            print("%-6s %-4g " % (f"{W:g}y", h), end="")
            for c in cutoffs:
                cal = sorted(r for t, r in rs if t <= c)
                ev = [r for t, r in rs if t > c]
                if len(cal) < 3 or not ev:
                    print("%-12s" % "-", end="")
                    continue
                m = cal[int(0.95 * (len(cal) - 1))]
                print("%-12s" % f"{sum(r <= m for r in ev) / len(ev):.0%} ({len(ev)})", end="")
            print("95%")

    section("C. false positives on the true chain (guarded band)")
    print("%-6s %-4s %-14s %-9s %-22s" % ("W", "h", "flagged", "band", "tip residual"))
    for W in WS:
        for h in (0, 0.5, 1, 2, 4, 6):
            rs = coverage_ratio(W, h, BTC)
            if not rs:
                continue
            m = m_band(W, h, BTC)
            if math.isnan(m):
                continue
            fp = sum(1 for _, r in rs if r > m)
            e = X_NOW - h
            mod = fit(e, W, BTC)
            band = m * denom(mod, X_NOW)
            resid = BTC[-1][1] - predict(mod, X_NOW)
            live = "FLAGGED" if resid < -band else "ok"
            print("%-6s %-4g %-14s %-9.3f %-+9.3f  %s"
                  % (f"{W:g}y", h, f"{fp}/{len(rs)}", band, resid, live))

    section("D. start-grid margins, worst-case fork (min) vs best-case (max)")
    series = {c: load(c) for c in ("BCH", "BSV", "XEC")}
    for W in (4.0,):
        for cal in (2020, 2022, 2024, 2026):
            for S in (1, 2):
                x0 = cal - 2009.0
                e = x0 - S
                mod = fit(e, W, BTC)
                if not mod or e - W < 1.0:
                    continue
                b = m_band(W, S, BTC) * denom(mod, x0)
                seps = [predict(mod, x0) - xs[-1][1]
                        for c in series
                        if (xs := [p for p in series[c] if p[0] <= x0 + 0.4])]
                if not seps:
                    continue
                flag = "  <-- true chain fails its own band" if \
                    BTC[-1][1] - predict(mod, x0) < -b and x0 > 2025 else ""
                print("  W=%gy start=%d S=%g: band=%.2f  max-margin=%+.2f  min-margin=%+.2f%s"
                      % (W, cal, S, b, max(seps) - b, min(seps) - b, flag))


if __name__ == "__main__":
    main()
