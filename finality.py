#!/usr/bin/env python3
"""Canonical finality rule: grade work since the trusted anchor.

This is the entry point the README's decision rule (§3) describes.  It owns the
statistic, the calibration and the decision, so a node does not have to reassemble
them:

    trusted anchor   (time t0, difficulty D0)
    candidate tip    (time t1, cumulative work C1)
    node clock       t_now
    elapsed          T  = t_now - t0                     (the node's clock)
    observed work    dC = C1 - C0
    trend work       Wtr = integral of D_tr(t)*2^32/600 over [t0, t_now]
    statistic        q  = log10(dC) - log10(Wtr)

    reject if  dC < 2^32 * D0                (hard floor: chain has not grown)
    reject if  q  < -band(W, h)              h = T in years
    accept otherwise

`band` is calibrated on q for the true chain and made non-decreasing in h by
**isotonic regression** (PAVA) rather than a running max.  For this statistic the
raw band is already almost monotone, so the two agree closely; the running max
mattered for the retired tip-difficulty band, where a noisy estimate at one h
inflated every larger h.

Usage:  python3 finality.py [W] [h_years]
"""
import math
import random
import sys

from analyze import load, fit, predict, denom, coverage_ratio, YEAR

WORK = 2 ** 32
TARGET = 600.0                 # seconds per block
TH_DAY = 1e12 * 86400          # hashes per (TH/s * day)
HASHPRICE = 0.04               # USD per TH/s per day
MIN_SUPPORT = 8                # refuse to trust a band from fewer windows
YEAR_SECONDS = YEAR

BTC = load("BTC")
X_NOW = BTC[-1][0]
H_NOW = 10 ** BTC[-1][1] * WORK / TARGET


def usd(hashes):
    return hashes / TH_DAY * HASHPRICE


# ---------------------------------------------------------------- statistic
def work_between(lo, hi, pts=None):
    """Chainwork (hashes) of a sampled chain between two times (years)."""
    pts = pts or BTC
    total = 0.0
    for i in range(1, len(pts)):
        x0, y0, h0, _ = pts[i - 1]
        x1, y1, h1, _ = pts[i]
        if x1 < lo or x0 > hi:
            continue
        a, z = max(x0, lo), min(x1, hi)
        if z <= a:
            continue
        total += (h1 - h0) * ((z - a) / (x1 - x0)) * WORK * 10 ** ((y0 + y1) / 2)
    return total


def trend_work(model, lo, hi):
    """Chainwork implied by the fitted trend line over [lo, hi] (years)."""
    a, b = model["a"], model["b"]
    return WORK / TARGET * YEAR * 10 ** a / (b + 1) * (hi ** (b + 1) - lo ** (b + 1))


def q_at(W, h, e, pts=None):
    pts = pts or BTC
    model = fit(e, W, pts)
    if not model or e + h > pts[-1][0]:
        return None
    act = work_between(e, e + h, pts)
    tr = trend_work(model, e, e + h)
    return None if act <= 0 or tr <= 0 else math.log10(act) - math.log10(tr)


def q_samples(W, h):
    out, e = [], 1.0 + W
    while e <= X_NOW - h:
        q = q_at(W, h, e)
        if q is not None:
            out.append((2009.0 + e + h, q))
        e += 0.5
    return sorted(out)


# ---------------------------------------------------------------- calibration
def isotonic(ys, ws=None):
    """Pool-adjacent-violators: closest non-decreasing sequence (weighted)."""
    ws = ws or [1.0] * len(ys)
    stack = []
    for y, w in zip(ys, ws):
        stack.append([y, w, 1])
        while len(stack) > 1 and stack[-2][0] > stack[-1][0]:
            y2, w2, c2 = stack.pop()
            y1, w1, c1 = stack.pop()
            stack.append([(y1 * w1 + y2 * w2) / (w1 + w2), w1 + w2, c1 + c2])
    out = []
    for y, _, c in stack:
        out += [y] * c
    return out


def band_raw(W, h, q=0.05):
    """One-sided band = magnitude of the lower `q` quantile of the true chain."""
    vals = sorted(v for _, v in q_samples(W, h))
    return None if not vals else max(0.0, -vals[int(q * (len(vals) - 1))])


def band(W, h, grid_max=10.0, step=0.5):
    """Isotonic non-decreasing band, fitted once over the full staleness grid.

    The fit is global (a node ships the resulting table), so the value cannot
    shrink as h grows.  Fitting only the prefix [0, h] does not have that
    property: adding a lower raw estimate at h + step can pool and lower the
    endpoint.
    """
    hs = sorted({round(i * step, 6) for i in range(int(round(grid_max / step)) + 1)} | {h})
    if band_raw(W, h) is None:          # no window reaches this staleness
        return float("nan")
    pts = []
    for hh in hs:
        b = band_raw(W, hh)
        if b is not None:
            pts.append((hh, b, len(q_samples(W, hh))))
    if not pts:
        return float("nan")
    fitted = isotonic([b for _, b, _ in pts], [max(1, n) for _, _, n in pts])
    value = fitted[0]
    for (hh, _, _), v in zip(pts, fitted):
        if hh <= h + 1e-9:
            value = v
    return value


def band_ci(W, h, trials=2000, seed=0):
    """Bootstrap 5–95 % interval for the raw one-sided band."""
    vals = [v for _, v in q_samples(W, h)]
    n = len(vals)
    if n < 2:
        return None
    rng = random.Random(seed)
    bs = []
    for _ in range(trials):
        s = sorted(vals[rng.randrange(n)] for _ in range(n))
        bs.append(max(0.0, -s[int(0.05 * (n - 1))]))
    bs.sort()
    return bs[int(0.05 * (trials - 1))], bs[int(0.95 * (trials - 1))]


