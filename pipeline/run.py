"""Fetch data, compute everything, write docs/data/*.json.

    python -m pipeline.run                 # normal scheduled run
    python -m pipeline.run --force-macro   # also refresh every FRED series now
    python -m pipeline.run --sample DIR    # offline preview with synthetic data
"""
import argparse
import json
import math
import subprocess
import os
import sys
from datetime import datetime, timedelta, timezone

from . import fetch, macro, markets, regime, sample

DOCS_DATA = os.path.join(fetch.ROOT, "docs", "data")


def clean(o):
    if isinstance(o, float):
        return o if math.isfinite(o) else None
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if hasattr(o, "item"):  # numpy scalars
        return clean(o.item())
    return o


def write(name, obj):
    os.makedirs(DOCS_DATA, exist_ok=True)
    with open(os.path.join(DOCS_DATA, name), "w") as f:
        json.dump(clean(obj), f, separators=(",", ":"), allow_nan=False)


def _age_hours(iso):
    if not iso:
        return 1e9
    return (datetime.now(timezone.utc) - datetime.fromisoformat(iso)).total_seconds() / 3600


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", metavar="DIR", help="build from synthetic data written to DIR")
    ap.add_argument("--no-fetch", action="store_true", help="rebuild from cached data only")
    ap.add_argument("--force-macro", action="store_true")
    ap.add_argument("--macro-hours", type=float, default=3.0,
                    help="refresh FRED when the cached copy is older than this")
    a = ap.parse_args(argv)

    # Runs can be triggered twice for the same slot (GitHub's schedule and the external timer).
    # They queue one after another, but each checks out the commit it was triggered on, so catch
    # up with any data the previous run saved first; otherwise saving our data would conflict.
    if os.environ.get("GITHUB_ACTIONS") == "true" and not a.sample:
        subprocess.run(["git", "pull", "-q", "--ff-only", "origin", os.environ.get("GITHUB_REF_NAME", "main")],
                       cwd=fetch.ROOT, check=False)

    meta_path = os.path.join(fetch.DATA, "meta.json")
    meta = json.load(open(meta_path)) if os.path.exists(meta_path) else {}

    if a.sample:
        sample.generate(a.sample)
        meta = dict(sample=True, market_fetched=fetch.now_iso(), macro_fetched=fetch.now_iso())
    elif not a.no_fetch:
        _, errs, missing = fetch.fetch_prices()
        meta.update(market_fetched=fetch.now_iso(), market_errors=errs[-20:], market_missing=missing,
                    sample=False)
        print(f"prices: {len(missing)} missing {missing} {errs[-3:]}", file=sys.stderr)
        if a.force_macro or _age_hours(meta.get("macro_fetched")) >= a.macro_hours:
            ferrs = fetch.fetch_fred()
            meta.update(macro_fetched=fetch.now_iso(), macro_errors=ferrs)
            print(f"fred: {len(ferrs)} errors {ferrs[:5]}", file=sys.stderr)

    prices, fred = fetch.load_prices(), fetch.load_fred()
    if prices.empty:
        sys.exit("No price data available; nothing to build.")

    market_json = markets.build(prices, fred)
    macro_json, derived = macro.build(fred)
    regime_json = regime.build(prices, fred, derived, macro_json)

    meta["built"] = fetch.now_iso()
    write("market.json", market_json)
    write("macro.json", macro_json)
    write("regime.json", regime_json)
    write("meta.json", dict(
        built=meta["built"], sample=meta.get("sample", False),
        market_fetched=meta.get("market_fetched"), macro_fetched=meta.get("macro_fetched"),
        market_missing=meta.get("market_missing", []), macro_missing=macro_json.get("missing", []),
        market_asof=regime_json["asof"],
    ))
    if not a.sample:
        os.makedirs(fetch.DATA, exist_ok=True)
        json.dump(meta, open(meta_path, "w"), indent=1)
    print("built", meta["built"], file=sys.stderr)


if __name__ == "__main__":
    main()
