#!/usr/bin/env python3
"""Block-level Poisson backtest of the freshness / work gate.

The claim that an asymmetric fork is caught "in hours" had no backtest.  This
simulates it directly:

  * a fork leaves a trusted anchor with the anchor's difficulty inherited,
  * hash rate is a share `f` of the dominant chain's, so blocks arrive Poisson
    with mean 600/f seconds,
  * the fork follows Bitcoin's real retarget (every 2016 blocks, clamped to 4x),
  * timestamps are honest (a miner sets the time it actually found the block;
    it cannot certify work it did not do),
  * the node's clock is t0 + T, and elapsed time T is the node's, not the
    candidate's.

Gates evaluated at T (never before tau):
  stale tip   reject if T - (time of last block) > tau
  interval    reject if work(t0, T) < trend_work(t0, T) / 10^band   (README §2)
  window      reject if work(T-L, T) / L < trend rate / 10^band

The interval gate has no built-in latency: the trend work grows with the node's
clock, so a fork below the rate edge fails at the first evaluation.  The window
variant pays one window.  The only forks that escape are those at or above the
edge 10^-band, i.e. near-even splits.

Usage:  python3 simulate.py [trials] [horizon_days]
"""
import math
import random
import sys

TRIALS = int(sys.argv[1]) if len(sys.argv) > 1 else 400
HORIZON = (float(sys.argv[2]) if len(sys.argv) > 2 else 7.0) * 86400.0
WORK = 2 ** 32
BLOCK = 600.0                     # target seconds
TAU = 6 * BLOCK                   # stale-tip threshold
WINDOW = 6 * 3600.0               # trailing work-rate window
CHECK = 60.0                      # node re-evaluates every minute
F_S = (0.50, 0.25, 0.10, 0.05, 0.01, 0.0015)   # 0.0015 ~ the BIP-110 share
BANDS = (0.65, 0.94)


def mine(f, horizon, rng):
    """Block times (s) and difficulty for an honest fork with hash share f."""
    d = 1.0                     # work in units of (D0 * 2^32)
    times, prefix, diffs = [], [0.0], []
    t = epoch0 = 0.0
    nb = 0
    while True:
        t += rng.expovariate(1.0 / (BLOCK / f))
        if t > horizon:
            break
        times.append(t); diffs.append(d)
        prefix.append(prefix[-1] + d)          # cumulative work in D0-block units
        nb += 1
        if nb == 2016:                          # real retarget, 4x clamp
            d *= min(4.0, max(0.25, (2016 * BLOCK) / (t - epoch0)))
            epoch0, nb = t, 0
    return times, prefix


def work_until(times, prefix, t):
    lo, hi = 0, len(times)
    while lo < hi:
        mid = (lo + hi) // 2
        if times[mid] <= t:
            lo = mid + 1
        else:
            hi = mid
    return prefix[lo]                          # in D0-block units; 1 unit = 10^band edge basis


def detect(f, band, horizon, rng):
    """Earliest T at which any gate rejects, or None."""
    times, prefix = mine(f, horizon, rng)
    trend_rate = 1.0 / BLOCK                   # units: D0-block per second
    t = TAU
    while t <= horizon:
        w = work_until(times, prefix, t)
        if times and t - times[-1] > TAU:                       # stale tip
            return t, "tip"
        if w < trend_rate * t / 10 ** band:                     # interval
            return t, "interval"
        if t >= WINDOW:                                         # trailing window
            w0 = work_until(times, prefix, t - WINDOW)
            if (w - w0) / WINDOW < trend_rate / 10 ** band:
                return t, "window"
        t += CHECK
    return None, "-"


def run(band):
    """f -> list of detection times (s) over TRIALS traces."""
    out = {}
    for f in F_S:
        hits, kinds = [], {}
        for i in range(TRIALS):
            t, k = detect(f, band, HORIZON, random.Random(1000 * i + int(f * 1e6)))
            if t is not None:
                hits.append(t)
                kinds[k] = kinds.get(k, 0) + 1
        out[f] = (sorted(hits), kinds)
    return out


def main():
    print("block-level Poisson backtest: honest timestamps, real 2016-block retarget")
    print(f"tau={TAU:.0f}s window={WINDOW/3600:.0f}h horizon={HORIZON/86400:.0f}d "
          f"trials={TRIALS} -> rate edge f* = 10^-band")
    results = {}
    for band in BANDS:
        res = results[band] = run(band)
        print(f"\nband = {band:.2f} dex   (edge f* = {10 ** -band:.3f})")
        print("  %-8s %-10s %-12s %-12s %-14s" %
              ("f", "mean gap", "detected", "median", "gates"))
        for f in F_S:
            hits, kinds = res[f]
            med = "-" if not hits else (f"{hits[len(hits)//2]/60:.0f} min")
            frac = f"{len(hits)/TRIALS:.0%}"
            top = ",".join(f"{k}:{v}" for k, v in sorted(kinds.items(), key=lambda z: -z[1]))
            print("  %-8.4g %-10s %-12s %-12s %-14s"
                  % (f, f"{BLOCK / f / 60:.0f} min", frac, med, top))
    print("\nreading: below the rate edge 10^-band the interval gate fires at the "
          "first check (tau), so latency is tau, not days.  At or above the\n"
          "edge detection is stochastic and slow -- variance in block counts "
          "either throws a long gap (tip) or a light window -- and a near-even\n"
          "split can escape for days: the residual 50/50 case.")
    try:
        plot(results)
    except ImportError:
        pass


def plot(results, path="diagrams/detection_latency.png"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    for (band, res), col in zip(results.items(), colors):
        fs = [f for f in F_S if f in res]
        frac = [len(res[f][0]) / TRIALS for f in fs]
        med = [(res[f][0][len(res[f][0]) // 2] / 60 if res[f][0] else float("nan"))
               for f in fs]
        ax1.semilogx(fs, frac, marker="o", ms=4, color=col, label=f"band={band:.2f} dex")
        ax1.axvline(10 ** -band, ls=":", lw=1, color=col)
        ax1.text(10 ** -band, 1.02, f"edge {10 ** -band:.2f}", color=col,
                 fontsize=8, ha="center")
        ax2.loglog(fs, med, marker="o", ms=4, color=col, label=f"band={band:.2f} dex")
    ax1.set_xlabel("fork hash share f (fraction of dominant hash rate)")
    ax1.set_ylabel("detected within horizon"); ax1.set_ylim(-0.02, 1.08)
    ax1.set_title("how often the gate fires")
    ax1.grid(which="both", alpha=0.25); ax1.legend(loc="center left")
    ax2.set_xlabel("fork hash share f (fraction of dominant hash rate)")
    ax2.set_ylabel("median detection time (min, detected traces only)")
    ax2.axhline(HORIZON / 60, ls="--", lw=1, color="#888")
    ax2.text(F_S[0], HORIZON / 60 * 1.05, "horizon", color="#888", fontsize=8)
    ax2.set_title("how long it takes (successful traces)")
    ax2.grid(which="both", alpha=0.25); ax2.legend(loc="upper left")
    fig.suptitle("Poisson gate backtest: below the edge detection is immediate, "
                 "near-even splits escape")
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)
    print(f"\nwrote {path}")


if __name__ == "__main__":
    main()
