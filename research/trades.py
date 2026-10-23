"""Search the site's data for tradeable rules, with out-of-sample discipline.

    python -m research.trades            (needs research/data and research/out from backtest.py)

Every rule here was written down before it was run. Each is judged on the full
sample and separately on 2008-2016 and 2017-2026. A rule only "passes" if it
helps in BOTH halves and is statistically solid on the full sample (t >= 2).

Execution everywhere: signal at Friday close, trade at the next day's close,
5bp cost per unit of turnover. Pairs are shown as long/short spreads; for a
long-only investor read them as "hold A instead of B".
"""
import os
import warnings

import numpy as np
import pandas as pd

from pipeline import config, regime
from research.backtest import (QK, QN, daily_returns, load, run_weights, stats,
                               to_daily_weights)

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
HALVES = [("2008-16", "2008-07-01", "2016-12-31"), ("2017-26", "2017-01-01", None)]
FULL = ("Full", "2008-07-01", None)

# tradeable stand-ins for chart items (futures where no ETF exists in the data)
TRADE = {
    "HPE": (["IWF"], ["IWD"]), "LPE": (["IWD"], ["IWF"]),
    "LCSC": (["SPY"], ["IWM"]), "SCLC": (["IWM"], ["SPY"]), "SMALL": (["IWM", "IWC"], ["SPY"]),
    "XLKXLB": (["XLK"], ["XLB"]), "PTECH": (["QQQ"], ["SPY"]),
    "DMEM": (["EFA"], ["EEM"]), "EMDM": (["EEM"], ["EFA"]), "EM": (["EEM"], ["CASH"]), "DM": (["EFA"], ["CASH"]),
    "HBLB": (["SPHB"], ["SPLV"]), "HB": (["SPHB"], ["CASH"]),
    "GOLD": (["GLD"], ["CASH"]), "COMM": (["DBC"], ["CASH"]), "OIL": (["CL=F"], ["CASH"]),
    "CULU": (["HG=F"], ["CASH"]), "LMGB": (["TLT", "IEF"], ["CASH"]), "SGB": (["SHY"], ["CASH"]),
    "CORP": (["LQD", "HYG"], ["CASH"]), "CYC": (["XLY", "XLI", "XLB", "XLF", "XLE"], ["CASH"]),
    "CYCDEF": (["XLY", "XLI", "XLB", "XLF", "XLE"], ["XLP", "XLU", "XLV"]),
    "JUNK": (["ARKK", "IWC"], ["SPY"]), "XLYXLP": (["XLY"], ["XLP"]), "XLPXLY": (["XLP"], ["XLY"]),
    "USD": (["UUP"], ["CASH"]), "MATFIN": (["XLB", "XLF"], ["SPY"]), "FCF": (["COWZ"], ["SPY"]),
    "LARGE": (["SPY"], ["CASH"]),
}
SGN = {"up": 1, "down": -1}


# ------------------------------------------------------------------ tools ---

def spread(r, num, den):
    """Daily return of basket(num) minus basket(den); NaN when any leg is missing."""
    a = r[num].mean(axis=1, skipna=False)
    b = r[den].mean(axis=1, skipna=False)
    return a - b


def to_daily(on_weekly, idx):
    w = pd.DataFrame({"x": on_weekly.astype(float)})
    return to_daily_weights(w, idx)["x"]


def diff_test(x, on, lag=10):
    """Mean daily return while on vs while off, and the Newey-West t-stat of the gap."""
    d = pd.concat([x.rename("x"), on.rename("on")], axis=1).dropna()
    if len(d) < 250 or d.on.sum() < 40 or (1 - d.on).sum() < 40:
        return np.nan, np.nan, np.nan, 0
    X = np.column_stack([np.ones(len(d)), d.on.values])
    y = d.x.values
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ b
    n = len(y)
    S = (X * e[:, None]).T @ (X * e[:, None]) / n
    for L in range(1, lag + 1):
        w = 1 - L / (lag + 1)
        G = (X[L:] * e[L:, None]).T @ (X[:-L] * e[:-L, None]) / n
        S += w * (G + G.T)
    Xi = np.linalg.inv(X.T @ X / n)
    V = Xi @ S @ Xi / n
    on_mean, off_mean = b[0] + b[1], b[0]
    return on_mean * 252 * 100, off_mean * 252 * 100, b[1] / np.sqrt(V[1, 1]), int(d.on.sum())


def clip(s, start, end):
    return s[(s.index >= start) & ((s.index <= end) if end else True)]


