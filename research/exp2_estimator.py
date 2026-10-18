#!/usr/bin/env python3
"""Exp 2 - estimator error, for the section-4 table.

The rule needs Dhat(t0,T) ~ D_true(t0+T).  If the estimate is wrong by a factor
of about 1/s the safe band s < Phi <= 1 closes, so the estimator's error - above
all its low tail - is the whole game.

For every 2014+ checkpoint and staleness T we form rho = Dhat/D_true and print
its median and 5-95% spread as T grows.  No figure: the numbers feed the table
in ../README.md section 4.
"""
import math

import model as M

THETA = M.THETA
TS = [d * 86400 for d in
      (0.5, 1, 2, 3, 5, 7, 10, 15, 21, 30, 45, 60, 90, 120, 180, 270, 365, 540, 730, 1095)]
TS = [T for T in TS if T <= 3 * M.YEAR]


def quant(sorted_xs, q):
    if not sorted_xs:
        return float("nan")
    return sorted_xs[min(len(sorted_xs) - 1, int(q * (len(sorted_xs) - 1)))]


def anchors():
    return [r[1] for r in M.BTC.rows if M.BTC.x(r[1]) >= M.FIRST]


def collect(est):
    """{T: sorted list of log10(Dhat/Dtrue)}."""
    out = {T: [] for T in TS}
    for t0 in anchors():
        for T in TS:
            if t0 + T > M.BTC.t1:
                continue
            dhat = M.ESTIMATORS[est](t0, T)
            dt = M.BTC.D(t0 + T)
            if dhat > 0 and dt > 0:
                out[T].append(math.log10(dhat / dt))
    for T in out:
        out[T].sort()
    return out


def main():
    data = {est: collect(est) for est in M.ESTIMATORS}
    show = [86400, 7 * 86400, 30 * 86400, 90 * 86400, 365 * 86400, 2 * 365 * 86400]
    show = [T for T in show if T in data["flat"]]
    print("median log10(Dhat/Dtrue) [dex];  + = overshoot")
    print("%-12s %s" % ("estimator", "".join("%-9s" % f"{T/86400:g}d" for T in show)))
    for est, d in data.items():
        if est == "flatbar":
            continue
        cells = [f"{quant(d[T], 0.5):+.2f}" for T in show]
        print("%-12s %s" % (est, "".join("%-9s" % c for c in cells)))
    print("\n5-95% spread (dex), and the 5th percentile (low tail)")
    print("%-12s %-10s %s" % ("estimator", "p5/p95", "".join("%-9s" % f"{T/86400:g}d" for T in show)))
    for est, d in data.items():
        if est == "flatbar":
            continue
        cells = [f"{quant(d[T],0.05):+.2f}" for T in show]
        print("%-12s %-10s %s" % (est, "p5", "".join("%-9s" % c for c in cells)))


if __name__ == "__main__":
    main()