def wf_coverage(W, h, cut=2020.0):
    rs = q_samples(W, h)
    cal = sorted(v for t, v in rs if t <= cut)
    ev = [v for t, v in rs if t > cut]
    if len(cal) < 3 or not ev:
        return None
    b = max(0.0, -cal[int(0.05 * (len(cal) - 1))])
    return b, sum(v >= -b for v in ev) / len(ev)


# ---------------------------------------------------------------- rule
def anchor_difficulty(e):
    row = [p for p in BTC if p[0] <= e]
    return 10 ** row[-1][1]


def floor_work(e):
    return WORK * anchor_difficulty(e)


def decide(anchor_time, cand_work, t_now, W, band_fn=None):
    """Apply the §3 rule.  Returns (ok, reason, q, band)."""
    band_fn = band_fn or band
    T = t_now - anchor_time
    if T <= 0:
        return False, "no elapsed time", float("nan"), float("nan")
    if cand_work < floor_work(anchor_time):
        return False, "below floor (chain has not grown)", float("nan"), float("nan")
    model = fit(anchor_time, W, BTC)
    if not model:
        return False, "no fit", float("nan"), float("nan")
    tr = trend_work(model, anchor_time, t_now)
    q = math.log10(cand_work) - math.log10(tr)
    b = band_fn(W, T)          # T is already in years
    if q < -b:
        return False, f"q={q:+.2f} < -band({b:.2f})", q, b
    return True, f"ok: q={q:+.2f} >= -band({b:.2f})", q, b


H_GRID = [0.5 * i for i in range(1, 21)]


def envelope(W, cap, band_fn=None):
    band_fn = band_fn or band
    best = None
    for h in H_GRID:
        if len(q_samples(W, h)) < MIN_SUPPORT:
            continue
        wf = wf_coverage(W, h)
        if not wf:
            continue
        b, cov = wf
        if cov >= 0.95 and b <= cap and q_at(W, h, X_NOW - h) >= -b:
            best = (h, len(q_samples(W, h)), b, cov)
    return best


def envelope_diff(W, cap):
    """Same envelope for the retired tip-difficulty statistic, for comparison."""
    from analyze import m_band
    best = None
    for h in H_GRID:
        rs = coverage_ratio(W, h, BTC)
        if not rs:
            continue
        cal = sorted(r for t, r in rs if t <= 2020.0)
        ev = [r for t, r in rs if t > 2020.0]
        if len(cal) < 3 or not ev:
            continue
        cov = sum(r <= cal[int(0.95 * (len(cal) - 1))] for r in ev) / len(ev)
        b = m_band(W, h, BTC)
        e = X_NOW - h
        model = fit(e, W, BTC)
        if cov >= 0.95 and b <= cap and \
                BTC[-1][1] - predict(model, X_NOW) >= -(b * denom(model, X_NOW)):
            best = (h, b, cov)
    return best


def envelope_report():
    lines = ["=== operating envelope (chainwork statistic) ===",
             "%-6s %-26s %-26s" % ("W", "band <= 1.0 dex", "band <= 2.0 dex")]
    for W in (2.0, 4.0, 8.0):
        cells = []
        for cap in (1.0, 2.0):
            r = envelope(W, cap)
            cells.append("none" if not r else
                         f"h<={r[0]:g}y (band {r[2]:.2f}, cov {r[3]:.0%}, n={r[1]})")
        lines.append("%-6s %-26s %-26s" % (f"{W:g}y", *cells))
    lines.append("=== same envelope, tip-difficulty statistic (band <= 2.0 dex) ===")
    for W in (2.0, 4.0, 8.0):
        r = envelope_diff(W, 2.0)
        lines.append("  W=%gy: %s" % (W, "none" if not r else
                                      f"h<={r[0]:g}y (band {r[1]:.2f}, cov {r[2]:.0%})"))
    return "\n".join(lines)


# ---------------------------------------------------------------- self-check
def main():
    WS = [float(sys.argv[1])] if len(sys.argv) > 1 else [2.0, 4.0, 8.0]
    print("finality rule: q = log10(work since anchor) - log10(trend integral)")
    print("band: isotonic (PAVA), no running max;  floor: one block at anchor difficulty\n")

    print("=== isotonic vs running max on the chainwork band (W=4) ===")
    for h in (0.5, 1, 2, 4, 6, 10):
        raw = band_raw(4.0, h)
        iso = band(4.0, h)
        run = 0.0
        for hh in (i * 0.5 for i in range(1, int(round(h / 0.5)) + 1)):
            b = band_raw(4.0, hh)
            if b is not None:
                run = max(run, b)
        print("  h=%-4g raw=%-6s isotonic=%-6.2f running-max=%.2f"
              % (h, "n/a" if raw is None else f"{raw:.2f}", iso, run))

    print("\n=== live decision (anchor = X_NOW - h, candidate = the real chain) ===")
    for W in WS:
        for h in (0.5, 1, 2, 4):
            e = X_NOW - h
            ok, why, _, _ = decide(e, work_between(e, X_NOW) + floor_work(e), X_NOW, W)
            print("  W=%gy h=%-4g %-9s %s" % (W, h, "ACCEPT" if ok else "REJECT", why))

    print("\n=== operating envelope (band <= 1.0 / 2.0 dex) ===")
    for W in WS:
        cells = []
        for cap in (1.0, 2.0):
            r = envelope(W, cap)
            cells.append("none" if not r else f"h<={r[0]:g}y (band {r[2]:.2f}, cov {r[3]:.0%})")
        print("  W=%gy:  <=1.0: %-28s  <=2.0: %s" % (W, cells[0], cells[1]))


if __name__ == "__main__":
    main()
