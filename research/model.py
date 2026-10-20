#!/usr/bin/env python3
"""Core model: trusted spine, chainwork, and the estimated-work bar.

The node ships a trusted header spine up to a checkpoint t0.  It finalises a
candidate only when the candidate proves enough work since t0.  The bar here is
the *estimated-work bar*: the power-law hashrate path, converted to
cumulative work, normalised to the actual hashrate at t0.

    P(d)  = 10^(A + N log10 d)          bottom price law (d = days since genesis)
    H_est(t) = D0 (P/P0)^(1/b) 2^32/600  dbtc conversion, b = 0.673473
    r0    = H_est(t0) / H_actual(t0)
    bar(T) = r0 * price_bar(t0, T)       checkpoint blocks
    Phi(T) = bar(T) / honest_work(T)     honest finalises iff Phi <= 1;
                                          an s-fork is kept out iff Phi > s.

All work is in hashes; `price_bar` is in checkpoint blocks (divided by w0), so
the 2^32 factors cancel.  The rule is deliberately evaluated with the bottom
law, the conservative price level.
"""
import json
import math
import os
from bisect import bisect_right

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

GENESIS = 1231006505          # 2009-01-03 18:15:05 UTC
YEAR = 31557600.0             # Julian year, seconds
TARGET = 600.0                # seconds per block
WORK = 2 ** 32                # hashes per unit difficulty per block

# Price laws and the dbtc price -> difficulty conversion.
PRICE_A_BOTTOM = -17.432
PRICE_N_BOTTOM = 5.834
PRICE_A_MEDIAN = -17.016
PRICE_N_MEDIAN = 5.8
DBTC_D0 = 54621616002.15709
DBTC_P0 = 455.91017420322737
DBTC_B = 0.6734733015588255
PRICE_P = PRICE_N_BOTTOM / DBTC_B


def load(chain):
    with open(os.path.join(DATA, f"{chain}.json")) as f:
        return sorted(json.load(f), key=lambda r: r[1])


class Chain:
    """A sampled header spine; difficulty is a step function per period."""

    def __init__(self, name):
        self.name = name
        self.rows = load(name)
        self.t = [r[1] for r in self.rows]
        self.d = [r[2] for r in self.rows]
        self.h = [r[0] for r in self.rows]
        self.t0, self.t1 = self.t[0], self.t[-1]
        self.np = len(self.rows) - 1
        self.cum = [0.0]
        for j in range(self.np):
            self.cum.append(self.cum[-1] +
                            (self.h[j + 1] - self.h[j]) * self.d[j] * WORK)

    def x(self, t):
        """Years since genesis."""
        return (t - GENESIS) / YEAR

    def D(self, t):
        i = min(max(bisect_right(self.t, t) - 1, 0), len(self.d) - 1)
        return self.d[i]

    def w(self, t):
        """Work of one block at the difficulty active at t (hashes)."""
        return self.D(t) * WORK

    def work(self, t0, t1):
        """Realised chainwork (hashes) over [t0, t1], O(log n)."""
        if t1 <= t0:
            return 0.0
        t0 = max(t0, self.t0)
        t1 = min(t1, self.t1)
        if t1 <= t0:
            return 0.0
        i0 = min(max(bisect_right(self.t, t0) - 1, 0), self.np - 1)
        i1 = min(max(bisect_right(self.t, t1) - 1, 0), self.np - 1)
        per = lambda j: (self.h[j + 1] - self.h[j]) * self.d[j] * WORK
        if i0 == i1:
            return (t1 - t0) / (self.t[i0 + 1] - self.t[i0]) * per(i0)
        head = per(i0) * (self.t[i0 + 1] - t0) / (self.t[i0 + 1] - self.t[i0])
        tail = per(i1) * (t1 - self.t[i1]) / (self.t[i1 + 1] - self.t[i1])
        return head + (self.cum[i1] - self.cum[i0 + 1]) + tail


BTC = Chain("BTC")


def price_law(t, a=PRICE_A_BOTTOM, n=PRICE_N_BOTTOM):
    """Bottom (or median) price law, USD/BTC."""
    d = (t - GENESIS) / 86400.0
    return 10 ** (a + n * math.log10(d)) if d > 0 else 0.0


def estimated_hashrate(t, a=PRICE_A_BOTTOM, n=PRICE_N_BOTTOM):
    """Power-law hashrate, EH/s."""
    d = DBTC_D0 * (price_law(t, a, n) / DBTC_P0) ** (1.0 / DBTC_B)
    return d * WORK / TARGET / 1e18


def actual_hashrate(t):
    """Realised hashrate from the spine, EH/s."""
    return BTC.w(t) / TARGET / 1e18


def anchor_r0(t0):
    """Bottom-law estimated hashrate / actual hashrate at the checkpoint."""
    return estimated_hashrate(t0) / actual_hashrate(t0)


def price_bar(t0, T):
    """Cumulative power-law work since t0, in checkpoint blocks."""
    a0 = BTC.x(t0)
    x = T / (YEAR * a0)
    return a0 * YEAR / (TARGET * (PRICE_P + 1.0)) * \
        ((1.0 + x) ** (PRICE_P + 1.0) - 1.0)


def est_work_bar(t0, T):
    """The estimated-work bar: r0 * cumulative power-law work."""
    return anchor_r0(t0) * price_bar(t0, T)


def phi_est(t0, T):
    """Estimated-work bar / honest work.  <=1 live, >s keeps an s-fork out."""
    h = BTC.work(t0, t0 + T) / BTC.w(t0)
    return est_work_bar(t0, T) / h if h > 0 else float("inf")
