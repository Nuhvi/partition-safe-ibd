#!/usr/bin/env python3
"""Trend-based justification of a chain, and the fit tightness it requires.

Reads data/<chain>.json (see fetch.py) and produces the diagrams in diagrams/:

  1 difficulty_loglog.png   all header-compatible chains, log-log difficulty vs time
  2 residual_rolling.png    each chain's residual against a rolling BTC trend
  3 tightness_vs_staleness.png  the band you need, as the trusted checkpoint ages
  4 start_grid.png          band + detectability for a node booting at (start, staleness)

The model: fit log10(difficulty) = a + b*log10(years-since-genesis) over a window
of the trusted chain (BTC), then judge any chain by how far its difficulty falls
below the fitted line.  The 95% band is the OLS prediction interval

    band(x) = m * s * sqrt(1 + 1/n + (log10 x - xbar)^2 / Sxx)

scaled by an empirical factor m, because Bitcoin difficulty is autocorrelated and
regime-shifting, so the raw OLS interval under-covers (see calibrate()).
"""
import json
import math
import os

try:  # plotting is optional: attack_cost.py imports the math without matplotlib
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ImportError:
    matplotlib = plt = None

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DIAG = os.path.join(HERE, "diagrams")
GEN, YEAR = 1231006505, 31557600.0
CHAINS = ["BTC", "BCH", "BSV", "XEC"]
COLOR = {"BTC": "#f7931a", "BCH": "#8dc351", "BSV": "#0ac18e", "XEC": "#6f7cff"}
FORK = {"BCH": 478558, "BSV": 478558, "XEC": 661648}
GENESIS = 1231006505


def load(chain):
    rows = json.load(open(os.path.join(DATA, f"{chain}.json")))
    return [((t - GEN) / YEAR, math.log10(d), h, t) for h, t, d in rows if d > 0]


def fit(e, W, pts):
    """OLS of log10(difficulty) on log10(years) over the trailing W years to `e`."""
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


def predict(m, x):
    return m["a"] + m["b"] * math.log10(x)


def denom(m, x):
    return m["s"] * math.sqrt(1 + 1 / m["n"] + (math.log10(x) - m["mx"]) ** 2 / m["Sxx"])


def next_btc(btc, x):
    for xx, y, _, _ in btc:
        if xx >= x:
            return y
    return None


def calibrate(W, hs, btc):
    """Empirical 95% inflation factor m per staleness h for a trailing-W fit."""
    out = {}
    for h in hs:
        rs = []
        e = 1.0 + W
        while e <= btc[-1][0] - h:
            m = fit(e, W, btc)
            if m:
                y = next_btc(btc, e + h)
                d = denom(m, e + h)
                if y is not None and d > 0:
                    rs.append(abs(y - predict(m, e + h)) / d)
            e += 0.5
        rs.sort()
        out[h] = rs[int(0.95 * (len(rs) - 1))] if rs else float("nan")
    # a band cannot shrink as the model ages: enforce monotonicity in h
    ks = sorted(out)
    for i in range(1, len(ks)):
        if not math.isnan(out[ks[i]]) and not math.isnan(out[ks[i - 1]]):
            out[ks[i]] = max(out[ks[i]], out[ks[i - 1]])
    return out


def m_band(W, h, btc, grid_max=10.0, step=0.5):
    """Calibrated m(W, h), evaluated on the full staleness grid.

    calibrate() enforces "a band cannot shrink as the model ages" by taking a
    running max over the staleness values it is handed.  Calling it with a
    single h skips that guard and understates the band at large h, so every
    caller should go through here (or the same grid) to stay consistent.
    """
    hs = sorted({round(i * step, 6) for i in range(int(round(grid_max / step)) + 1)} | {h})
    return calibrate(W, hs, btc)[h]


def coverage_ratio(W, h, btc):
    """(test time, |residual| / raw single-h band) for every fit window.

    Small ratios mean the true chain stayed inside the band; a ratio > 1 means
    the model would have flagged the dominant chain itself.
    """
    out = []
    e = 1.0 + W
    while e <= btc[-1][0] - h:
        m = fit(e, W, btc)
        if m:
            y = next_btc(btc, e + h)
            d = denom(m, e + h)
            if y is not None and d > 0:
                out.append((2009.0 + e + h, abs(y - predict(m, e + h)) / d))
        e += 0.5
    return sorted(out)


