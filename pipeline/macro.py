"""Build docs/data/macro.json: every indicator from the slide, transformed and trended."""
import numpy as np
import pandas as pd

from . import config

FREQ_NAMES = {"D": "daily", "W": "weekly", "M": "monthly", "Q": "quarterly"}
PER_YEAR = {"D": 252, "W": 52, "M": 12, "Q": 4}


def infer_freq(s):
    if len(s) < 3:
        return "M"
    gap = np.median(np.diff(s.index.values).astype("timedelta64[D]").astype(float))
    if gap < 5:
        return "D"
    if gap < 12:
        return "W"
    if gap < 45:
        return "M"
    return "Q"


def transform(s, how, freq):
    if how == "level":
        return s
    if how == "yoy":
        if freq == "D":
            prev = s.reindex(s.index - pd.DateOffset(years=1), method="ffill")
            prev.index = s.index
            return (s / prev - 1) * 100
        return (s / s.shift(PER_YEAR[freq]) - 1) * 100
    if how == "mom":
        return (s / s.shift(1) - 1) * 100
    if how == "diff":
        return s.diff()
    if how == "ann3m":
        return ((s / s.shift(3)) ** 4 - 1) * 100
    raise ValueError(how)


# ------------------------------------------------------------ derived ---

def _monthly(s, how="last"):
    s = s.dropna()
    r = s.resample("ME")
    return (r.mean() if how == "mean" else r.last()).dropna()


def real_ahe(fred):
    ahe, cpi = fred.get("CES0500000003"), fred.get("CPIAUCSL")
    if ahe is None or cpi is None:
        return None
    a = _monthly(ahe)
    c = _monthly(cpi)
    df = pd.concat([a, c], axis=1, keys=["a", "c"]).dropna()
    out = ((df.a / df.a.shift(12) - 1) - (df.c / df.c.shift(12) - 1)) * 100
    out = out.dropna()
    out.index = out.index.to_period("M").to_timestamp()
    return out


def lei_proxy(fred):
    """Free-data leading index: average z-score of 6-month changes in
    hours, claims (inverted), orders, permits, stocks, the curve and sentiment."""
    spec = [  # (series, monthly aggregation, change type, sign)
        ("AWHMAN", "last", "diff", 1),
        ("ICSA", "mean", "pct", -1),
        ("NEWORDER", "last", "pct", 1),
        ("PERMIT", "last", "pct", 1),
        ("SP500", "mean", "pct", 1),
        ("T10YFF", "mean", "diff", 1),
        ("UMCSENT", "last", "diff", 1),
    ]
    parts = []
    for sid, agg, chg, sign in spec:
        s = fred.get(sid)
        if s is None or len(s) < 30:
            continue
        m = _monthly(s, agg)
        c = (m - m.shift(6)) if chg == "diff" else (m / m.shift(6) - 1)
        c = c.dropna()
        if len(c) < 24:
            continue
        z = (c - c.rolling(120, min_periods=36).mean()) / c.rolling(120, min_periods=36).std()
        parts.append(sign * z.rename(sid))
    if len(parts) < 3:
        return None
    df = pd.concat(parts, axis=1)
    # The current month is incomplete for monthly releases; only keep months
    # where most components have reported
    need = min(5, len(parts))
    out = df.mean(axis=1, skipna=True)[df.notna().sum(axis=1) >= need].dropna()
    out.index = out.index.to_period("M").to_timestamp()
    return out


def derived_series(fred):
    d = {}
    r = real_ahe(fred)
    if r is not None and len(r):
        d["REAL_AHE"] = r
    l = lei_proxy(fred)
    if l is not None and len(l):
        d["LEI_PROXY"] = l
    return d


# --------------------------------------------------------------- rows ---

def _r(x, dp):
    if x is None or not np.isfinite(x):
        return None
    return round(float(x), dp + 2)