def conditional_rows(name, x, on):
    """One result row: full sample plus each half, for a daily return x traded while `on`."""
    row = dict(rule=name)
    for lab, s, e in [FULL] + HALVES:
        onm, offm, t, n = diff_test(clip(x, s, e), clip(on, s, e))
        row[f"{lab} on"] = onm
        row[f"{lab} off"] = offm
        row[f"{lab} t"] = t
        row[f"{lab} days"] = n
    gaps = [row[f"{h[0]} on"] - row[f"{h[0]} off"] for h in HALVES]
    row["passes"] = bool(row["Full t"] >= 2 and all(np.isfinite(g) and g > 0 for g in gaps))
    return row


def strat_rows(name, ret, bench, cash):
    row = dict(rule=name)
    for lab, s, e in [FULL] + HALVES:
        a, b = clip(ret, s, e).dropna(), clip(bench, s, e).dropna()
        if len(a) < 250:
            continue
        sa, sb = stats(a, cash), stats(b, cash)
        row[f"{lab}"] = f"{sa['CAGR']:.1f}% / {sa['Sharpe']:.2f} / {sa['MaxDD']:.0f}%"
        row[f"{lab} bench"] = f"{sb['CAGR']:.1f}% / {sb['Sharpe']:.2f} / {sb['MaxDD']:.0f}%"
        row[f"{lab} dSharpe"] = round(sa["Sharpe"] - sb["Sharpe"], 2)
    return row


# ------------------------------------------------------------------ data ---

def setup():
    px, fred = load()
    config.MEASURES["CULU"] = dict(type="price", ticker="HG=F", label="Copper")
    eng = regime.Engine(px, fred, {})
    r = daily_returns(px, fred)
    reg = pd.read_csv(os.path.join(OUT, "regimes_assets.csv"), parse_dates=["date"])
    lead = reg[reg.win == "3M"].set_index("date").leader
    sig = pd.read_csv(os.path.join(OUT, "signals.csv.gz"), parse_dates=["date"])
    sig3 = sig[(sig.win == "3M") & (sig.status != "na")]
    s = sig3[sig3.quad != "quality"].copy()
    s["v"] = s.status.map({"match": 1, "against": -1}).fillna(0)
    net = s.groupby(["date", "quad"]).v.mean().unstack()[QK]
    return px, fred, eng, r, lead, sig, sig3, net


# ------------------------------------------------------------- batteries ---

def battery_items(r, lead, sig3):
    """A. Each playbook item traded while its quadrant leads (R), while the item's own
    3-month trend agrees (M), and while both hold (R+M)."""
    rows = []
    for q in config.QUADRANTS:
        on_r = lead == q["key"]
        for k, label, e in q["signals"]:
            if e not in SGN or k not in TRADE:
                continue
            num, den = TRADE[k]
            if any(t not in r.columns for t in num + den):
                continue
            x = SGN[e] * spread(r, num, den)
            st = sig3[(sig3.quad == q["key"]) & (sig3.key == k)].set_index("date").status
            on_m = (st == "match").reindex(on_r.index).fillna(False).astype(bool)
            for tag, on in [("R", on_r), ("M", on_m), ("R+M", on_r & on_m)]:
                row = conditional_rows(f"{QN[q['key']]}: {label}", x, to_daily(on, r.index))
                row["variant"] = tag
                rows.append(row)
    return pd.DataFrame(rows)


def battery_thresholds(r, net, lead):
    """B. Risk OFF strength thresholds (cash when Risk OFF's score >= x, leader or not)."""
    rows = []
    cash = r["CASH"]
    spx = r["^SP500TR"]
    for thr in [0.2, 0.3, 0.4, 0.5]:
        off = net["riskoff"] >= thr
        w = pd.DataFrame({"^SP500TR": 1 - off.astype(float), "CASH": off.astype(float)})
        rows.append(strat_rows(f"Cash when Risk OFF score >= {thr}", run_weights(to_daily_weights(w, r.index), r),
                               spx, cash))
    off = lead == "riskoff"
    w = pd.DataFrame({"^SP500TR": 1 - off.astype(float), "CASH": off.astype(float)})
    rows.append(strat_rows("Cash when Risk OFF leads (the site's rule)", run_weights(to_daily_weights(w, r.index), r),
                           spx, cash))
    return pd.DataFrame(rows)


