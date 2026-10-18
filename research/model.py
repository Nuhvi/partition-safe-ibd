#!/usr/bin/env python3
"""Core model for the "100 current blocks" partition rule.

The idea (see final/README.md for the write-up):

  A node ships with a trusted Bitcoin header spine up to a *compile-time*
  checkpoint t0 (the tips in data/BTC.json; one header per 2016-block period).
  When it starts at wall-clock t_now it may be network-partitioned and so cannot
  tell whether the chain it is offered is the best chain.  It therefore refuses
  to finalize a candidate unless the candidate carries at least

      bar(t0, t_now) = THETA * Dhat(t0, T) * 2**32          T = t_now - t0

  of work since the checkpoint: the work of THETA (=100) blocks mined at the
  *current* difficulty Dhat, which the node can only *estimate* from the trusted
  history t <= t0.  THETA=100 is the Coinbase-maturity bound: 100 blocks at
  current difficulty is assumed prohibitive.

Everything is measured in *hashes* (chainwork).  One block at difficulty D costs
D * 2**32 hashes.  The realised hash rate over a difficulty period is
blocks * D * 2**32 / (period duration), which is the only rate the data can
support; the target rate D * 2**32 / 600 is used only for reference.

The whole analysis turns on one dimensionless ratio:

      Phi(t0, T) = bar / W_honest = THETA * Dhat * 2**32 / W(t0, t0+T)

where W(t0, t0+T) is the honest chain's realised work since the checkpoint.

  * the honest chain finalizes iff  Phi <= 1          (availability)
  * a fork of hash share s is kept out iff  Phi > s   (security)

so the rule is correct exactly on   s < Phi <= 1.  Dhat is the node's estimate,
so "how accurate must the estimate be?" becomes the central question.
"""
import json
import math
import os
from bisect import bisect_right

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

GENESIS = 1231006505          # 2009-01-03 18:15:05 UTC
YEAR = 31557600.0             # Julian year, seconds
WORK = 2 ** 32                # hashes per unit difficulty per block
TARGET = 600.0                # seconds per block
THETA = 100                   # coinbase maturity: blocks the attacker must redo
FIRST = 2.0                   # ignore the first ~2y (pre-2011 difficulty is noise)


def load(chain):
    """[[height, unix_time, difficulty], ...] sorted by height/time."""
    with open(os.path.join(DATA, f"{chain}.json")) as f:
        return sorted(json.load(f), key=lambda r: r[1])


class Chain:
    """A sampled header spine.  Difficulty is piecewise constant per period."""

    def __init__(self, name):
        self.name = name
        self.rows = load(name)
        self.t = [r[1] for r in self.rows]
        self.d = [r[2] for r in self.rows]
        self.h = [r[0] for r in self.rows]
        self.t0, self.t1 = self.t[0], self.t[-1]
        self.np = len(self.rows) - 1        # number of complete periods
        # prefix chainwork at each sample time: cum[i] = work(t_0, t_i)
        self.cum = [0.0]
        for j in range(self.np):
            self.cum.append(self.cum[-1] + (self.h[j + 1] - self.h[j]) * self.d[j] * WORK)

    def x(self, t):
        """Years since genesis."""
        return (t - GENESIS) / YEAR

    def D(self, t):
        """Difficulty of the block active at time t (step function)."""
        i = bisect_right(self.t, t) - 1
        i = min(max(i, 0), len(self.d) - 1)
        return self.d[i]

    def mean_D(self, t0, t1):
        """Work-weighted mean difficulty over [t0, t1]."""
        w = self.work(t0, t1)
        secs = t1 - t0
        if secs <= 0:
            return 0.0
        return w / (secs / TARGET * WORK)

    def work(self, t0, t1):
        """Realised chainwork (hashes) over [t0, t1], O(log n).

        Period i spans [t_i, t_{i+1}) with difficulty d_i and n_i = h_{i+1}-h_i
        blocks; its realised rate is n_i*d_i*2**32/(t_{i+1}-t_i).  Work is the
        integral of that rate, i.e. proportional-blocks * difficulty * 2**32.
        """
        if t1 <= t0:
            return 0.0
        if t0 <= self.t0:
            t0 = self.t0
        if t1 >= self.t1:
            t1 = self.t1
        i0 = min(max(bisect_right(self.t, t0) - 1, 0), self.np - 1)
        i1 = min(max(bisect_right(self.t, t1) - 1, 0), self.np - 1)
        per = lambda j: (self.h[j + 1] - self.h[j]) * self.d[j] * WORK
        if i0 == i1:
            frac = (t1 - t0) / (self.t[i0 + 1] - self.t[i0])
            return frac * per(i0)
        head = per(i0) * (self.t[i0 + 1] - t0) / (self.t[i0 + 1] - self.t[i0])
        tail = per(i1) * (t1 - self.t[i1]) / (self.t[i1 + 1] - self.t[i1])
        return head + (self.cum[i1] - self.cum[i0 + 1]) + tail


    def G(self, t0, t1):
        """mean difficulty over [t0,t1] / difficulty at t0 (the repo's G)."""
        d0 = self.D(t0)
        return self.mean_D(t0, t1) / d0 if d0 else float("nan")


