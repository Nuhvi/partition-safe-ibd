#!/usr/bin/env python3
"""All-checkpoint scan: worst Phi, the implied network-share edge, median law."""
import model as M

NOW = M.BTC.t1


def year_of(t):
    return 2009 + M.BTC.x(t)


def main():
    best = (float("inf"), None, None)
    best_med = (float("inf"), None, None)
    n = 0
    for r in M.BTC.rows:
        t0 = r[1]
        if year_of(t0) < 2016 or t0 >= NOW - 86400:
            continue
        n += 1
        for k in range(1, 80):
            T = (NOW - t0) * k / 80
            p = M.phi_est(t0, T)
            pm = M.phi_est_median(t0, T)
            if p < best[0]:
                best = (p, t0, T)
            if pm < best_med[0]:
                best_med = (pm, t0, T)
    p, t0, T = best
    smax = p / (1.0 + p)
    print(f"sampled 2016+ checkpoints: {n}")
    print(f"bottom law: min Phi {p:.5f} at {year_of(t0):.3f}, T={T/86400:.1f} d")
    print(f"  max network share = {100*smax:.3f}%")
    print(f"  5% network line = {100*M.network_share_to_honest(0.05):.3f}% of honest")
    print(f"  10% network line = {100*M.network_share_to_honest(0.10):.3f}% of honest")
    print(f"median law: min Phi {best_med[0]:.5f} at "
          f"{year_of(best_med[1]):.3f}, T={best_med[2]/86400:.1f} d")


if __name__ == "__main__":
    main()