def zscore_weekly(m, dates, months):
    """Point-in-time z-score of a cumulative measure's move over `months`, on a weekly grid."""
    m = m.dropna()
    vol = m.diff().rolling(252, min_periods=120).std()
    out = {}
    for d in dates:
        a = m[m.index <= d]
        b = m[m.index <= d - pd.DateOffset(months=months)]
        if len(a) < 130 or not len(b):
            continue
        n = int((a.index > b.index[-1]).sum())
        v = vol[vol.index <= d].iloc[-1]
        if v > 0:
            out[d] = (a.iloc[-1] - b.iloc[-1]) / (v * np.sqrt(max(n, 1)))
    return pd.Series(out)


def battery_macro(px, eng, r, dates):
    """C. Single macro signals from the literature, each a pre-specified trade."""
    cash, spx = r["CASH"], r["^SP500TR"]
    z = lambda key, mo=3: zscore_weekly(eng.idx[key], dates, mo)
    logp = lambda t: np.log(px[t].dropna())
    rows = []

    def timing(name, out_weekly):
        w = pd.DataFrame({"^SP500TR": 1 - out_weekly.astype(float), "CASH": out_weekly.astype(float)})
        rows.append(strat_rows(name, run_weights(to_daily_weights(w, r.index), r), spx, cash))

    hy_ief = zscore_weekly(logp("HYG") - logp("IEF"), dates, 3)
    timing("C1 Credit: cash when high yield lags Treasuries (3M z < -0.3)", hy_ief < -0.3)
    timing("C2 Defensive rotation: cash when staples beat discretionary (3M z > 0.3)", z("XLPXLY") > 0.3)
    cg = zscore_weekly(logp("HG=F") - logp("GC=F"), dates, 3)
    w = pd.DataFrame({"IEF": (cg < -0.3).astype(float), "SHY": (cg >= -0.3).astype(float)})
    rows.append(strat_rows("C3 Copper/gold falling -> 7-10y bonds, else 1-3y (vs 50/50)",
                           run_weights(to_daily_weights(w, r.index), r), 0.5 * r["IEF"] + 0.5 * r["SHY"], cash))
    usd = z("USD")
    w = pd.DataFrame({"EFA": (usd > 0.3).astype(float), "EEM": (usd <= 0.3).astype(float)})
    rows.append(strat_rows("C4 Dollar rising -> developed instead of emerging (vs 50/50)",
                           run_weights(to_daily_weights(w, r.index), r), 0.5 * r["EFA"] + 0.5 * r["EEM"], cash))
    vix1 = z("VIX", 1)
    timing("C5 Cash after a VIX spike (1M z > 1.5)", vix1 > 1.5)
    for t, key in [("DBC", "COMM"), ("GLD", "GOLD")]:
        zz = z(key)
        w = pd.DataFrame({t: (zz > 0.3).astype(float), "CASH": (zz <= 0.3).astype(float)})
        rows.append(strat_rows(f"C6 Trend: hold {t} only when its 3M z > 0.3 (vs holding {t})",
                               run_weights(to_daily_weights(w, r.index), r), r[t], cash))
    return pd.DataFrame(rows)


def every(dates, n):
    return dates[::n]