BTC = Chain("BTC")


# --------------------------------------------------------------------- estimators
# A node only knows history up to t0.  Each estimator returns Dhat(t0, T): its
# guess at the difficulty current at t_now = t0 + T.  `k` is an optional
# conservatism factor (upper-confidence slack, in units of the extrapolation sd).

def est_flat(t0, T, chain=BTC):
    """No growth: current difficulty = checkpoint difficulty."""
    return chain.D(t0)


def est_exp(t0, T, win_years=2.0, cap_per_year=None, chain=BTC):
    """Extrapolate the trailing `win_years` difficulty growth exponentially."""
    d0 = chain.D(t0)
    dp = chain.D(t0 - win_years * YEAR)
    if dp <= 0 or d0 <= 0:
        return d0
    g = (d0 / dp) ** (1.0 / win_years)
    if cap_per_year is not None:
        g = min(g, cap_per_year)
    return d0 * g ** (T / YEAR)


def _ols_loglog(t0, win_years, chain=BTC):
    """OLS of log10 D on log10 age over a trailing window; None if too short."""
    rows = [r for r in chain.rows
            if r[1] > GENESIS and (t0 - win_years * YEAR) <= r[1] <= t0]
    pts = [(math.log10(chain.x(r[1])), math.log10(r[2])) for r in rows if r[2] > 0]
    n = len(pts)
    if n < 6:
        return None
    mx = sum(p[0] for p in pts) / n
    my = sum(p[1] for p in pts) / n
    sxx = sum((p[0] - mx) ** 2 for p in pts)
    if sxx <= 0:
        return None
    b = sum((p[0] - mx) * (p[1] - my) for p in pts) / sxx
    a = my - b * mx
    s = math.sqrt(max(sum((p[1] - (a + b * p[0])) ** 2 for p in pts) / (n - 2), 1e-12))
    return {"a": a, "b": b, "s": s, "sxx": sxx, "mx": mx, "n": n}


def est_ols(t0, T, win_years=4.0, k=0.0, chain=BTC):
    """Log-log trend extrapolation, optionally + k extrapolation sd (one-sided)."""
    m = _ols_loglog(t0, win_years, chain)
    if m is None:
        return chain.D(t0)
    x = math.log10(chain.x(t0 + T))
    pred = m["a"] + m["b"] * x
    if k:
        sd = m["s"] * math.sqrt(1.0 + 1.0 / m["n"] + (x - m["mx"]) ** 2 / m["sxx"])
        pred += k * sd
    return 10 ** pred


def est_flatbar(t0, T, chain=BTC):
    """Not a difficulty estimate - the *age-proportional* (flat) bar of the prior
    work (resistance.md): bar = D0 * (T/600) * 2**32.  Expressed as the Dhat
    that reproduces it: Dhat = D0 * T/(600*THETA).  Included as the reference
    rule to beat."""
    return chain.D(t0) * (T / (TARGET * THETA))


ESTIMATORS = {
    "flat": est_flat,
    "flatbar": est_flatbar,
    "exp-2y": lambda t0, T: est_exp(t0, T, 2.0),
    "exp-1y": lambda t0, T: est_exp(t0, T, 1.0),
    "exp-2y-cap2x": lambda t0, T: est_exp(t0, T, 2.0, cap_per_year=2.0),
    "ols-4y": lambda t0, T: est_ols(t0, T, 4.0),
    "ols-4y+2sd": lambda t0, T: est_ols(t0, T, 4.0, k=2.0),
    "max(100,flat)": lambda t0, T: max(est_exp(t0, T, 2.0, cap_per_year=2.0),
                                       est_flatbar(t0, T)),
}


# --------------------------------------------------------------------- rule
def bar(t0, T, est="flat", theta=THETA):
    """The work (hashes) a candidate must carry since t0.  T in seconds."""
    return theta * ESTIMATORS[est](t0, T) * WORK


def phi(t0, T, est="flat", theta=THETA, chain=BTC):
    """bar / honest work.  <=1 lets the honest chain finalize; >s keeps an
    s-attacker out; the rule is correct on s < phi <= 1."""
    w = chain.work(t0, t0 + T)
    return bar(t0, T, est, theta) / w if w > 0 else float("inf")


def finalize_time(t0, share=1.0, est="flat", theta=THETA, chain=BTC,
                  t_end=None, steps=400):
    """First T (seconds) at which a candidate holding `share` of the honest
    work clears the bar, or None.  share=1 is the honest chain, share=s a fork
    that forked at t0 and has mined with that hash share ever since."""
    t_end = t_end or chain.t1
    if t0 >= t_end:
        return None
    # geometric scan (finalization times span hours to decades)
    lo = 60.0
    hi = t_end - t0
    def clears(T):
        return share * chain.work(t0, t0 + T) >= bar(t0, T, est, theta)
    if clears(hi):
        # bisect for the first crossing
        for _ in range(80):
            mid = math.sqrt(lo * hi)
            if clears(mid):
                hi = mid
            else:
                lo = mid
        return hi
    return None
