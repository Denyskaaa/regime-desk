"""Backtest the regime map with point-in-time weekly calls.

    python -m research.backtest            (after research/data has been pulled)

Writes research/out/*.csv and prints the result tables.
Everything uses data available at each Friday close; trades execute at the
next day's close and earn returns from the day after that.
"""
import json
import os
import time

import numpy as np
import pandas as pd

from pipeline import config, regime

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
OUT = os.path.join(HERE, "out")
QK = ["growth", "riskon", "riskoff", "value"]
QN = {"growth": "Growth", "riskon": "Risk ON", "riskoff": "Risk OFF", "value": "Value", "quality": "Quality"}
NBER = [("1990-07-01", "1991-03-31"), ("2001-03-01", "2001-11-30"),
        ("2007-12-01", "2009-06-30"), ("2020-02-01", "2020-04-30")]


# ------------------------------------------------------------------ data ---

def load():
    px = pd.read_csv(os.path.join(DATA, "prices_max.csv.gz"), index_col=0, parse_dates=True).sort_index()
    nom = pd.read_csv(os.path.join(DATA, "tsy_nominal.csv.gz"), index_col=0, parse_dates=True).sort_index()
    real = pd.read_csv(os.path.join(DATA, "tsy_real.csv.gz"), index_col=0, parse_dates=True).sort_index()
    fred = {
        "DGS2": nom["2 YR"].dropna(), "DGS10": nom["10 YR"].dropna(),
        "DGS3MO": nom["3 MO"].dropna(), "DFII10": real["10 YR"].dropna(),
    }
    fred["T10YIE"] = (fred["DGS10"] - fred["DFII10"]).dropna()
    return px, fred


def fridays(index, start, end=None):
    s = pd.Series(index, index=index)
    s = s[(s.index >= start) & ((s.index <= end) if end else True)]
    return list(s.groupby(s.index.to_period("W")).last())


# ------------------------------------------------- regime reconstruction ---

def reconstruct(px, fred, start_assets="2008-01-01", start_curve="1990-06-01"):
    # copper alone for "Copper + Lumber": the lumber contract on Yahoo only starts in 2022
    config.MEASURES["CULU"] = dict(type="price", ticker="HG=F", label="Copper")
    eng = regime.Engine(px, fred, {})
    rows, sigrows, curve_rows = [], [], []
    t0 = time.time()
    for win, kw in config.WINDOWS.items():
        off = pd.DateOffset(**kw)
        for d in fridays(fred["DGS10"].index, start_curve):
            c = eng.curve(d, off)
            if c:
                curve_rows.append(dict(date=d, win=win, **{k: c[k] for k in
                                       ("d2", "d10", "level", "slope", "quad", "clear", "clear_level", "clear_slope")}))
        for d in fridays(px["^SP500TR"].dropna().index, start_assets):
            res = eng.evaluate(d, off)
            row = dict(date=d, win=win, leader=res["assets"]["leader"], ax=res["assets"]["x"], ay=res["assets"]["y"])
            for q in res["quadrants"] + [res["quality"]]:
                row[f"net_{q['key']}"] = q["net"]
                row[f"n_{q['key']}"] = q["n"]
                for s in q["signals"]:
                    sigrows.append(dict(date=d, win=win, quad=q["key"], key=s["key"], expect=s["expect"],
                                        status=s["status"], z=s.get("z")))
            rows.append(row)
    print(f"reconstructed in {time.time() - t0:.0f}s")
    return eng, pd.DataFrame(rows), pd.DataFrame(sigrows), pd.DataFrame(curve_rows)


def leader_ex_yields(sig):
    """Asset leader using only non-rate signals (so it is independent of the curve)."""
    s = sig[~sig.key.isin(["NY", "RY", "IE", "Y2"]) & (sig.status != "na") & (sig.quad != "quality")].copy()
    s["v"] = s.status.map({"match": 1, "against": -1}).fillna(0)
    net = s.groupby(["date", "win", "quad"]).v.mean().unstack("quad")
    return net, net[QK].idxmax(axis=1)


# --------------------------------------------------------------- returns ---

