"""Compute every backtest figure the site displays and save research/out/site_constants.json.

    python -m research.site_constants      (needs research/data and research/data/long)

The alert: Risk OFF has the highest 5-day average score on the 3-month checklist at a day's
close; the backtest trades at the next day's close and moves back after the first close where
it no longer leads. Two eras, tested separately:
  post  Jul 2008 - today   the checklist as the site computes it (real ETFs)
  pre   Jul 1990 - Jun 2008  rebuilt with long-history stand-ins (research/long_test.py)
The pipeline reads this file, so rerunning it refreshes the site without editing code.
"""
import json
import os
import warnings
from datetime import date

import numpy as np
import pandas as pd

from pipeline import config, regime
from research import long_test as lt
from research.backtest import daily_returns, fwd, load, run_weights, stats, to_daily_weights
from research.trades import HALVES, clip, diff_test, to_daily

warnings.filterwarnings("ignore")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
ERAS = {"post": ("2008-07-01", None), "pre": ("1990-07-01", "2008-06-30")}
SPX = "^SP500TR"


def nw_diff(x, mask, lag):
    """Mean of x when mask is on minus when off, with a Newey-West t-stat."""
    x = x.dropna()
    m = mask.reindex(x.index).fillna(False).astype(float)
    X = np.column_stack([np.ones(len(x)), m.values])
    y = x.values
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ b
    n = len(y)
    S = (X * e[:, None]).T @ (X * e[:, None]) / n
    for L in range(1, lag + 1):
        G = (X[L:] * e[L:, None]).T @ (X[:-L] * e[:-L, None]) / n
        S += (1 - L / (lag + 1)) * (G + G.T)
    Xi = np.linalg.inv(X.T @ X / n)
    V = Xi @ S @ Xi / n
    return float(b[1]), float(b[1] / np.sqrt(V[1, 1]))


def cash_switch(on, r):
    on = on.dropna().astype(float)
    w = to_daily_weights(pd.DataFrame({SPX: 1 - on, "CASH": on}), r.index)
    return run_weights(w, r), w["CASH"].fillna(0)


def episodes(wc, sp):
    rows = []
    for _, g in wc.groupby((wc != wc.shift()).cumsum()):
        if g.iloc[0] == 1:
            rows.append(dict(start=str(g.index[0].date()), end=str(g.index[-1].date()), days=int(len(g)),
                             spx=round(float((1 + sp.reindex(g.index).fillna(0)).prod() - 1) * 100, 1)))
    return pd.DataFrame(rows)


ann = lambda m: (np.exp(m * 4) - 1) * 100


def track(on, r, era, label):
    a, b = era
    spx = r[SPX].dropna()
    x, wc = cash_switch(on, r)
    s_on, s_bh = stats(clip(x, a, b), r["CASH"]), stats(clip(r[SPX], a, b), r["CASH"])
    days = clip(on, a, b).index
    f = fwd(np.log((1 + spx.fillna(0)).cumprod()), list(days), 63)
    m = on.reindex(f.index).fillna(False)
    d, t = nw_diff(f, m, 63)
    ep = episodes(clip(wc, a, b), r[SPX])
    false, real = ep[ep.spx > 0], ep[ep.spx <= 0]
    return dict(
        label=label, period=f"{pd.Timestamp(days[0]):%b %Y} – {pd.Timestamp(days[-1]):%b %Y}",
        episodes=int(len(ep)), share_of_days=int(round(m.mean() * 100)),
        median_weeks=max(1, int(round(ep.days.median() / 5))) if len(ep) else 0,
        spx_next3m=round(ann(f[m].mean()), 1), spx_avg3m=round(ann(f.mean()), 1), gap=round(d * 400, 1), gap_t=round(t, 1),
        cash_cagr=s_on["CAGR"], cash_sharpe=s_on["Sharpe"], cash_maxdd=round(s_on["MaxDD"]),
        bh_cagr=s_bh["CAGR"], bh_sharpe=s_bh["Sharpe"], bh_maxdd=round(s_bh["MaxDD"]),
        false_alarms=int(len(false)), false_cost=round(false.spx.mean(), 1) if len(false) else 0,
        real_alerts=int(len(real)), real_saved=round(real.spx.mean(), 1) if len(real) else 0,
        recent=ep.tail(3).to_dict("records"),
    ), ep


