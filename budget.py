#!/usr/bin/env python3
"""Attack budget: can the collective non-BTC hash fool the rule?

A fork starting at the trusted anchor can accumulate at most its own hash over
the elapsed interval:

    work_att = integral of s(t) * H_real(t) dt

where `s(t)` is the collective non-BTC SHA256d share (forks.py) and `H_real` is
Bitcoin's real hash rate.  The rule accepts when

    work_att >= W_fit / 10^band        W_fit = the trend's expected work

so the danger margin is

    M = log10(work_att / W_fit) + band

`M >= 0` means a fork matching the non-BTC collective *at that time* would pass.
The margin is evaluated for every historical stale window, so "is this
attackable?" is answered with measured hash and measured trend breaks rather
than a chosen share.  `g = log10(W_real / W_fit)` is how far the real chain broke
above the stale fit; an upward break (g > 0) lowers the bar, a downward break
raises it.

Usage:  python3 budget.py
"""
import math
import random

import forks
from finality import (load, fit, trend_work, band, floor_work, work_between,
                      BTC, X_NOW, WORK, H_NOW, usd)

W = 4.0
HS = (0.5, 1, 2, 3, 4, 6, 8, 10)

# per-BTC-interval work and the non-BTC share over that interval
_INTERVALS = []
for i in range(1, len(BTC)):
    x0, _, _, _ = BTC[i - 1]
    x1, _, _, _ = BTC[i]
    _, y0, h0, _ = BTC[i - 1]
    _, y1, h1, _ = BTC[i]
    _INTERVALS.append((x0, x1, (h1 - h0) * WORK * 10 ** ((y0 + y1) / 2),
                       forks.share_at((x0 + x1) / 2)))


def window(e, h):
    """(real work, attacker work with the non-BTC share) over [e, e+h]."""
    wr = watt = 0.0
    for x0, x1, dw, s in _INTERVALS:
        a, z = max(x0, e), min(x1, e + h)
        if z <= a:
            continue
        f = (z - a) / (x1 - x0)
        wr += dw * f
        watt += s * dw * f
    return wr, watt


def analyze():
    rows = []
    for h in HS:
        b = band(W, h)
        ms = []
        e = 1.0 + W
        while e <= X_NOW - h:
            model = fit(e, W, BTC)
            if model:
                wr, watt = window(e, h)
                wf = trend_work(model, e, e + h)
                if wr > 0 and watt > 0 and wf > 0:
                    ms.append((2009.0 + e + h, math.log10(watt / wf) + b,
                               math.log10(watt / wr), math.log10(wr / wf)))
            e += 0.5
        rows.append((h, b, ms))
    return rows


def continuation():
    """Point-3 rule: accept iff work since the checkpoint >= f * work in the
    equal period before it, with f = 10^-k the forgiveness the true chain needs.

    The attacker's work is `share * W_real_post`, so it passes when
    log10(share) + R >= -k, i.e. M_c = log10(share) + R + k >= 0, where
    R = log10(W_real_post / W_pre).  No fit and no extrapolation: the bar is the
    trusted chain's own recent work.
    """
    rows = []
    for L in HS:
        rs, e = [], 1.0
        while e + L <= X_NOW:
            wpre = work_between(e - L, e)
            wpost = work_between(e, e + L)
            if wpre > 0 and wpost > 0:
                r = math.log10(wpost / wpre)
                sh = window(e, L)[1] / window(e, L)[0] if window(e, L)[0] > 0 else 0.0
                rs.append((2009.0 + e + L, r, sh))
            e += 0.5
        if not rs:
            continue
        v = sorted(r for _, r, _ in rs)
        k = -v[int(0.05 * (len(v) - 1))]        # forgiveness: true chain keeps 95 %
        ms = [(t, math.log10(sh) + r + k) for t, r, sh in rs if sh > 0]
        rows.append((L, k, ms))
    return rows


def continuation_report():
    rows = continuation()
    lines = ["=== continuation rule: accept iff W_post >= 10^-k * W_pre ===",
             "%-6s %-9s %-5s %-10s %-10s" % ("L", "k (forgive)", "n", "max M_c", "median M_c")]
    for L, k, ms in rows:
        ms_sorted = sorted(m for _, m in ms)
        lines.append("%-6g %-9.2f %-5d %+-10.2f %+-10.2f"
                     % (L, k, len(ms), ms_sorted[-1], ms_sorted[len(ms_sorted) // 2]))
    lines.append("k is calibrated in-sample (true chain keeps 95 %); M_c >= 0 means "
                 "a fork with the era's non-BTC share would pass.")
    return "\n".join(lines)


def main():
    rows = analyze()
    print("M = log10(attacker work / trend work) + band;  M >= 0 means a fork")
    print("matching the collective non-BTC hash of that era would pass.\n")
    print("%-6s %-7s %-5s %-10s %-10s %-12s %-12s" %
          ("h", "band", "n", "max M", "median M", "worst share", "needed share"))
    for h, b, ms in rows:
        if not ms:
            continue
        ms_sorted = sorted(ms, key=lambda z: z[1])
        worst = ms_sorted[-1]
        med = ms_sorted[len(ms_sorted) // 2][1]
        print("%-6g %-7.2f %-5d %+-10.2f %+-10.2f %-12s %-12s"
              % (h, b, len(ms), worst[1], med,
                 f"{100 * 10 ** worst[2]:.2f}%", f"{100 * 10 ** -(worst[3] + b):.4f}%"))

    print("\nreading: 'max M' uses the most attacker-favourable historical window "
          "(high non-BTC share and/or an upward BTC break); 'median M' the typical\n"
          "one.  'needed share' is the constant share that would pass at this h if "
          "BTC broke upward as far as it historically did.")
    print("\n" + continuation_report())

    try:
        plot(rows)
    except ImportError:
        pass


def plot(rows, path="diagrams/attack_budget.png"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    hs = [h for h, _, _ in rows]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    mins = [min(m[1] for m in ms) for _, _, ms in rows]
    meds = [sorted(m[1] for m in ms)[len(ms) // 2] for _, _, ms in rows]
    maxs = [max(m[1] for m in ms) for _, _, ms in rows]
    ax1.errorbar(hs, meds, yerr=[ [m - lo for m, lo in zip(meds, mins)],
                                  [hi - m for m, hi in zip(meds, maxs)]],
                 fmt="o", capsize=4, color="#2c3e50")
    ax1.axhline(0, color="#c0392b", ls="--", lw=1, label="attackable")
    ax1.set_xlabel("checkpoint staleness h (years)")
    ax1.set_ylabel("danger margin M (dex)")
    ax1.set_title("M > 0: a fork with that era's non-BTC hash would pass")
    ax1.grid(alpha=0.25); ax1.legend()

    needed = [10 ** -(max(m[3] for m in ms) + b) for _, b, ms in rows]
    avail = [max(10 ** m[2] for m in ms) for _, _, ms in rows]
    ax2.semilogy(hs, [100 * a for a in avail], "o-", color="#c0392b",
                 label="available (worst window)")
    ax2.semilogy(hs, [100 * n for n in needed], "s--", color="#2c3e50",
                 label="needed to pass")
    ax2.set_xlabel("checkpoint staleness h (years)"); ax2.set_ylabel("share (%, log)")
    ax2.set_title("attacker share: available vs needed")
    ax2.grid(which="both", alpha=0.25); ax2.legend()
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)
    print(f"\nwrote {path}")


if __name__ == "__main__":
    main()
