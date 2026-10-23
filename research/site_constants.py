"""Compute every backtest figure the site displays and save research/out/site_constants.json.

    python -m research.site_constants      (after research.backtest has rebuilt research/out)

The pipeline reads this file, so rerunning the research refreshes the site's
track-record numbers without editing code.
"""
import json
import os
import warnings
from datetime import date

import numpy as np
import pandas as pd

from research.backtest import (QK, daily_returns, fwd, load, nw_t, run_weights, stats,
                               to_daily_weights)
from research.trades import HALVES, clip, diff_test, to_daily, setup

warnings.filterwarnings("ignore")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
START = "2008-07-01"


def episodes(off, spx):
    rows, g = [], (off != off.shift()).cumsum()
    for _, s in off.groupby(g):
        if not s.iloc[0]:
            continue
        st, en = s.index[0], s.index[-1]
        # out of the market from the next day's close after the first alert Friday
        # to the next day's close after the first clear Friday (matches the strategy's cash days)
        i0 = spx.index.searchsorted(st, side="right")
        nxt = off.index[off.index > en]
        i1 = min(spx.index.searchsorted(nxt[0], side="right") if len(nxt) else len(spx) - 1, len(spx) - 1)
        rows.append(dict(start=str(st.date()), end=str(en.date()), weeks=int(len(s)),
                         spx=float(spx.iloc[i1] / spx.iloc[i0] - 1) * 100))
    return pd.DataFrame(rows)


def diff_t_weekly(x, mask, lag=13):
    x = x.dropna()
    m = mask.reindex(x.index).astype(float)
    X = np.column_stack([np.ones(len(x)), m.values])
    y = x.values
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
    return float(b[1]), float(b[1] / np.sqrt(V[1, 1]))


