"""Rebuild the 3-month checklist with long-history substitutes and test the Risk OFF alert before 2008.

    python -m research.long_test          (after research/fetch_long.py has pulled research/data/long)

Most checklist items are ETFs launched 1998-2011. Each is replaced by an older stand-in:
  sector and style ETFs   -> Ken French daily industry and size/value portfolios
  SPY, IWM, IWC           -> Vanguard 500 Index (VFINX), Small-Cap Index (NAESX), DFA Micro Cap (DFSCX)
  EEM, EFA                -> Vanguard Emerging Markets Index (VEIEX), Ken French developed ex-US market
  LQD + HYG               -> Vanguard Long-Term Investment-Grade (VWESX) + High-Yield Corporate (VWEHX)
  DBC                     -> S&P GSCI index;  crude oil futures -> FRED WTI spot
  SHY, IEF, TLT           -> returns implied by 2-, 7/10- and 20/30-year Treasury yields
  TIPS yield, breakeven   -> before 2003: Cleveland Fed 10-year real rate and expected inflation
                             (monthly, used one month late), or left out (variant A)
Items with no stand-in (gold before 2000, high-beta and low-vol ETFs, ARKK) are left out
before their ETFs exist, exactly as the main backtest already does for 2008-2011.

The scores use the same math as pipeline/regime.py (vectorized; checked to match it exactly).
"""
import copy
import gzip
import os

import numpy as np
import pandas as pd

from pipeline import config, regime
from research.backtest import load, daily_returns, run_weights, to_daily_weights, stats, fwd

HERE = os.path.dirname(os.path.abspath(__file__))
LONG = os.path.join(HERE, "data", "long")
OUT = os.path.join(HERE, "out")
PRE = ("1990-07-01", "2008-06-30")
POST = ("2008-07-01", None)


# ------------------------------------------------------------------ data ---

def kf_table(name):
    """First table of a Ken French CSV (value-weighted), daily % returns."""
    t = gzip.open(os.path.join(LONG, f"{name}.csv.gz"), "rt", encoding="latin-1").read().splitlines()
    h = next(i for i, l in enumerate(t) if l.strip().startswith(","))
    cols = [c.strip() for c in t[h].split(",")[1:]]
    rows, j = [], h + 1
    while j < len(t) and t[j].strip() and t[j].strip()[0].isdigit():
        p = [x.strip() for x in t[j].split(",")]
        rows.append(p[:len(cols) + 1])
        j += 1
    idx = pd.to_datetime([r[0] for r in rows], format="%Y%m%d")
    df = pd.DataFrame([r[1:] for r in rows], index=idx, columns=cols).apply(pd.to_numeric, errors="coerce")
    return df.mask(df <= -99.99)


def level_from_pct(r):
    return (1 + r.dropna() / 100).cumprod()


def bond_from_yields(*series, duration):
    """Daily total return of a constant-maturity Treasury position from yield changes (first series
    with data on both days wins, so switching series never creates a jump)."""
    ys = [s.dropna() for s in series]
    idx = ys[0].index
    for s in ys[1:]:
        idx = idx.union(s.index)
    dy = pd.Series(np.nan, index=idx)
    carry = pd.Series(np.nan, index=idx)
    for s in reversed(ys):  # earlier series take priority
        s = s.reindex(idx)
        d = s.diff()
        ok = d.notna()
        dy[ok] = d[ok]
        carry[ok] = s.shift(1)[ok]
    r = carry / 100 / 252 - duration * dy / 100
    return (1 + r.fillna(0)).cumprod()


def spliced_changes(daily, monthly, lag_months=1):
    """Daily series from `daily`, extended back with changes of a monthly series (used one month late)."""
    m = monthly.dropna().copy()
    m.index = m.index + pd.DateOffset(months=lag_months)
    days = pd.bdate_range(m.index[0], daily.index[-1])
    pre = m.reindex(days, method="ffill")
    pre = pre[pre.index < daily.dropna().index[0]]
    d = pd.concat([pre.diff().fillna(0), daily.dropna().diff().fillna(0)])
    d = d[~d.index.duplicated(keep="last")].sort_index()
    lvl = d.cumsum()
    return lvl - lvl.iloc[-1] + daily.dropna().iloc[-1]