# ---------------------------------------------------------------- diagrams
def fig_loglog():
    fig, ax = plt.subplots(figsize=(11, 6.5))
    for c in CHAINS:
        pts = load(c)
        ax.plot([x for x, *_ in pts], [10 ** y for _, y, *_ in pts], lw=2,
                color=COLOR[c], label=c, marker=None if c == "BTC" else "o", ms=3)
    for xf, label, ty in ((8.58, "BCH\n2017-08", 1e13), (9.87, "BSV\n2018-11", 3e10),
                          (11.87, "XEC\n2020-11", 1e8)):
        ax.axvline(xf, color="#c00", ls=":", lw=1)
        ax.text(xf + 0.05, ty, label, color="#c00", fontsize=8)
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("years since genesis (log)"); ax.set_ylabel("difficulty (log)")
    ax.set_title("Header-compatible SHA256d chains: difficulty, log-log")
    ax.grid(True, which="both", alpha=0.25); ax.legend(loc="upper left")
    fig.tight_layout(); fig.savefig(f"{DIAG}/difficulty_loglog.png", dpi=130)
    plt.close(fig)


def fig_residuals(W=4.0):
    btc = load("BTC")
    fig, ax = plt.subplots(figsize=(11, 6))
    xs, band = [], []
    for x, y, _, _ in btc:
        if x < 2:
            continue
        m = fit(x, W, btc)
        if not m:
            continue
        xs.append(x); band.append(2.4 * denom(m, x))  # m=2.4 ~ nominal 95% at h~0
    ax.fill_between(xs, [-b for b in band], band, color="#888", alpha=0.18,
                    label="95% band of the rolling 4y BTC fit (~±0.5–1 dex)")
    ax.axhline(0, color="#555", lw=1)
    for c in ["BTC", "BCH", "BSV", "XEC"]:
        pts = load(c)
        rx, ry = [], []
        for x, y, _, _ in pts:
            m = fit(x, W, btc)
            if m and x >= 2:
                rx.append(x); ry.append(y - predict(m, x))
        ax.plot(rx, ry, lw=2, color=COLOR[c], marker=None if c == "BTC" else "o",
                ms=3, label=f"{c} residual")
    ax.set_xscale("log")
    ax.set_xlabel("years since genesis (log)"); ax.set_ylabel("log10(diff) − trend (dex)")
    ax.set_title("Residual against a rolling 4-year BTC trend: true chain bounded, forks diverge")
    ax.grid(True, which="both", alpha=0.25); ax.legend(loc="lower left")
    fig.tight_layout(); fig.savefig(f"{DIAG}/residual_rolling.png", dpi=130)
    plt.close(fig)