def main():
    px, fred, eng, r, lead_all, sig, sig3, net = setup()
    cash = r["CASH"]
    spx = px["^SP500TR"].dropna()
    lspx = np.log(spx)
    lead = lead_all[lead_all.index >= START]          # every figure covers the stated period only
    ro = lead == "riskoff"

    # --- the alert's track record (cash while Risk OFF leads, Friday close, next-day trade)
    ro_all = lead_all == "riskoff"
    w = pd.DataFrame({"^SP500TR": 1 - ro_all.astype(float), "CASH": ro_all.astype(float)})
    strat = run_weights(to_daily_weights(w, r.index), r)
    s_on, s_bh = stats(clip(strat, START, None), cash), stats(clip(r["^SP500TR"], START, None), cash)
    nx = fwd(lspx, list(lead.index), 63)
    ann = lambda m: (np.exp(m * 4) - 1) * 100
    comm = fwd(np.log(px["DBC"].dropna()), list(lead.index), 63)
    ep = episodes(ro, spx)
    false = ep[ep.spx > 0]
    real = ep[ep.spx <= 0]
    track = dict(
        period=f"Jul 2008 – {pd.Timestamp(lead.index[-1]).strftime('%b %Y')}",
        episodes=int(len(ep)), share_of_weeks=int(round(ro.mean() * 100)),
        median_weeks=int(ep.weeks.median()),
        spx_next3m=round(ann(nx[ro.reindex(nx.index)].mean()), 1), spx_avg3m=round(ann(nx.mean()), 1),
        commodities_next3m=round(ann(comm[ro.reindex(comm.index)].mean()), 1),
        cash_cagr=s_on["CAGR"], cash_sharpe=s_on["Sharpe"], cash_maxdd=round(s_on["MaxDD"]),
        bh_cagr=s_bh["CAGR"], bh_sharpe=s_bh["Sharpe"], bh_maxdd=round(s_bh["MaxDD"]),
        false_alarms=int(len(false)), false_cost=round(false.spx.mean(), 1),
        real_alerts=int(len(real)), real_saved=round(real.spx.mean(), 1),
        missed="the COVID crash of early 2020, which was too fast for a 3-month signal",
        recent=ep.tail(3).to_dict("records"),
    )

    # --- which holdings the switch helped (Sharpe and worst drop, buy & hold -> with switch)
    overlay = []
    for a, label in [("SPY", "S&P 500"), ("QQQ", "Nasdaq-100"), ("IWM", "Small caps"), ("EFA", "Developed ex-US"),
                     ("EEM", "Emerging markets"), ("XLK", "Tech"), ("XLF", "Financials"), ("XLP", "Staples"),
                     ("HYG", "High-yield bonds"), ("XLE", "Energy"), ("GLD", "Gold"), ("TLT", "Long Treasuries")]:
        ov = run_weights(to_daily_weights(pd.DataFrame({a: 1 - ro_all.astype(float), "CASH": ro_all.astype(float)}),
                                          r.index), r)
        row = dict(t=a, name=label)
        halves_ok = []
        for lab, s, e in [("full", START, None)] + HALVES:
            b = clip(r[a], s, e).dropna()
            if len(b) < 500:
                continue
            x = clip(ov, s, e).dropna()
            x = x[x.index >= b.index[0]]
            sx, sb = stats(x, cash), stats(b, cash)
            if lab == "full":
                row.update(sharpe_before=sb["Sharpe"], sharpe_after=sx["Sharpe"],
                           dd_before=round(sb["MaxDD"]), dd_after=round(sx["MaxDD"]))
            else:
                halves_ok.append(bool(sx["Sharpe"] > sb["Sharpe"]))
        row["helped_both_halves"] = bool(halves_ok and all(halves_ok) and len(halves_ok) == 2)
        overlay.append(row)

    # --- where money sat best while the alert was on (annualized, each half)
    on = to_daily(ro_all, r.index)
    parking = []
    for a, label in [("CASH", "T-bills (cash)"), ("SHY", "Short Treasuries (SHY)"), ("UUP", "US dollar (UUP)"),
                     ("TLT", "Long Treasuries (TLT)"), ("GLD", "Gold (GLD)"), ("XLP", "Staples (XLP)"),
                     ("XLU", "Utilities (XLU)"), ("XLV", "Health care (XLV)"), ("SPY", "S&P 500 (what you avoided)")]:
        row = dict(t=a, name=label)
        for lab, s, e in HALVES:
            onm, _, _, _ = diff_test(clip(r[a], s, e), clip(on, s, e))
            row[lab] = round(float(onm), 1) if np.isfinite(onm) else None
        parking.append(row)

    # --- does each quadrant's call carry forward? (next 3 months vs other weeks)
    from pipeline import config
    SGN = {"up": 1, "down": -1}
    dates = list(lead.index)
    inv = [k for k, m in config.MEASURES.items() if m["type"] in ("price", "basket", "ratio") and k != "VIX"]

    def step(s, ds, h):
        s = s.dropna()
        pos = s.index.searchsorted(pd.DatetimeIndex(ds), side="right")
        v = np.array([s.iloc[p] if p < len(s) else np.nan for p in pos])
        return pd.Series(np.r_[v[h:], [np.nan] * h] - v, index=ds)

    W13 = pd.DataFrame({k: step(eng.idx[k], dates, 13) for k in inv})
    spx13 = step(lspx, dates, 13)
    follow = {}
    for q in config.QUADRANTS:
        items = [(k, SGN[e]) for k, _, e in q["signals"] if e in SGN and k in inv]
        pb = sum(s * W13[k] for k, s in items) / len(items)
        m = lead == q["key"]
        dpb, tpb = diff_t_weekly(pb, m)
        dsp, tsp = diff_t_weekly(spx13, m)
        follow[q["key"]] = dict(weeks=int(m.sum()), playbook=round(dpb * 400, 1), playbook_t=round(tpb, 1),
                                spx=round(dsp * 400, 1), spx_t=round(tsp, 1),
                                tested_edge=bool(abs(tpb) >= 2 or abs(tsp) >= 2))

    out = dict(generated=str(date.today()), track=track, overlay=overlay, parking=parking, follow=follow,
               ties_3m=int((lead == "tie").sum()))
    with open(os.path.join(OUT, "site_constants.json"), "w") as f:
        json.dump(out, f, indent=1)
    return out


if __name__ == "__main__":
    o = main()
    print(json.dumps({k: v for k, v in o.items() if k != "overlay"}, indent=1)[:3000])
    for row in o["overlay"]:
        print(row)