def load_long(variant="B"):
    px0, fred0 = load()
    y = pd.read_csv(os.path.join(LONG, "yahoo.csv.gz"), index_col=0, parse_dates=True)
    fd = pd.read_csv(os.path.join(LONG, "fred_daily.csv.gz"), index_col=0, parse_dates=True)
    fm = pd.read_csv(os.path.join(LONG, "fred_monthly.csv.gz"), index_col=0, parse_dates=True)
    ind = kf_table("kf_ind12")
    sbm = kf_table("kf_6sbm")
    ff3 = kf_table("kf_ff3")
    dev = kf_table("kf_dev_xus")

    cols = {}
    for k in ["NoDur", "Manuf", "Enrgy", "Chems", "BusEq", "Utils", "Hlth", "Money"]:
        cols["KF_" + k.upper()] = level_from_pct(ind[k])
    cols["KF_DISC"] = level_from_pct((ind["Durbl"] + ind["Shops"]) / 2)
    cols["KF_BIG_GROWTH"] = level_from_pct(sbm["BIG LoBM"])
    cols["KF_BIG_VALUE"] = level_from_pct(sbm["BIG HiBM"])
    cols["KF_MKT"] = level_from_pct(ff3["Mkt-RF"] + ff3["RF"])
    cols["KF_DEVXUS"] = level_from_pct(dev["Mkt-RF"] + dev["RF"])
    for t in ["VFINX", "NAESX", "DFSCX", "VEIEX", "VWEHX", "VWESX", "^SPGSCI"]:
        cols[t] = y[t].dropna()
    cols["OIL_WTI"] = fd["DCOILWTICO"].dropna()
    cols["T_SHY"] = bond_from_yields(fd["DGS2"], duration=1.9)
    cols["T_IEF"] = bond_from_yields(fd["DGS7"], fd["DGS10"], duration=7.5)
    cols["T_TLT"] = bond_from_yields(fd["DGS20"], fd["DGS30"], fd["DGS10"], duration=17)
    # items with no older stand-in keep their real tickers (and start when those start)
    for t in ["^VIX", "DX-Y.NYB", "GC=F", "HG=F", "^NDX", "^GSPC", "SPHB", "SPLV", "ARKK", "IWC", "SPY",
              "^SP500TR", "IEF"]:
        if t in px0.columns:
            cols[t] = px0[t].dropna()
    px = pd.DataFrame(cols).sort_index()
    px = px[px.index >= "1980-01-01"]

    fred = dict(fred0)
    fred["DGS10"] = fd["DGS10"].dropna()
    fred["DGS2"] = fd["DGS2"].dropna()
    if variant == "B":
        fred["DFII10"] = spliced_changes(fred0["DFII10"], fm["REAINTRATREARAT10Y"])
        fred["T10YIE"] = spliced_changes(fred0["T10YIE"], fm["EXPINF10YR"])
    return px, fred, px0, fred0


SUBS = {
    "COMM": dict(type="price", ticker="^SPGSCI"),
    "CORP": dict(type="basket", tickers=["VWESX", "VWEHX"]),
    "CULU": dict(type="price", ticker="HG=F"),
    "CYC": dict(type="basket", tickers=["KF_DISC", "KF_MANUF", "KF_CHEMS", "KF_MONEY", "KF_ENRGY"]),
    "CYCDEF": dict(type="ratio", num=["KF_DISC", "KF_MANUF", "KF_CHEMS", "KF_MONEY", "KF_ENRGY"],
                   den=["KF_NODUR", "KF_UTILS", "KF_HLTH"]),
    "DMEM": dict(type="ratio", num=["KF_DEVXUS"], den=["VEIEX"]),
    "EM": dict(type="price", ticker="VEIEX"),
    "EMDM": dict(type="ratio", num=["VEIEX"], den=["KF_DEVXUS"]),
    "HPE": dict(type="ratio", num=["KF_BIG_GROWTH"], den=["KF_BIG_VALUE"]),
    "LCSC": dict(type="ratio", num=["VFINX"], den=["NAESX"]),
    "LMGB": dict(type="basket", tickers=["T_TLT", "T_IEF"]),
    "LPE": dict(type="ratio", num=["KF_BIG_VALUE"], den=["KF_BIG_GROWTH"]),
    "MATFIN": dict(type="ratio", num=["KF_CHEMS", "KF_MONEY"], den=["KF_MKT"]),
    "OIL": dict(type="price", ticker="OIL_WTI"),
    "SCLC": dict(type="ratio", num=["NAESX"], den=["VFINX"]),
    "SGB": dict(type="price", ticker="T_SHY"),
    "SMALL": dict(type="ratio", num=["NAESX", "DFSCX"], den=["VFINX"]),
    "XLKXLB": dict(type="ratio", num=["KF_BUSEQ"], den=["KF_CHEMS"]),
    "XLPXLY": dict(type="ratio", num=["KF_NODUR"], den=["KF_DISC"]),
    "XLYXLP": dict(type="ratio", num=["KF_DISC"], den=["KF_NODUR"]),
}


def engine(px, fred, subs=True):
    saved = copy.deepcopy(config.MEASURES)
    config.MEASURES["CULU"] = dict(type="price", ticker="HG=F", label="Copper")
    if subs:
        for k, v in SUBS.items():
            config.MEASURES[k] = dict(config.MEASURES[k], **v)
            for drop in ("ticker", "tickers", "num", "den"):
                if drop not in v and drop in config.MEASURES[k] and drop in saved[k]:
                    config.MEASURES[k].pop(drop)
    eng = regime.Engine(px, fred, {})
    config.MEASURES.clear()
    config.MEASURES.update(saved)
    return eng


