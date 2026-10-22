"""Turn regime calls into simple, pre-specified portfolios and compare with benchmarks."""
import numpy as np
import pandas as pd

from research.backtest import (QK, ROTATION, basket_w, daily_returns, load, run_weights, stats,
                               to_daily_weights)


def build(px, fred, reg, cur, start, end=None):
    r = daily_returns(px, fred)
    r = r[(r.index >= start) & ((r.index <= end) if end else True)]
    avail = {c: px[c].first_valid_index() for c in px.columns}
    avail["CASH"] = pd.Timestamp("1900-01-01")
    spx = px["^SP500TR"].dropna()
    sma = spx.rolling(200).mean()
    out = {}

    def wk_frame(rows, idx):
        return pd.DataFrame(rows, index=idx).fillna(0)

    # Benchmarks
    out["Buy & hold S&P 500"] = r["^SP500TR"]
    out["60/40 stocks/bonds"] = 0.6 * r["^SP500TR"] + 0.4 * r["BONDS"]
    fri = r.index.to_series().groupby(r.index.to_period("W")).last()
    trend = pd.DataFrame({"^SP500TR": (spx > sma).reindex(fri.values).astype(float).values,
                          "CASH": (spx <= sma).reindex(fri.values).astype(float).values}, index=fri.values)
    out["200-day trend filter"] = run_weights(to_daily_weights(trend, r.index), r)

    for win in ["1M", "3M"]:
        a = reg[reg.win == win].set_index("date").leader
        a = a[(a.index >= start) & ((a.index <= end) if end else True)]
        c = cur[cur.win == win].set_index("date")
        cq = c.quad.where(c.clear, "unclear").reindex(a.index)
        # Timing: out of stocks only when the map says Risk OFF
        w = pd.DataFrame({"^SP500TR": (a != "riskoff").astype(float), "CASH": (a == "riskoff").astype(float)})
        out[f"Assets {win}: cash in Risk OFF"] = run_weights(to_daily_weights(w, r.index), r)
        w = pd.DataFrame({"^SP500TR": (cq != "riskoff").astype(float), "CASH": (cq == "riskoff").astype(float)})
        out[f"Curve {win}: cash in Risk OFF"] = run_weights(to_daily_weights(w, r.index), r)
        # Rotation: hold the chart's favoured basket for the leading quadrant
        rows = [basket_w(ROTATION[q], avail, d) for d, q in a.items()]
        w = wk_frame(rows, a.index)
        out[f"Assets {win}: rotate into playbook"] = run_weights(to_daily_weights(w, r.index), r)
    res = pd.DataFrame({k: stats(v[v.index >= start], r["CASH"]) for k, v in out.items()}).T
    return res, out, r


if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore")
    px, fred = load()
    reg = pd.read_csv("research/out/regimes_assets.csv", parse_dates=["date"])
    cur = pd.read_csv("research/out/regimes_curve.csv", parse_dates=["date"])
    for s, e in [("2008-07-01", None), ("2008-07-01", "2016-12-31"), ("2017-01-01", None), ("2010-01-01", None)]:
        res, out, r = build(px, fred, reg, cur, s, e)
        print(f"\n=== {s} to {e or 'today'} ===")
        print(res.to_string())
