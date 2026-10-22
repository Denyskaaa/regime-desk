"""Build docs/data/market.json: last price and period moves for every ticker."""
import numpy as np
import pandas as pd

from . import config

PERIODS = ["d1", "w1", "m1", "m3", "ytd", "y1"]


def _ref_values(s):
    """Reference values for each period, looked up by calendar date."""
    last_date = s.index[-1]

    def at(d):
        sub = s[s.index <= d]
        return float(sub.iloc[-1]) if len(sub) else np.nan

    return {
        "d1": float(s.iloc[-2]) if len(s) > 1 else np.nan,
        "w1": at(last_date - pd.Timedelta(days=7)),
        "m1": at(last_date - pd.DateOffset(months=1)),
        "m3": at(last_date - pd.DateOffset(months=3)),
        "ytd": at(pd.Timestamp(year=last_date.year - 1, month=12, day=31)),
        "y1": at(last_date - pd.DateOffset(years=1)),
    }


def _clean(x, nd=4):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return None
    return round(float(x), nd)


def describe(s, kind):
    s = s.dropna()
    if len(s) < 2:
        return None
    last = float(s.iloc[-1])
    refs = _ref_values(s)
    chg = {}
    for k in PERIODS:
        ref = refs[k]
        if not np.isfinite(ref) or ref == 0:
            chg[k] = None
        elif kind == "yield":
            chg[k] = _clean((last - ref) * 100, 1)  # basis points
        else:
            chg[k] = _clean((last / ref - 1) * 100, 2)  # percent
    yr = s[s.index > s.index[-1] - pd.DateOffset(years=1)]
    hi, lo = float(yr.max()), float(yr.min())
    spark = s[s.index > s.index[-1] - pd.DateOffset(months=3)]
    return dict(
        last=_clean(last, 4),
        date=s.index[-1].strftime("%Y-%m-%d"),
        chg=chg,
        hi52=_clean(hi, 4), lo52=_clean(lo, 4),
        range52=_clean((last - lo) / (hi - lo), 3) if hi > lo else None,
        spark=[_clean(v, 4) for v in spark.values],
    )


def _yahoo_yield(s):
    # Yahoo has quoted ^TNX both as 4.25 and 42.5 over the years; normalise to percent
    s = s.dropna()
    if len(s) and s.median() > 20:
        s = s / 10
    return s


def build(prices, fred):
    groups = []
    for gname, items in config.MARKET_GROUPS:
        out = []
        for it in items:
            t, name = it[0], it[1]
            kind = it[2] if len(it) > 2 else "price"
            if t not in prices.columns:
                continue
            s = prices[t]
            if kind == "yield":
                s = _yahoo_yield(s)
            d = describe(s, kind)
            if d:
                out.append(dict(t=t, name=name, kind=kind, src="Yahoo", **d))
        if gname == "Rates":
            for sid, name in config.MARKET_FRED_RATES:
                if sid in fred:
                    d = describe(fred[sid], "yield")
                    if d:
                        out.append(dict(t=sid, name=name, kind="yield", src="FRED", **d))
        if out:
            groups.append(dict(name=gname, items=out))
    return dict(groups=groups)