def battery_momentum(px, r):
    """D. Momentum rules on the site's own ETF universe (well-documented in the literature)."""
    cash = r["CASH"]
    rows = []
    spx_idx = px["^SP500TR"].dropna().index
    allfri = list(pd.Series(spx_idx, index=spx_idx).groupby(spx_idx.to_period("W")).last())
    spx = r["SPY"]
    periods = [("Full", "1999-07-01", None), ("1999-2007", "1999-07-01", "2007-12-31")] + HALVES

    def multi_period(name, ret, bench):
        row = dict(rule=name)
        for lab, s, e in periods:
            a, b = clip(ret, s, e).dropna(), clip(bench, s, e).dropna()
            if len(a) < 250:
                continue
            sa, sb = stats(a, cash), stats(b, cash)
            row[lab] = f"{sa['CAGR']:.1f}% / {sa['Sharpe']:.2f} / {sa['MaxDD']:.0f}%"
            row[f"{lab} bench"] = f"{sb['CAGR']:.1f}% / {sb['Sharpe']:.2f}"
            row[f"{lab} dSharpe"] = round(sa["Sharpe"] - sb["Sharpe"], 2)
        rows.append(row)

    # D1 sector rotation: top 3 of the 9 original sectors by 26-week return, rebalance every 4 weeks
    sect = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]
    p = px[sect].dropna()
    reb = [d for d in every(allfri, 4) if d >= p.index[0] + pd.Timedelta(days=200)]
    W, EW = [], []
    for d in reb:
        hist = p[p.index <= d]
        mom = hist.iloc[-1] / hist[hist.index <= d - pd.Timedelta(weeks=26)].iloc[-1] - 1
        top = mom.sort_values(ascending=False).index[:3]
        W.append({t: (1 / 3 if t in top else 0.0) for t in sect})
        EW.append({t: 1 / 9 for t in sect})
    W, EW = pd.DataFrame(W, index=reb), pd.DataFrame(EW, index=reb)
    rot = run_weights(to_daily_weights(W, r.index), r)
    ew = run_weights(to_daily_weights(EW, r.index), r)
    multi_period("D1 Sector momentum: top 3 of 9 by 6-month return (vs equal-weight sectors)", rot, ew)

    # D2 trend-filtered multi-asset: each of SPY, EFA, IEF, gold, commodities held only above its 200-day avg
    assets = {"SPY": "SPY", "EFA": "EFA", "IEF": "IEF", "GOLD": "GC=F", "DBC": "DBC"}
    reb = [d for d in allfri if d >= pd.Timestamp("2003-01-01")]
    W, B = [], []
    for d in reb:
        avail = [k for k, t in assets.items() if px[t].dropna().index[0] <= d - pd.Timedelta(days=300)]
        row, brow = {}, {}
        for k in avail:
            s = px[assets[k]].dropna()
            s = s[s.index <= d]
            above = s.iloc[-1] > s.iloc[-200:].mean()
            row[assets[k]] = row.get(assets[k], 0) + (1 / len(avail) if above else 0)
            row["CASH"] = row.get("CASH", 0) + (0 if above else 1 / len(avail))
            brow[assets[k]] = 1 / len(avail)
        W.append(row); B.append(brow)
    W, B = pd.DataFrame(W, index=reb).fillna(0), pd.DataFrame(B, index=reb).fillna(0)
    multi_period("D2 Multi-asset trend: hold each asset only above its 200-day avg (vs holding all)",
                 run_weights(to_daily_weights(W, r.index), r), run_weights(to_daily_weights(B, r.index), r))

    # D3 dual momentum: SPY vs EFA by 12-month return; if the winner beats T-bills hold it, else IEF
    reb = [d for d in every(allfri, 4) if d >= pd.Timestamp("2003-08-01")]
    cashidx = (1 + cash.fillna(0)).cumprod()
    W = []
    for d in reb:
        def ret12(t):
            s = px[t].dropna(); s = s[s.index <= d]
            return s.iloc[-1] / s[s.index <= d - pd.Timedelta(weeks=52)].iloc[-1] - 1
        c = cashidx[cashidx.index <= d]
        cash12 = c.iloc[-1] / c[c.index <= d - pd.Timedelta(weeks=52)].iloc[-1] - 1
        best = max(["SPY", "EFA"], key=ret12)
        W.append({"SPY": 0.0, "EFA": 0.0, "IEF": 0.0, (best if ret12(best) > cash12 else "IEF"): 1.0})
    W = pd.DataFrame(W, index=reb)
    multi_period("D3 Dual momentum: SPY or EFA, else bonds (vs SPY)", run_weights(to_daily_weights(W, r.index), r), spx)
    return pd.DataFrame(rows)


def battery_state_machine(r, lead):
    """E. The two working states combined (rules picked from the full-sample findings, so in-sample)."""
    cash = r["CASH"]
    rows = []
    for name, growth_t in [("E1 Risk OFF -> cash, Growth -> QQQ, else SPY", "QQQ"),
                           ("E2 Risk OFF -> cash, Growth -> IWF, else SPY", "IWF")]:
        w = pd.DataFrame({"SPY": ((lead != "riskoff") & (lead != "growth")).astype(float),
                          growth_t: (lead == "growth").astype(float),
                          "CASH": (lead == "riskoff").astype(float)})
        rows.append(strat_rows(name, run_weights(to_daily_weights(w, r.index), r), r["SPY"], cash))
    w = pd.DataFrame({"SPY": (lead != "riskoff").astype(float), "CASH": (lead == "riskoff").astype(float)})
    rows.append(strat_rows("E0 Risk OFF -> cash, else SPY (reference)", run_weights(to_daily_weights(w, r.index), r),
                           r["SPY"], cash))
    return pd.DataFrame(rows)


