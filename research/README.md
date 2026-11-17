# research/ — model and figures

The write-up is in [`../README.md`](../README.md). This directory contains only
the model and the scripts that produce the figures it uses.

## Files

| file | output | what it shows |
|---|---|---|
| `model.py` | — | spine, chainwork, power-law hashrate, estimated-work bar, $\Phi$ |
| `refresh.py` | updates `data/` | appends the latest header and price samples; no refit |
| `estimated_hashrate.py` | `estimated_hashrate.png` | actual vs power-law hashrate, 2010 to the data cut |
| `estimated_work_history.py` | `estimated_work_history.png` | $\Phi$ over the whole history; selected anchors, worst anchor, median law |
| `estimated_work_backtest.py` | — | all-checkpoint scan: min $\Phi$, network edge, median |
| `cost_5pct.py` | `cost_5pct.png` | 5% attacker: energy cost + foregone profit |
| `run_all.py` | — | refreshes the data, then runs the four scripts |

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

`run_all.py` calls `refresh.py` first. That appends the newest headers from
mempool.space and the newest prices from blockchain.info, then rebuilds the
figures. The model constants stay fixed; nothing is refitted. Use
`--offline` to rebuild the figures from the stored data only.

`refresh.py` stores one row per finished difficulty period, plus one
provisional tip row. Each later run replaces that tip row. A partial period
with fewer than 100 blocks is not stored, because the hashrate sample would be
too noisy.
