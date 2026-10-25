"""Rules built on things that hurt stocks in every era, tested decade by decade since 1928.

    python -m research.universal          (after research/fetch_long.py has pulled research/data/long)

The Risk OFF alert worked in 2008-2026 and failed in 1990-2008, and both verdicts rest on a handful
of episodes. A more universal rule should rest on mechanisms that don't depend on the era:
  trend         big bear markets keep falling for months; prices below their 10-month average flag it
  recessions    earnings collapse in recessions; rising unemployment flags one (with a 1-month
                publication lag)
  credit        lenders demand more when defaults loom; the Baa-Aaa corporate spread rising flags it
  yield curve   an inverted curve has preceded most US recessions since the 1950s
The trend + macro rules sell only when both agree, so ordinary dips (no recession) are sat through.

Monthly decisions at month-end, applied to the next month's return; 10bp per switch.
US stocks = Ken French market (all NYSE/AMEX/Nasdaq stocks, value-weighted, with dividends);
cash = 1-month T-bills. All parameters are the standard ones from the literature, chosen before testing.
"""
import os

import numpy as np
import pandas as pd

from research.long_test import kf_table

HERE = os.path.dirname(os.path.abspath(__file__))
LONG = os.path.join(HERE, "data", "long")
COST = 0.0010


def market():
    ff = kf_table("kf_ff3")
    d = ff[["Mkt-RF", "RF"]].dropna() / 100
    mkt_d = d["Mkt-RF"] + d["RF"]
    idx = (1 + mkt_d).cumprod()
    m = pd.DataFrame({
        "ret": (1 + mkt_d).groupby(mkt_d.index.to_period("M")).prod() - 1,
        "rf": (1 + d["RF"]).groupby(d.index.to_period("M")).prod() - 1,
        "close": idx.groupby(idx.index.to_period("M")).last(),
        "hi12": idx.rolling(252, min_periods=200).max().groupby(idx.index.to_period("M")).last(),
    })
    return m, idx


def macro():
    fm = pd.read_csv(os.path.join(LONG, "fred_monthly.csv.gz"), index_col=0, parse_dates=True)
    fm.index = fm.index.to_period("M")
    return fm


def signals(m, fm):
    """Out-of-market flags known at each month-end (True = hold cash next month)."""
    sma10 = m.close.rolling(10).mean()
    below = m.close < sma10
    out = {"Buy & hold": pd.Series(False, index=m.index),
           "Price below 10-month average": below,
           "10%+ below 12-month high": m.close / m.hi12 - 1 < -0.10}
    if "UNRATE" in fm:
        u = fm["UNRATE"].dropna()
        rising = (u > u.rolling(12).mean()).shift(1)              # month t-1 data is out in early month t
        out["Trend + rising unemployment"] = below & rising.reindex(m.index).fillna(False).astype(bool)
    if {"BAA", "AAA"} <= set(fm.columns):
        sp = (fm["BAA"] - fm["AAA"]).dropna()                     # default spread, monthly since 1919
        widening = sp > sp.rolling(12).mean()
        out["Trend + widening credit spread"] = below & widening.reindex(m.index).fillna(False).astype(bool)
    if {"GS10", "TB3MS"} <= set(fm.columns):
        curve = (fm["GS10"] - fm["TB3MS"]).dropna()
        inverted_lately = (curve < 0).rolling(12).max().astype(bool)
        out["Trend + curve inverted in past year"] = below & inverted_lately.reindex(m.index).fillna(False).astype(bool)
    return out


def run(m, out):
    pos = (~out.astype(bool)).astype(float).shift(1).fillna(1.0)   # decided at month-end, held next month
    r = pos * m.ret + (1 - pos) * m.rf - pos.diff().abs().fillna(0) * COST
    return r, pos


def stats(r, rf):
    r, rf = r.dropna(), rf.reindex(r.dropna().index)
    yrs = len(r) / 12
    eq = (1 + r).cumprod()
    ex = r - rf
    return dict(CAGR=round((eq.iloc[-1] ** (1 / yrs) - 1) * 100, 1),
                Sharpe=round(ex.mean() / ex.std() * np.sqrt(12), 2) if ex.std() > 0 else np.nan,
                MaxDD=round((eq / eq.cummax() - 1).min() * 100))


def evaluate(start="1928-01", decades=None):
    m, _ = market()
    fm = macro()
    m = m[m.index >= pd.Period(start, "M")]
    out = signals(m, fm)
    rows, dec = [], {}
    for name, o in out.items():
        r, pos = run(m, o)
        s = stats(r, m.rf)
        rows.append(dict(rule=name, **s, out=round((1 - pos).mean() * 100), switches_yr=round(pos.diff().abs().sum() / (len(pos) / 12), 1)))
        dec[name] = {f"{d}s": stats(r[(r.index.year >= d) & (r.index.year < d + 10)], m.rf)["Sharpe"]
                     for d in (decades or range(1930, 2030, 10))}
    return pd.DataFrame(rows).set_index("rule"), pd.DataFrame(dec).T


if __name__ == "__main__":
    pd.set_option("display.width", 220)
    for start, d0 in [("1928-01", 1930), ("1949-01", 1950), ("1955-01", 1960)]:
        tab, dec = evaluate(start, decades=range(d0, 2030, 10))
        print(f"\n=== {start} to 2026 ===")
        print(tab.to_string())
        print("\nSharpe by decade:")
        print(dec.to_string())
        bh = dec.loc["Buy & hold"]
        print("\nDecades with a better Sharpe than buy & hold:")
        for k in dec.index[1:]:
            v = dec.loc[k]
            ok = (v > bh).sum(), v.notna().sum()
            print(f"  {k:38s} {ok[0]} of {ok[1]}")
