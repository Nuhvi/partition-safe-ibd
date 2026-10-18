#!/usr/bin/env python3
"""Finality rules for a partitioned node, and their calibration.

The rule to use is the **flat bar** (`decide_flat`, resistance.md):

    accept iff  dC >= D0 * (2^32/600) * T          T = now - t0, the node's clock
    and, optionally, the tip is fresh

where `dC` is the candidate's work since the trusted anchor and `D0` the anchor
difficulty.  A fork holding a share `s` of believable hash passes iff
`s >= 1/G(T)` with `G(T) = mean difficulty over [t0, now] / D0`.

The rest of this module is the *fitted-trend* variant (`decide`, `band`,
`isotonic`, `q_samples`): it grades `dC` against a trend integral with a band
`10^-b`, which is weaker — the attacker passes through the band the rule needs
for downward breaks (`s >= 10^(-g-b)`).  It is kept for the comparison in
resistance.md §10.

Usage:  python3 finality.py [W] [h_years]
"""
import json
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
GEN, YEAR = 1231006505, 31557600.0

WORK = 2 ** 32
TARGET = 600.0                 # seconds per block
TH_DAY = 1e12 * 86400          # hashes per (TH/s * day)
HASHPRICE = 0.04               # USD per TH/s per day
MIN_SUPPORT = 8                # refuse to trust a band from fewer windows


def load(chain):
    rows = json.load(open(os.path.join(DATA, f"{chain}.json")))
    return [((t - GEN) / YEAR, math.log10(d), h, t) for h, t, d in rows if d > 0]


def fit(e, W, pts):
    """OLS of log10(difficulty) on log10(years) over the trailing W years to e."""
    tr = [(math.log10(x), y) for x, y, _, _ in pts if x > 0 and e - W <= x <= e]
    n = len(tr)
    if n < 6:
        return None
    mx = sum(x for x, _ in tr) / n
    my = sum(y for _, y in tr) / n
    Sxx = sum((x - mx) ** 2 for x, _ in tr)
    if Sxx <= 0:
        return None
    b = sum((x - mx) * (y - my) for x, y in tr) / Sxx
    a = my - b * mx
    s = math.sqrt(max(sum((y - (a + b * x)) ** 2 for x, y in tr) / (n - 2), 1e-12))
    return {"a": a, "b": b, "s": s, "Sxx": Sxx, "mx": mx, "n": n}


def predict(model, x):
    return model["a"] + model["b"] * math.log10(x)


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


def bar_work(anchor_time, t_now):
    """The flat bar: the constant-difficulty work over the elapsed interval."""
    return anchor_difficulty(anchor_time) * WORK / TARGET * (t_now - anchor_time) * YEAR


def decide_flat(anchor_time, cand_work, t_now, tip_time=None, tau=None):
    """The flat bar (resistance.md §1).  Returns (ok, ratio, reason).

    Accept iff the candidate's work since the checkpoint is at least the
    anchor-difficulty work over the interval; optionally also require a fresh tip
    (the tip age must come from the node's clock, not the header).
    """
    T = t_now - anchor_time
    if T <= 0:
        return False, float("nan"), "no elapsed time"
    if tip_time is not None and tau is not None and t_now - tip_time > tau:
        return False, float("nan"), "stale tip"
    r = cand_work / bar_work(anchor_time, t_now)
    return r >= 1.0, r, (f"work = {r:.2f}x bar" if r >= 1.0 else f"work = {r:.2f}x bar (< 1)")


def decide(anchor_time, cand_work, t_now, W, band_fn=None):
    """Apply the finality rule.  Returns (ok, reason, q, band)."""
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


def envelope_report():
    lines = ["=== operating envelope (band <= 1.0 / 2.0 dex) ===",
             "%-6s %-26s %-26s" % ("W", "band <= 1.0 dex", "band <= 2.0 dex")]
    for W in (2.0, 4.0, 8.0):
        cells = []
        for cap in (1.0, 2.0):
            r = envelope(W, cap)
            cells.append("none" if not r else
                         f"h<={r[0]:g}y (band {r[2]:.2f}, cov {r[3]:.0%}, n={r[1]})")
        lines.append("%-6s %-26s %-26s" % (f"{W:g}y", *cells))
    return "\n".join(lines)


# ---------------------------------------------------------------- self-check
def main():
    WS = [float(sys.argv[1])] if len(sys.argv) > 1 else [2.0, 4.0, 8.0]
    print("the flat bar: accept iff work since the checkpoint >= anchor-difficulty work\n")

    print("=== live tip (candidate = the real chain) ===")
    for h in (0.5, 1, 2, 3, 4, 6, 10):
        e = X_NOW - h
        ok, r, why = decide_flat(e, work_between(e, X_NOW), X_NOW)
        print("  h=%-4g %-7s %s" % (h, "ACCEPT" if ok else "REJECT", why))

    print("\n=== a fork holding a share s of the real work (all else equal) ===")
    h = 4.0
    e = X_NOW - h
    real = work_between(e, X_NOW)
    for s in (0.005, 0.02, 0.05, 0.33, 0.49):
        ok, r, _ = decide_flat(e, s * real, X_NOW)
        print("  s=%-5.1f%%  %-7s work/bar=%.3f" % (100 * s, "ACCEPT" if ok else "REJECT", r))

    print("\n=== the fitted-trend variant (weaker; see resistance.md) ===")
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