def fig_tightness(Ws=(2.0, 4.0, 8.0), maxh=10.0):
    btc = load("BTC")
    hs = [i * 0.5 for i in range(int(maxh / 0.5) + 1)]
    fig, ax = plt.subplots(figsize=(10, 6))
    for W in Ws:
        m = calibrate(W, hs, btc)
        ss = []
        e = 1.0 + W
        while e <= btc[-1][0]:
            mod = fit(e, W, btc)
            if mod:
                ss.append(mod["s"])
            e += 0.5
        ss.sort()
        s_typ = ss[len(ss) // 2] if ss else 0.2
        y = [m[h] * s_typ for h in hs]
        ax.plot(hs, y, lw=2, marker="o", ms=3,
                label=f"history window W={W:g}y  (σ≈{s_typ:.2f} dex)")
    ax.axvspan(5, maxh, color="#c00", alpha=0.06)
    ax.text(5.1, ax.get_ylim()[1] * 0.55, "thin calibration\n(few fit windows\nreach this far)",
            color="#c00", fontsize=8)
    ax.axhline(math.log10(10), color="#888", ls="--", lw=1)
    ax.text(0.2, math.log10(10) + 0.05, "x10", color="#888", fontsize=8)
    ax.axhline(math.log10(100), color="#888", ls="--", lw=1)
    ax.text(0.2, math.log10(100) + 0.05, "x100", color="#888", fontsize=8)
    ax.set_xlabel("staleness h = years since the trusted checkpoints stopped (log10 box)")
    ax.set_ylabel("95% band half-width (dex)")
    ax.set_title("Fit tightness required vs staleness, for 95% coverage of the true chain")
    ax.grid(True, alpha=0.25); ax.legend()
    fig.tight_layout(); fig.savefig(f"{DIAG}/tightness_vs_staleness.png", dpi=130)
    plt.close(fig)


def fig_start_grid(W=4.0, Ss=(0, 1, 2, 3, 4, 6, 8), starts=(2014, 2016, 2018, 2020, 2022, 2024, 2026)):
    btc = load("BTC")

    def m_of(h):
        # same guarded value used by attack_cost.py and calibration_audit.py
        return m_band(W, h, btc)

    band = [[float("nan")] * len(starts) for _ in Ss]
    margin = [[float("nan")] * len(starts) for _ in Ss]
    others = ["BCH", "BSV", "XEC"]
    series = {c: load(c) for c in others}
    for i, S in enumerate(Ss):
        for j, cal in enumerate(starts):
            x0 = cal - 2009.0
            e = x0 - S
            mod = fit(e, W, btc)
            if not mod or e - W < 1.0:
                continue
            b = m_of(S) * denom(mod, x0)
            band[i][j] = b
            sep = 0.0
            for c in others:
                pts = series[c]
                xs = [p for p in pts if p[0] <= x0 + 0.4]
                if not xs:
                    continue
                y = xs[-1][1]
                sep = max(sep, predict(mod, x0) - y)  # best-case fork; worst-case is in calibration_audit.py
            if sep > 0:
                margin[i][j] = sep - b

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    import numpy as np
    B = np.array(band); M = np.array(margin)
    im1 = ax1.imshow(B, cmap="viridis", aspect="auto", origin="lower")
    ax1.set_title(f"required 95% band half-width (dex), W={W:g}y")
    for i in range(len(Ss)):
        for j in range(len(starts)):
            if not math.isnan(B[i, j]):
                ax1.text(j, i, f"{B[i,j]:.1f}", ha="center", va="center",
                         color="w", fontsize=7)
    ax1.set_xticks(range(len(starts))); ax1.set_xticklabels(starts)
    ax1.set_yticks(range(len(Ss))); ax1.set_yticklabels(Ss)
    ax1.set_xlabel("node start year"); ax1.set_ylabel("checkpoint staleness (years)")
    fig.colorbar(im1, ax=ax1, fraction=0.046)

    img = ax2.imshow(M, cmap="RdYlGn", aspect="auto", origin="lower", vmin=-3, vmax=3)
    ax2.set_title("detection margin = fork divergence − band  (>0 = caught)")
    for i in range(len(Ss)):
        for j in range(len(starts)):
            if not math.isnan(M[i, j]):
                ax2.text(j, i, f"{M[i,j]:+.1f}", ha="center", va="center", fontsize=7)
            elif not math.isnan(B[i, j]):
                ax2.text(j, i, "no fork", ha="center", va="center", fontsize=6, color="#555")
    ax2.set_xticks(range(len(starts))); ax2.set_xticklabels(starts)
    ax2.set_yticks(range(len(Ss))); ax2.set_yticklabels(Ss)
    ax2.set_xlabel("node start year"); ax2.set_ylabel("checkpoint staleness (years)")
    fig.colorbar(img, ax=ax2, fraction=0.046)
    fig.suptitle("A node booting at (start year, checkpoint staleness): band needed vs detection")
    fig.tight_layout(); fig.savefig(f"{DIAG}/start_grid.png", dpi=130)
    plt.close(fig)
    return B, M, Ss, starts


def main():
    os.makedirs(DIAG, exist_ok=True)
    fig_loglog();     print("wrote difficulty_loglog.png")
    fig_residuals();  print("wrote residual_rolling.png")
    fig_tightness();  print("wrote tightness_vs_staleness.png")
    B, M, Ss, starts = fig_start_grid(); print("wrote start_grid.png")
    print("\nband half-width (dex) by (staleness x start year):")
    print("stag\\start " + "".join(f"{s:>7}" for s in starts))
    for i, S in enumerate(Ss):
        print(f"{S:>10} " + "".join(f"{v:7.2f}" if not math.isnan(v) else "      -"
                                    for v in B[i]))


if __name__ == "__main__":
    main()
