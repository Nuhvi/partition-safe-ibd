# research/ — model and figures

The write-up is in [`../README.md`](../README.md). This directory contains only
the model and the scripts that produce the figures it uses.

## Files

| file | output | what it shows |
|---|---|---|
| `model.py` | — | spine, chainwork, power-law hashrate, estimated-work bar, $\Phi$ |
| `estimated_hashrate.py` | `estimated_hashrate.png` | actual vs power-law hashrate, 2010–2026 |
| `estimated_work_history.py` | `estimated_work_history.png` | $\Phi$ from selected checkpoints over the whole history; 5% safe, 10% not in 2018–20 |
| `cost_5pct.py` | `cost_5pct.png` | 5% attacker: work cost + foregone profit |
| `run_all.py` | — | runs the three scripts |

`data/BTC.json` is the sampled header spine (one row per 2016-block period);
`data/btc_price_raw.json` is the price history. `figs.py` holds the shared
matplotlib style.

## Model

`Chain` stores the spine, the difficulty step function, and prefix chainwork.
`work(a,b)` is realised chainwork in hashes. The price law is converted to
hashrate by the `dbtc` relation; the estimated-work bar is

$$
\text{bar}(T)=r_0\,\hat h(T),
\qquad
r_0=\frac{H_{\text{est}}(t_0)}{H_{\text{actual}}(t_0)}.
$$

`phi_est(t0,T)` is `bar / honest_work`: at most 1 for the honest chain, above
`s` to keep an `s`-fork out.

## Reproduce

```sh
../.venv/bin/python run_all.py
```