def main():
    days_n = config.ALERT_DAYS

    # ---- post-2008: the checklist as the site computes it
    px, fred = load()
    config.MEASURES["CULU"] = dict(type="price", ticker="HG=F", label="Copper")  # lumber futures start 2022
    eng = regime.Engine(px, fred, {})
    r = daily_returns(px, fred)
    d_post = r.index[r.index >= "2008-01-01"]
    nets_post, matches_post = regime.daily_nets(eng, d_post)
    avg_post, lead5_post, _ = regime.avg_leaders(nets_post, days_n)
    alert_post = lead5_post == "riskoff"

    # ---- 1990-2008: stand-ins
    pxl, fredl, px0, fred0 = lt.load_long("B")
    engl = lt.engine(pxl, fredl, subs=True)
    d_pre = r.index[(r.index >= "1990-01-01") & (r.index <= "2008-06-30")]
    sc_pre, _ = lt.scores(engl, d_pre)
    nets_pre = pd.DataFrame({k: v.net for k, v in sc_pre.items()})
    avg_pre, lead5_pre, _ = regime.avg_leaders(nets_pre, days_n)
    alert_pre = lead5_pre == "riskoff"

    tr_post, ep_post = track(alert_post, r, ERAS["post"], "2008–2026 (real ETFs)")
    tr_pre, ep_pre = track(alert_pre, r, ERAS["pre"], "1990–2008 (rebuilt with stand-ins)")
    tr_post["missed"] = "the fast crashes of early 2020 and spring 2025"
    tr_pre["missed"] = "the 1990, 1998, 2000–02 and 2007–08 falls"

    # ---- weekday sensitivity of the old one-day rule vs the 5-day average (post-2008)
    one_day = regime.avg_leaders(nets_post, 1)[1] == "riskoff"
    wk = {}
    for nm, sig in [("one_day", one_day), ("avg5", alert_post)]:
        row = {}
        for k, dn in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri"]):
            x, _ = cash_switch(sig.reindex(d_post[d_post.dayofweek == k]), r)
            row[dn] = stats(clip(x, *ERAS["post"]), r["CASH"])["Sharpe"]
        x, _ = cash_switch(sig, r)
        row["daily"] = stats(clip(x, *ERAS["post"]), r["CASH"])["Sharpe"]
        wk[nm] = row

    # ---- which holdings the switch helped, and where money sat best (post-2008 only)
    cash = r["CASH"]
    overlay = []
    for a, label in [("SPY", "S&P 500"), ("QQQ", "Nasdaq-100"), ("IWM", "Small caps"), ("EFA", "Developed ex-US"),
                     ("EEM", "Emerging markets"), ("XLK", "Tech"), ("XLF", "Financials"), ("XLP", "Staples"),
                     ("HYG", "High-yield bonds"), ("XLE", "Energy"), ("GLD", "Gold"), ("TLT", "Long Treasuries")]:
        on = alert_post.astype(float)
        ov = run_weights(to_daily_weights(pd.DataFrame({a: 1 - on, "CASH": on}), r.index), r)
        row = dict(t=a, name=label)
        halves_ok = []
        for lab, s, e in [("full", "2008-07-01", None)] + HALVES:
            bb = clip(r[a], s, e).dropna()
            if len(bb) < 500:
                continue
            xx = clip(ov, s, e).dropna()
            xx = xx[xx.index >= bb.index[0]]
            sx, sb = stats(xx, cash), stats(bb, cash)
            if lab == "full":
                row.update(sharpe_before=sb["Sharpe"], sharpe_after=sx["Sharpe"],
                           dd_before=round(sb["MaxDD"]), dd_after=round(sx["MaxDD"]))
            else:
                halves_ok.append(bool(sx["Sharpe"] > sb["Sharpe"]))
        row["helped_both_halves"] = bool(len(halves_ok) == 2 and all(halves_ok))
        overlay.append(row)
    on_d = to_daily(alert_post, r.index)
    parking = []
    for a, label in [("CASH", "T-bills (cash)"), ("SHY", "Short Treasuries (SHY)"), ("UUP", "US dollar (UUP)"),
                     ("TLT", "Long Treasuries (TLT)"), ("GLD", "Gold (GLD)"), ("XLP", "Staples (XLP)"),
                     ("XLU", "Utilities (XLU)"), ("XLV", "Health care (XLV)"), ("SPY", "S&P 500 (what you avoided)")]:
        row = dict(t=a, name=label)
        for lab, s, e in HALVES:
            onm, _, _, _ = diff_test(clip(r[a], s, e), clip(on_d, s, e))
            row[lab] = round(float(onm), 1) if np.isfinite(onm) else None
        parking.append(row)

    # ---- does each quadrant call carry forward? S&P over the next 3 months, both eras (daily, one-day leader)
    lead1 = {"post": regime.avg_leaders(nets_post, 1)[1], "pre": regime.avg_leaders(nets_pre, 1)[1]}
    spx_lv = np.log((1 + r[SPX].fillna(0)).cumprod())
    follow = {}
    for q in config.QUADRANTS:
        follow[q["key"]] = {}
        for era, (a, b) in ERAS.items():
            L = clip(lead1[era], a, b)
            f = fwd(spx_lv, list(L.index), 63)
            m = L.reindex(f.index) == q["key"]
            d, t = nw_diff(f, m, 63)
            follow[q["key"]][era] = dict(days=int(m.sum()), spx=round(d * 400, 1), spx_t=round(t, 1))
        p, o = follow[q["key"]]["pre"], follow[q["key"]]["post"]
        follow[q["key"]]["consistent"] = bool(np.sign(p["spx"]) == np.sign(o["spx"]) and min(abs(p["spx_t"]), abs(o["spx_t"])) >= 1.5)

    out = dict(generated=str(date.today()), rule=f"Risk OFF has the highest {days_n}-day average score",
               track=tr_post, track_pre=tr_pre, weekday=wk, overlay=overlay, parking=parking, follow=follow)
    with open(os.path.join(OUT, "site_constants.json"), "w") as f:
        json.dump(out, f, indent=1)
    ep_post.to_csv(os.path.join(OUT, "alert_episodes_post.csv"), index=False)
    ep_pre.to_csv(os.path.join(OUT, "alert_episodes_pre.csv"), index=False)
    return out


if __name__ == "__main__":
    o = main()
    print(json.dumps({k: v for k, v in o.items() if k not in ("overlay", "parking")}, indent=1)[:6000])
    for row in o["overlay"]:
        print(row)
    for row in o["parking"]:
        print(row)
