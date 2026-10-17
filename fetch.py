#!/usr/bin/env python3
"""Fetch per-block difficulty series for the header-compatible SHA256d chains.

Only chains sharing Bitcoin's 80-byte header layout and SHA256d proof of work are
included, because their difficulty / chainwork is directly comparable:

    BTC  Bitcoin        genesis 2009-01-03              (reference chain)
    BCH  Bitcoin Cash   fork 2017-08-01 @ 478558
    BSV  Bitcoin SV     fork 2018-11-15 @ 556766 (from BCH, shares the BTC prefix)
    XEC  eCash (BCHA)   fork 2020-11-15 @ 661648 (from BCH)

Sources:
  * BTC  - the checkpoint spine `checkpoints.txt` (copied into this repo):
           one header every 2016 blocks, full history, no network needed.
  * BCH / XEC - the Blockchair API (free tier: <=30 requests / 60 s, so throttled).
  * BSV  - a public Bitcoin SV JSON-RPC node.

Output: data/<chain>.json  ->  [[height, unix_time, difficulty], ...]
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
SPINE = os.path.join(HERE, "checkpoints.txt")
GENESIS = 1231006505  # 2009-01-03 18:15:05 UTC

STEP = 20160  # sample every 20 difficulty periods (~20 weeks)

BLOCKCHAIR = {
    "BCH": ("bitcoin-cash", 478558, 478558),
    "XEC": ("ecash", 661648, 661648),
}
BSV_RPC = "https://bsv-rpc.publicnode.com"


class Throttle:
    """Keep at most `limit` requests inside any rolling `window` seconds."""

    def __init__(self, limit=28, window=60.0):
        self.limit, self.window, self.hits = limit, window, []

    def wait(self):
        now = time.time()
        self.hits = [t for t in self.hits if now - t < self.window]
        if len(self.hits) >= self.limit:
            time.sleep(self.window - (now - self.hits[0]) + 0.5)
        self.hits.append(time.time())


def _get(url, timeout=40):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; partition-safe-ibd/1.0)",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def diff_from_bits(bits):
    exp = bits >> 24
    man = bits & 0xFFFFFF
    return (0xFFFF * 2 ** 208) / (man * 256 ** (exp - 3))


def fetch_btc():
    rows = []
    with open(SPINE) as f:
        for i, line in enumerate(l.strip() for l in f if l.strip()):
            b = bytes.fromhex(line)
            rows.append([i * 2016,
                         int.from_bytes(b[68:72], "little"),
                         diff_from_bits(int.from_bytes(b[72:76], "little"))])
    return rows


def rpc(url, method, *params):
    body = json.dumps({"jsonrpc": "1.0", "id": 1, "method": method,
                       "params": list(params)}).encode()
    req = urllib.request.Request(url, body, {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (compatible; partition-safe-ibd/1.0)",
    })
    with urllib.request.urlopen(req, timeout=40) as r:
        out = json.loads(r.read())
    if out.get("error"):
        raise RuntimeError(out["error"])
    return out["result"]


def fetch_bsv():
    tip = rpc(BSV_RPC, "getblockcount")
    rows, h = [], 478558
    while h <= tip:
        hd = rpc(BSV_RPC, "getblockheader", rpc(BSV_RPC, "getblockhash", h))
        rows.append([h, hd["time"], diff_from_bits(int(hd["bits"], 16))])
        h += STEP
    return rows


def fetch_blockchair(chain):
    slug, start, _ = BLOCKCHAIR[chain]
    throttle, rows, h = Throttle(), [], start
    while True:
        url = f"https://api.blockchair.com/{slug}/blocks?q=id({h})"
        for attempt in range(6):
            throttle.wait()
            try:
                d = _get(url)
            except urllib.error.HTTPError:
                d = {"context": {"code": 429}}
            code = d.get("context", {}).get("code")
            if code == 200 and d.get("data"):
                break
            if code in (402, 429):
                time.sleep(30 * (attempt + 1))  # back off a long time
                continue
            d = None
            break
        if not d or not d.get("data"):
            sys.stderr.write(f"\n  {chain}: stopped at height {h} (code={code})\n")
            break
        b = d["data"][0]
        ts = int(time.mktime(time.strptime(b["time"], "%Y-%m-%d %H:%M:%S")) -
                 time.timezone)
        rows.append([b["id"], ts, b["difficulty"]])
        sys.stderr.write(f"\r  {chain}: height {h}  ({len(rows)} pts)")
        sys.stderr.flush()
        h += STEP
    sys.stderr.write("\n")
    return rows


def main():
    os.makedirs(DATA, exist_ok=True)
    for chain in (sys.argv[1:] or ["BTC", "BCH", "BSV", "XEC"]):
        path = os.path.join(DATA, f"{chain}.json")
        if os.path.exists(path):
            print(f"{chain}: cached ({path})")
            continue
        print(f"{chain}: fetching ...")
        rows = (fetch_btc() if chain == "BTC"
                else fetch_bsv() if chain == "BSV"
                else fetch_blockchair(chain))
        if not rows:
            print(f"{chain}: FAILED, no data")
            continue
        with open(path, "w") as f:
            json.dump(rows, f)
        print(f"{chain}: {len(rows)} points -> {path}")


if __name__ == "__main__":
    main()