def daily_returns(px, fred):
    idx = px["^SP500TR"].dropna().index
    r = px.reindex(idx).pct_change(fill_method=None)
    cash = (fred["DGS3MO"].reindex(idx).ffill() / 100 / 252).shift(1)
    y10 = fred["DGS10"].reindex(idx).ffill()
    bond_approx = (y10.shift(1) / 100 / 252 - 7.5 * y10.diff() / 100)  # 7-10Y Treasury approximation
    bonds = r["IEF"].where(r["IEF"].notna(), bond_approx)
    r["CASH"], r["BONDS"], r["BOND_APPROX"] = cash, bonds, bond_approx
    return r


def fwd(series_idx, dates, h):
    """Log change of a cumulative series from the day after each date to h trading days later."""
    s = series_idx.dropna()
    out = {}
    pos = s.index.searchsorted(pd.DatetimeIndex(dates), side="right")  # next trading day
    for d, p in zip(dates, pos):
        if p + h < len(s):
            out[d] = float(s.iloc[p + h] - s.iloc[p])
    return pd.Series(out)


def nw_t(x, lag):
    """Mean and Newey-West t-stat for overlapping observations."""
    x = pd.Series(x).dropna().values
    n = len(x)
    if n < 10:
        return np.nan, np.nan, n
    m = x.mean()
    e = x - m
    v = e @ e / n
    for L in range(1, lag + 1):
        w = 1 - L / (lag + 1)
        v += 2 * w * (e[L:] @ e[:-L]) / n
    return m, m / np.sqrt(v / n), n


# ------------------------------------------------------------ strategies ---

def run_weights(w, r, cost_bp=5):
    """w: daily weights (DataFrame, columns = return columns). Returns daily strategy returns."""
    w = w.reindex(r.index).ffill().fillna(0)
    ret = (w * r[w.columns].fillna(0)).sum(axis=1)
    turn = w.diff().abs().sum(axis=1).fillna(0)
    return ret - turn * cost_bp / 1e4


def to_daily_weights(signal_weights, r_index):
    """Weekly weights decided at Friday close -> traded next day close -> earn from the day after."""
    w = signal_weights.reindex(r_index.union(signal_weights.index)).ffill()
    return w.reindex(r_index).shift(2)


def stats(ret, cash):
    ret = ret.dropna()
    cash = cash.reindex(ret.index).fillna(0)
    yrs = len(ret) / 252
    eq = (1 + ret).cumprod()
    cagr = eq.iloc[-1] ** (1 / yrs) - 1
    vol = ret.std() * np.sqrt(252)
    ex = ret - cash
    sharpe = ex.mean() / ex.std() * np.sqrt(252) if ex.std() > 0 else np.nan
    dd = (eq / eq.cummax() - 1).min()
    return dict(CAGR=round(cagr * 100, 2), Vol=round(vol * 100, 2), Sharpe=round(sharpe, 2),
                MaxDD=round(dd * 100, 1), Years=round(yrs, 1))


def basket_w(tickers, avail, date):
    t = [x for x in tickers if x in avail and avail[x] <= date]
    return {x: 1 / len(t) for x in t} if t else {"CASH": 1.0}


ROTATION = {  # long-only playbook baskets, taken from the chart's ▲ lists
    "riskon": ["IWM", "SPHB", "EEM", "XLY", "XLI", "DBC", "GLD", "HYG"],
    "growth": ["EFA", "GLD", "IWF", "TLT", "IEF", "XLK", "QQQ"],
    "value": ["IWM", "XLB", "XLF", "IWD", "XLE", "XLI", "DBC", "EEM"],
    "riskoff": ["XLP", "UUP", "CASH"],
}


def main():
    os.makedirs(OUT, exist_ok=True)
    px, fred = load()
    print("prices", px.shape, "from", px.index[0].date(), "to", px.index[-1].date())
    eng, reg, sig, cur = reconstruct(px, fred)
    reg.to_csv(os.path.join(OUT, "regimes_assets.csv"), index=False)
    sig.to_csv(os.path.join(OUT, "signals.csv.gz"), index=False)
    cur.to_csv(os.path.join(OUT, "regimes_curve.csv"), index=False)
    print("done; rows", len(reg), len(sig), len(cur))


if __name__ == "__main__":
    main()
