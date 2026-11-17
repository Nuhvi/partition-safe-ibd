#!/usr/bin/env python3
"""Append new header and price samples to the stored data.

This script does not change the model and does not refit anything.  It only
extends the two data files:

    data/BTC.json             [height, unix_time, difficulty] per 2016 blocks
    data/btc_price_raw.json   daily price samples on the stored 4-day grid

The spine receives one row per finished difficulty period, plus one provisional
tip row.  A later run replaces that tip row, so the file stays consistent.  The
tip row is omitted when the current period has fewer than TIP_MIN blocks.  Such
a short sample would make a noisy hashrate point.

Sources:
    headers  mempool.space, then blockstream.info (same API layout)
    price    the blockchain.info market-price chart (the source of the stored
             file; the stored grid keeps every fourth day of the daily series)

Run this script directly, or let run_all.py call it.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
SPINE = os.path.join(DATA, "BTC.json")
PRICE = os.path.join(DATA, "btc_price_raw.json")

STEP = 2016                 # blocks per difficulty period (spine sample step)
TIP_MIN = 100               # minimum blocks in a partial tip sample
PRICE_STEP = 4 * 86400      # stored price grid: one sample each fourth day
PRICE_X0 = 1230940800       # first stored price sample (2009-01-03)
HEADER_APIS = ("https://mempool.space/api", "https://blockstream.info/api")
PRICE_API = ("https://api.blockchain.info/charts/market-price"
             "?timespan=all&format=json&sampled=false")
UA = "partition-safe-ibd/1.0"


def _get(url, timeout=40, tries=3):
    """GET a URL as text, with short backoff on network errors."""
    last = None
    for i in range(tries):
        req = urllib.request.Request(url, headers={
            "User-Agent": UA,
            "Accept": "application/json",
        })
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode()
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"GET {url} failed: {last}")


def _json(url):
    return json.loads(_get(url))


def _header(height):
    """[height, time, difficulty] for one block, first API that answers."""
    err = None
    for api in HEADER_APIS:
        try:
            h = _get(f"{api}/block-height/{height}").strip()
            b = _json(f"{api}/block/{h}")
            return [int(b["height"]), int(b["timestamp"]),
                    float(b["difficulty"])]
        except (RuntimeError, KeyError, ValueError) as e:
            err = e
    raise RuntimeError(f"no header for height {height}: {err}")


def _tip():
    err = None
    for api in HEADER_APIS:
        try:
            return int(_get(f"{api}/blocks/tip/height").strip())
        except (RuntimeError, ValueError) as e:
            err = e
    raise RuntimeError(f"no tip height: {err}")


def _write(path, obj, **kw):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, **kw)
        f.write("\n")
    os.replace(tmp, path)


def refresh_spine(path=SPINE, dry=False):
    """Append new difficulty periods and a provisional tip row.

    Returns the list of added rows.
    """
    with open(path) as f:
        rows = json.load(f)
    # Drop a provisional tip row from an earlier run.  Rows on the 2016-block
    # grid are finished periods and stay.
    had_tip = bool(rows and rows[-1][0] % STEP)
    if had_tip:
        rows.pop()
    h0 = rows[-1][0]
    tip = _tip()
    if tip < h0:
        raise RuntimeError(f"tip {tip} is behind the stored height {h0}")
    new = []
    h = h0 + STEP
    while h <= tip:
        new.append(_header(h))
        h += STEP
    last = h - STEP
    if tip > last and tip - last >= TIP_MIN:
        new.append(_header(tip))
    if (new or had_tip) and not dry:
        _write(path, rows + new)
    n_period = sum(1 for r in new if r[0] % STEP == 0)
    if n_period:
        print(f"spine: +{n_period} periods, height {h0} -> {new[-1][0]} "
              f"({_date(rows[-1][1])} -> {_date(new[-1][1])})")
    elif new:
        print(f"spine: tip -> {new[-1][0]} ({_date(new[-1][1])})")
    else:
        print(f"spine: current at height {h0}")
    return new


def refresh_price(path=PRICE, dry=False):
    """Append new price samples on the stored 4-day grid.

    Returns the number of added samples.
    """
    with open(path) as f:
        stored = json.load(f)
    vals = stored["values"]
    have = {v["x"] for v in vals}
    api = _json(PRICE_API)
    if api.get("status") != "ok":
        raise RuntimeError(f"price API status {api.get('status')!r}")
    new = [v for v in api["values"]
           if v["x"] not in have and (v["x"] - PRICE_X0) % PRICE_STEP == 0]
    if new and not dry:
        vals.extend(new)
        vals.sort(key=lambda v: v["x"])
        _write(path, stored, separators=(",", ":"))
    if new:
        print(f"price: +{len(new)} samples, {_date(new[-1]['x'])}")
    else:
        print(f"price: current at {_date(vals[-1]['x'])}")
    return len(new)


def _date(t):
    return time.strftime("%Y-%m-%d", time.gmtime(t))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--dry-run", action="store_true",
                   help="print what would be added and write nothing")
    a = p.parse_args(argv)
    failed = False
    for name, fn in (("spine", refresh_spine), ("price", refresh_price)):
        try:
            fn(dry=a.dry_run)
        except Exception as e:  # keep going: one stale file is not fatal
            failed = True
            print(f"{name}: refresh failed ({e})", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