def battery_follow_or_fade(eng, sig, r, px):
    """F. Pooled across every tradeable checklist item: after a big move, does it continue or reverse?"""
    keys = [k for k in TRADE if k in eng.idx and eng.idx[k] is not None]
    out = []
    for win, h in [("1M", 4), ("3M", 13)]:
        s = sig[(sig.win == win) & sig.key.isin(keys) & (sig.status != "na")]
        s = s.drop_duplicates(["date", "key"])[["date", "key", "z"]]
        dates = sorted(s.date.unique())
        fw = {}
        for k in keys:
            m = eng.idx[k].dropna()
            pos = m.index.searchsorted(pd.DatetimeIndex(dates), side="right")
            v = np.array([m.iloc[p] if p < len(m) else np.nan for p in pos])
            fw[k] = pd.Series(np.r_[v[h:], [np.nan] * h] - v, index=dates)
        s["fwd"] = [fw[k].get(d, np.nan) for d, k in zip(s.date, s.key)]
        s = s.dropna()
        s["follow"] = np.sign(s.z) * s.fwd
        for lo, hi, lab in [(0, 0.3, "small (|z|<0.3)"), (0.3, 1, "medium (0.3-1)"), (1, 2, "large (1-2)"),
                            (2, 99, "extreme (>2)")]:
            x = s[(s.z.abs() >= lo) & (s.z.abs() < hi)]
            for per, a, b in [("2008-16", "2008-07-01", "2016-12-31"), ("2017-26", "2017-01-01", "2100-01-01")]:
                y = x[(x.date >= a) & (x.date <= b)]
                out.append(dict(window=win, move=lab, period=per, obs=len(y),
                                follow_ann=round(y.follow.mean() * (52 / h) * 100, 2),
                                follow_hit=round((y.follow > 0).mean() * 100, 1)))
    return pd.DataFrame(out)


def battery_overlay(r, lead):
    """G. The Risk OFF cash switch applied to many different holdings (added after E showed it
    improved QQQ as much as SPY). One effect tested broadly, not independent discoveries."""
    cash, ro = r["CASH"], (lead == "riskoff").astype(float)
    rows = []
    for a in ["SPY", "QQQ", "IWM", "SPHB", "EFA", "EEM", "XLK", "XLY", "XLF", "XLI", "XLB", "XLE", "XLC", "XLRE",
              "XLV", "XLP", "XLU", "SPLV", "QUAL", "COWZ", "DBC", "GLD", "HYG", "LQD", "TLT", "IEF"]:
        ov = run_weights(to_daily_weights(pd.DataFrame({a: 1 - ro, "CASH": ro}), r.index), r)
        row = dict(asset=a)
        for lab, s, e in [FULL] + HALVES:
            b = clip(r[a], s, e).dropna()
            if len(b) < 500:
                continue
            x = clip(ov, s, e).dropna()
            x = x[x.index >= b.index[0]]
            sx, sb = stats(x, cash), stats(b, cash)
            row[f"{lab} sharpe"] = f"{sb['Sharpe']:.2f}->{sx['Sharpe']:.2f}"
            row[f"{lab} cagr"] = f"{sb['CAGR']:.1f}->{sx['CAGR']:.1f}"
            row[f"{lab} maxdd"] = f"{sb['MaxDD']:.0f}->{sx['MaxDD']:.0f}"
        rows.append(row)
    return pd.DataFrame(rows)


def battery_parking(r, lead):
    """H. While Risk OFF is on, what did each place to park money return (annualized)?"""
    on = to_daily(lead == "riskoff", r.index)
    rows = []
    for a in ["CASH", "SHY", "IEF", "TLT", "LQD", "GLD", "UUP", "XLP", "XLU", "XLV", "SPLV", "QUAL", "COWZ", "SPY"]:
        row = {"park in": a}
        for lab, s, e in [FULL] + HALVES:
            onm, _, _, _ = diff_test(clip(r[a], s, e), clip(on, s, e))
            row[lab] = round(onm, 1) if np.isfinite(onm) else None
        rows.append(row)
    return pd.DataFrame(rows)


def main():
    px, fred, eng, r, lead, sig, sig3, net = setup()
    battery_overlay(r, lead).to_csv(os.path.join(OUT, "trades_G_overlay.csv"), index=False)
    battery_parking(r, lead).to_csv(os.path.join(OUT, "trades_H_parking.csv"), index=False)
    dates = list(lead.index)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    pd.set_option("display.max_rows", 400)

    A = battery_items(r, lead, sig3)
    A.to_csv(os.path.join(OUT, "trades_A_items.csv"), index=False)
    B = battery_thresholds(r, net, lead)
    C = battery_macro(px, eng, r, dates)
    D = battery_momentum(px, r)
    E = battery_state_machine(r, lead)
    F = battery_follow_or_fade(eng, sig, r, px)
    for name, df in [("B", B), ("C", C), ("D", D), ("E", E), ("F", F)]:
        df.to_csv(os.path.join(OUT, f"trades_{name}.csv"), index=False)
    return A, B, C, D, E, F


if __name__ == "__main__":
    main()
