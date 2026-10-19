#!/usr/bin/env python3
"""Core model for the "100 current blocks" partition rule.

The idea (see ../README.md for the write-up):

  A node ships with a trusted Bitcoin header spine up to a *compile-time*
  checkpoint t0 (the tips in data/BTC.json; one header per 2016-block period).
  When it starts at wall-clock t_now it may be network-partitioned and so cannot
  tell whether the chain it is offered is the best chain.  It therefore refuses
  to finalize a candidate until the candidate carries, measured in blocks of
  work at the checkpoint difficulty,

      c(t0, T) = C / w0  >=  max( MATURITY * rho , T / TARGET )

  where C is the candidate's chainwork since t0, w0 the work of one block at the
  checkpoint, and rho the estimated work of one block now relative to w0.  The
  first term is MATURITY (=100) blocks at the *estimated current* work per
  block - the Coinbase-maturity bound; the second is one block per TARGET (=600
  seconds) of checkpoint age at the *checkpoint* rate, which needs no estimate.

Everything is measured in *hashes* (chainwork).  One block at difficulty D costs
D * 2**32 hashes; call that the block's *work*.  The realised hash rate over a
difficulty period is blocks * work / (period duration), which is the only rate
the data can support; the target rate work / TARGET is used only for reference.
The estimators fit work per block directly and return the dimensionless ratio
rho, so 2**32 appears in exactly one place (Chain.w).

The analysis turns on one dimensionless ratio:

      Phi(t0, T) = bar / W_honest

where W_honest = work(t0, t0+T) is the honest chain's realised work since the
checkpoint.  In checkpoint blocks, bar/w0 = max(MATURITY*rho, T/TARGET) and
W_honest/w0 = G * T/TARGET, with G the interval's mean work per block / w0.

  * the honest chain finalizes iff  Phi <= 1          (availability)
  * a fork of hash share s is kept out iff  Phi > s   (security)

so the rule is correct exactly on   s < Phi <= 1.  rho is the node's estimate,
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
TARGET = 600.0                # seconds per block (protocol constant)
MATURITY = 100                # coinbase maturity: blocks the attacker must redo
FIRST = 5.0                   # test checkpoints from 2014 (post-ASIC; see est_plaw)
PLAW_WIN = 4.0                # estimator: trailing window, years
PLAW_FLOOR = 2.0              # estimator: ignore pre-2011 difficulty noise when fitting


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

    def w(self, t):
        """Work of one block at the difficulty active at t (hashes)."""
        return self.D(t) * WORK

    def mean_w(self, t0, t1):
        """Work-weighted mean work per block over [t0, t1]."""
        secs = t1 - t0
        if secs <= 0:
            return 0.0
        return self.work(t0, t1) / (secs / TARGET)

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
        """mean work per block over [t0,t1] / work per block at t0 (the repo's G)."""
        w0 = self.w(t0)
        return self.mean_w(t0, t1) / w0 if w0 else float("nan")


BTC = Chain("BTC")


# --------------------------------------------------------------------- estimators
# A node only knows history up to t0.  Each estimator returns rho(t0, T): the
# estimated work of one block at t_now = t0 + T, relative to the checkpoint's
# w0 (so rho = 1 means "no growth").  The bar is then MATURITY * rho * w0.
# `k` is an optional conservatism factor (upper-confidence slack, in units of the
# extrapolation sd).

def est_flat(t0, T, chain=BTC):
    """No growth: current work per block = checkpoint work per block."""
    return 1.0


def est_exp(t0, T, win_years=2.0, cap_per_year=None, chain=BTC):
    """Extrapolate the trailing `win_years` work-per-block growth exponentially."""
    w0 = chain.w(t0)
    wp = chain.w(t0 - win_years * YEAR)
    if wp <= 0 or w0 <= 0:
        return 1.0
    g = (w0 / wp) ** (1.0 / win_years)
    if cap_per_year is not None:
        g = min(g, cap_per_year)
    return g ** (T / YEAR)


def _ols_loglog(t0, win_years, chain=BTC):
    """OLS of log10 work per block on log10 age; None if too short."""
    rows = [r for r in chain.rows
            if r[1] > GENESIS and (t0 - win_years * YEAR) <= r[1] <= t0]
    pts = [(math.log10(chain.x(r[1])), math.log10(chain.w(r[1]))) for r in rows if r[2] > 0]
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
        return 1.0
    x = math.log10(chain.x(t0 + T))
    pred = m["a"] + m["b"] * x
    if k:
        sd = m["s"] * math.sqrt(1.0 + 1.0 / m["n"] + (x - m["mx"]) ** 2 / m["sxx"])
        pred += k * sd
    return 10 ** pred / chain.w(t0)


def plaw_window_rows(t0, win_years, chain=BTC):
    """The rows the power law is fitted to: history in [t0 - win, t0], after
    PLAW_FLOOR.  win_years=None means all history."""
    lo = t0 - win_years * YEAR if win_years else -float("inf")
    return [r for r in chain.rows
            if chain.x(r[1]) >= PLAW_FLOOR and lo <= r[1] <= t0 and r[2] > 0]


def plaw_fit(t0, rows, chain=BTC):
    """Anchored power-law fit of work per block on chain age.

    Returns (y0, x0, p, r): the log10 work per block and log10 age at the
    checkpoint, the least-squares slope through that anchor, and the largest
    residual the fit needed to contain `rows`.  None if the fit is degenerate.
    """
    y0 = math.log10(chain.w(t0))
    x0 = math.log10(chain.x(t0))
    num = den = 0.0
    if len(rows) < 6:
        return None
    for r in rows:
        x = math.log10(chain.x(r[1]))
        num += (x - x0) * (math.log10(chain.w(r[1])) - y0)
        den += (x - x0) ** 2
    if den <= 0:
        return None
    p = num / den
    r = max(abs(math.log10(chain.w(rw[1])) - (y0 + p * (math.log10(chain.x(rw[1])) - x0)))
            for rw in rows)
    return y0, x0, p, r


def est_plaw(t0, T, win_years=PLAW_WIN, band=1.0, chain=BTC):
    """Recommended estimate: rho, a power law in chain age anchored at the
    checkpoint, lifted by the band the same fit needed for its own history.

    Work per block is a power law in chain age (log-log fit R^2 ~ 0.96 over
    2014-2026, vs 0.83 for an exponential): growth decelerates in proportion to
    age, so this tracks the curve instead of over-shooting it, roughly halving
    the over-shoot of the exponential estimate for the same low tail.

    The trend is the (anchored) least-squares slope of log10(work per block) on
    log10(age) over a trailing 4-year window, forced through (age(t0), w0) so its
    value at t0 is exact; rho(t0) = 1.  The margin is not a constant: it is
    kappa = 10**r, the largest relative departure that *this* fit needed to
    contain the history it was fitted to - self-calibrating, so a stretch where
    work wandered off the line gets a wider band.  It is applied one-sided
    (upward): over-shoot only delays finalization.

    In the code the exponent is written with the age ratio, i.e. the trend is
    (1 + T/(YEAR*a0))**p with a0 the checkpoint's age; w0, and with it the whole
    2**32 factor, cancels out of rho.

    Scope: validated on checkpoints from 2014 (FIRST), the post-ASIC regime.  A
    fit to the 2012-2013 history cannot anticipate the ASIC transition (say
    2013.05 -> 2,500x difficulty in two years) and under-shoots it.  This is a
    real limitation of the power-law form - the trailing-growth exponential
    over-shoots that transition instead - traded for a better modern-era tail.
    """
    f = plaw_fit(t0, plaw_window_rows(t0, win_years, chain=chain), chain)
    if f is None:
        return 1.0
    y0, x0, p, r = f
    return 10 ** (p * math.log10(chain.x(t0 + T) / chain.x(t0)) + band * r)


ESTIMATORS = {
    "flat": est_flat,
    "exp-2y": lambda t0, T: est_exp(t0, T, 2.0),
    "exp-3y": lambda t0, T: est_exp(t0, T, 3.0),
    "exp-4y": lambda t0, T: est_exp(t0, T, 4.0),
    "exp-1y": lambda t0, T: est_exp(t0, T, 1.0),
    "exp-2y-cap2x": lambda t0, T: est_exp(t0, T, 2.0, cap_per_year=2.0),
    "ols-4y": lambda t0, T: est_ols(t0, T, 4.0),
    "ols-4y+2sd": lambda t0, T: est_ols(t0, T, 4.0, k=2.0),
    "plaw-4y": lambda t0, T: est_plaw(t0, T, 4.0),
}


# --------------------------------------------------------------------- rule
# The bar is the larger of two independent guards, both in work units:
#   * fixed: MATURITY blocks at the node's *estimate* of the current work per
#     block.  Needs the estimator; guards short staleness (the coinbase bound).
#   * age:   the work a chain at the *checkpoint* rate would have done over T -
#     one block per TARGET - which needs no estimate and grows with staleness.
def fixed_bar(t0, T, est="flat", chain=BTC):
    """Work of MATURITY blocks at the estimated current work per block."""
    return MATURITY * ESTIMATORS[est](t0, T) * chain.w(t0)


def age_bar(t0, T, chain=BTC):
    """Work at the checkpoint rate over the checkpoint's age: T/TARGET blocks."""
    return chain.w(t0) * T / TARGET


def bar(t0, T, est="plaw-4y", chain=BTC):
    """The recommended rule: the larger of the two guards (work, hashes)."""
    return max(fixed_bar(t0, T, est, chain), age_bar(t0, T, chain))


def fixed_rule(est="flat"):
    """The fixed guard as a rule callable(t0, T) -> work, for experiments."""
    return lambda t0, T: fixed_bar(t0, T, est)


def phi(t0, T, bar_fn=bar, chain=BTC):
    """bar / honest work.  <=1 lets the honest chain finalize; >s keeps an
    s-attacker out; the rule is correct on s < phi <= 1."""
    w = chain.work(t0, t0 + T)
    return bar_fn(t0, T) / w if w > 0 else float("inf")


def finalize_time(t0, share=1.0, bar_fn=bar, chain=BTC, t_end=None):
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
        return share * chain.work(t0, t0 + T) >= bar_fn(t0, T)
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