def trend_status(t, freq, good):
    """Compare the recent level of the transformed series with the period before."""
    t = t.dropna()
    if len(t) < 8:
        return None, None
    if freq == "D":
        recent = t.iloc[-5:].mean()
        before = t[t.index <= t.index[-1] - pd.DateOffset(months=1)].iloc[-5:].mean()
        hist = t.iloc[-1260:]
        tol = 0.25 * (hist.diff(21).std() or 0)
    elif freq == "W":
        recent, before = t.iloc[-4:].mean(), t.iloc[-8:-4].mean()
        tol = 0.25 * (t.iloc[-260:].diff(4).std() or 0)
    elif freq == "M":
        recent, before = t.iloc[-3:].mean(), t.iloc[-6:-3].mean()
        tol = 0.25 * (t.iloc[-60:].diff(3).std() or 0)
    else:
        recent, before = t.iloc[-1], t.iloc[-2]
        tol = 0.25 * (t.iloc[-20:].diff().std() or 0)
    delta = recent - before
    if not np.isfinite(delta):
        return None, None
    if abs(delta) <= tol:
        return "steady", float(delta)
    up = delta > 0
    if good == "up":
        return ("improving" if up else "worsening"), float(delta)
    if good == "down":
        return ("worsening" if up else "improving"), float(delta)
    return ("rising" if up else "falling"), float(delta)


def history(t, freq):
    t = t.dropna()
    t = t[t.index > t.index[-1] - pd.DateOffset(years=5)]
    if freq == "D":  # one point per week, keeping each week's real last date
        t = t.groupby(t.index.to_period("W")).tail(1)
    return [[d.strftime("%Y-%m-%d"), round(float(v), 4)] for d, v in t.items()]


def build_row(cfg, s):
    s = s.dropna().sort_index()
    if cfg.get("scale"):
        s = s * cfg["scale"]
    freq = infer_freq(s)
    t = transform(s, cfg["transform"], freq).dropna()
    if t.empty:
        return None
    dp = cfg.get("dp", 1)
    last = float(t.iloc[-1])
    if freq == "D":
        ref = t[t.index <= t.index[-1] - pd.DateOffset(months=1)]
        prev, chg_label = (float(ref.iloc[-1]) if len(ref) else np.nan), "vs 1M ago"
    else:
        prev, chg_label = (float(t.iloc[-2]) if len(t) > 1 else np.nan), "vs prior"
    status, _ = trend_status(t, freq, cfg.get("good"))
    row = dict(
        id=cfg["id"], name=cfg["name"], unit=cfg.get("unit", ""), dp=dp,
        freq=FREQ_NAMES[freq], good=cfg.get("good"),
        last=_r(last, dp), prev=_r(prev, dp),
        chg=_r(last - prev, dp) if np.isfinite(prev) else None, chg_label=chg_label,
        date=t.index[-1].strftime("%Y-%m-%d"),
        status=status, note=cfg.get("note"),
        hist=history(t, freq),
    )
    if cfg.get("alt") == "ann3m" and freq == "M":
        a = transform(s, "ann3m", freq).dropna()
        if len(a):
            row["alt"] = dict(label="3-month annualized", value=_r(a.iloc[-1], dp), unit="%")
    if cfg.get("ma"):
        m = s.rolling(cfg["ma"]).mean().dropna()
        if len(m):
            row["alt"] = dict(label=f"{cfg['ma']}-week average", value=_r(m.iloc[-1], dp), unit=cfg.get("unit", ""))
    return row


def build(fred):
    derived = derived_series(fred)
    allser = {**fred, **derived}
    groups, missing = [], []
    for gname, sub, rows in config.MACRO_GROUPS:
        out = []
        for cfg in rows:
            s = allser.get(cfg["id"])
            if s is None or s.dropna().empty:
                missing.append(cfg["id"])
                continue
            r = build_row(cfg, s)
            if r:
                out.append(r)
        groups.append(dict(name=gname, sub=sub, rows=out, not_free=config.NOT_FREE.get(gname, [])))
    return dict(groups=groups, missing=missing), derived