# ---------------------------------------------------- vectorized scoring ---

def item_z(m, dates, months=3, is_yield=False):
    m = m.dropna()
    idx = m.index
    pe = idx.searchsorted(dates, side="right") - 1
    ps = idx.searchsorted(dates - pd.DateOffset(months=months), side="right") - 1
    v = m.values
    vol = m.diff().rolling(252, min_periods=2).std().values
    ok = (pe + 1 >= 120) & (ps >= 0) & (pe >= 0)
    pe_c, ps_c = np.clip(pe, 0, None), np.clip(ps, 0, None)
    chg = v[pe_c] - v[ps_c]
    n = np.maximum(pe_c - ps_c, 1)
    sd = vol[pe_c]
    z = np.where(sd > 0, chg / (sd * np.sqrt(n)), 0.0)
    if is_yield:
        z = np.where(np.abs(chg) < regime.MIN_BP * np.sqrt(months), 0.0, z)
    # stale series (e.g. a stand-in that has stopped updating) give no reading
    stale = (dates - idx[pe_c]).days > 10
    return pd.Series(np.where(ok & ~stale, z, np.nan), index=dates)


def status(expect, z):
    b, S = config.Z_BAND, config.Z_STRONG
    if expect == "up":
        return np.select([z > b, z < -b], [1, -1], 0)
    if expect == "down":
        return np.select([z < -b, z > b], [1, -1], 0)
    if expect == "flat":
        return np.select([np.abs(z) <= b, np.abs(z) > S], [1, -1], 0)
    if expect == "flat_down":
        return np.select([z <= b, z > S], [1, -1], 0)
    raise ValueError(expect)


def scores(eng, dates, months=3, types=None):
    zc, out, items = {}, {}, {}
    for q in config.QUADRANTS:
        rows = []
        for k, lab, e in q["signals"]:
            typ = config.MEASURES[k]["type"]
            if typ == "macro":
                continue
            if k not in zc:
                s = eng.idx.get(k)
                zc[k] = item_z(s, dates, months, typ == "yield") if s is not None else pd.Series(np.nan, index=dates)
            z = zc[k].values
            rows.append(np.where(np.isnan(z), np.nan, status(e, np.nan_to_num(z))))
        A = np.vstack(rows)
        n = np.sum(~np.isnan(A), axis=0)
        match = np.nansum(A == 1, axis=0)
        against = np.nansum(A == -1, axis=0)
        net = np.where(n > 0, (match - against) / np.maximum(n, 1), 0.0)
        out[q["key"]] = pd.DataFrame({"net": np.round(net, 3), "match": match, "n": n}, index=dates)
    return out, pd.DataFrame(zc)


def leaders(sc):
    net = pd.DataFrame({k: v.net for k, v in sc.items()})
    mt = pd.DataFrame({k: v.match for k, v in sc.items()})
    top = net.eq(net.max(axis=1), axis=0)
    win = top & mt.eq(mt.where(top).max(axis=1), axis=0)
    return win.idxmax(axis=1).where(win.sum(axis=1) == 1, "tie"), net


def avg_leader_is_riskoff(net, days):
    a = net.rolling(days).mean()
    top = a.eq(a.max(axis=1), axis=0)
    return top["riskoff"] & (top.sum(axis=1) == 1)


# ------------------------------------------------------------ evaluation ---

def strategy(out, r):
    out = out.dropna().astype(float)
    w = pd.DataFrame({"^SP500TR": 1 - out, "CASH": out})
    wd = to_daily_weights(w, r.index)
    return run_weights(wd, r), wd["CASH"].fillna(0)


def clip(s, a, b):
    return s[(s.index >= a) & ((s.index <= b) if b else True)]


def episodes(wc, sp):
    blocks = (wc != wc.shift()).cumsum()
    rows = []
    for _, g in wc.groupby(blocks):
        if g.iloc[0] == 1:
            rows.append(dict(start=g.index[0].date(), end=g.index[-1].date(), days=len(g),
                             spx=round(float((1 + sp.reindex(g.index).fillna(0)).prod() - 1) * 100, 1)))
    return pd.DataFrame(rows)


def evaluate(name, out, r, period):
    a, b = period
    x, wc = strategy(out, r)
    s = stats(clip(x, a, b), r["CASH"])
    bh = stats(clip(r["^SP500TR"], a, b), r["CASH"])
    w = clip(wc, a, b)
    ep = episodes(w, r["^SP500TR"])
    yrs = len(w) / 252
    return dict(rule=name, CAGR=s["CAGR"], Sharpe=s["Sharpe"], MaxDD=s["MaxDD"], bh_CAGR=bh["CAGR"],
                bh_Sharpe=bh["Sharpe"], bh_MaxDD=bh["MaxDD"], out=round(w.mean() * 100, 1), alerts=len(ep),
                false=int((ep.spx > 0).sum()) if len(ep) else 0, switches_yr=round((w.diff().abs() > 0).sum() / yrs, 1)), ep
