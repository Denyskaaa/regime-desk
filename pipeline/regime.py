"""The regime engine: your quadrant chart, turned into numbers.

Every ▲/▼ on the chart becomes a measured move over a look-back window. Each
quadrant scores (confirming - contradicting) / signals with data, and the top
score is the market's best fit. Exact ties are reported as ties.

Only market signals are scored. EPS and LEI are shown as context: they are
revised and published late, so the backtest could not use them point-in-time.
The yield curve is reported separately as context (it had no timing value).
"""
import numpy as np
import pandas as pd

from . import config

QN = {q["key"]: q["name"] for q in config.QUADRANTS}
QN["quality"] = config.QUALITY["name"]
CURVE_TO_QUAD = {(True, True): "riskon", (True, False): "growth",
                 (False, False): "riskoff", (False, True): "value"}
DEAD_BP = 3.0  # curve moves smaller than this (per month) are noise
MIN_BP = 2.0   # a single rate signal needs at least this move (per month) to count


# ------------------------------------------------------------- measures ---

def _avail(prices, tickers, min_obs=260):
    return [t for t in tickers if t in prices.columns and prices[t].notna().sum() >= min_obs]


def measure_index(key, prices, fred):
    """A cumulative series whose change over a window is the measure's move:
    log price for assets, basis points for yields."""
    m = config.MEASURES[key]
    typ = m["type"]
    if typ == "price":
        if not _avail(prices, [m["ticker"]]):
            return None
        s = prices[m["ticker"]].dropna()
        return np.log(s[s > 0])
    if typ in ("basket", "ratio"):
        num = _avail(prices, m["tickers"] if typ == "basket" else m["num"])
        den = _avail(prices, m.get("den", [])) if typ == "ratio" else []
        if not num or (typ == "ratio" and not den):
            return None
        df = prices[num + den].dropna(how="any")
        df = df[(df > 0).all(axis=1)]
        lr = np.log(df).diff().iloc[1:]
        r = lr[num].mean(axis=1)
        if den:
            r = r - lr[den].mean(axis=1)
        return r.cumsum()
    if typ == "yield":
        s = fred.get(m["series"])
        return None if s is None or s.empty else s.dropna() * 100
    return None


def window_change(m, end, offset):
    """Move over the window ending at `end`, and how unusual it is (z-score
    against the measure's own daily volatility over the past year)."""
    m = m[m.index <= end]
    if len(m) < 120:
        return None
    ms = m[m.index <= end - offset]
    if ms.empty:
        return None
    chg = float(m.iloc[-1] - ms.iloc[-1])
    n = int((m.index > ms.index[-1]).sum())
    vol = float(m.diff().iloc[-252:].std())
    z = chg / (vol * np.sqrt(max(n, 1))) if vol > 0 else 0.0
    return chg, z, m.index[-1]


def macro_signal(key, derived, fred, end):
    m = config.MEASURES[key]
    sid = m["series"]
    s = derived.get(sid) if sid in derived else fred.get(sid)
    if s is None or s.empty:
        return None
    s = s[s.index <= end].dropna()
    if len(s) < 8:
        return None
    if sid == "CP":  # corporate profits, quarterly: q/q growth vs its history
        q = (s / s.shift(1) - 1).dropna() * 100
        sd = float(q.iloc[-40:].std()) or 1.0
        return float(q.iloc[-1]), float(q.iloc[-1]) / sd, q.index[-1], "% q/q"
    v = float(s.iloc[-1])  # LEI proxy is already in z units
    return v, v, s.index[-1], "σ"


def status_for(expect, z):
    b, S = config.Z_BAND, config.Z_STRONG
    if expect == "up":
        return "match" if z > b else "against" if z < -b else "neutral"
    if expect == "down":
        return "match" if z < -b else "against" if z > b else "neutral"
    if expect == "flat":
        return "match" if abs(z) <= b else "against" if abs(z) > S else "neutral"
    if expect == "flat_down":
        return "match" if z <= b else "against" if z > S else "neutral"
    raise ValueError(expect)


def arrow(z):
    b = config.Z_BAND
    return "up" if z > b else "down" if z < -b else "flat"


# ------------------------------------------------------------ evaluation ---

class Engine:
    def __init__(self, prices, fred, derived, score_macro=False):
        self.prices, self.fred, self.derived = prices, fred, derived
        self.score_macro = score_macro
        self.idx = {}
        for k, m in config.MEASURES.items():
            if m["type"] != "macro":
                self.idx[k] = measure_index(k, prices, fred)

    def signal(self, key, label, expect, end, offset):
        m = config.MEASURES[key]
        base = dict(key=key, label=label, expect=expect, measure=m["label"], why=config.WHY.get(key, ""))
        if m["type"] == "macro":
            r = macro_signal(key, self.derived, self.fred, end)
            if r is None:
                return dict(base, status="na")
            v, z, d, unit = r
            st = status_for(expect, z)
            return dict(base, value=round(v, 2), unit=unit, z=round(z, 2), actual=arrow(z),
                        status=st if self.score_macro else "context", would=st, date=d.strftime("%Y-%m-%d"))
        s = self.idx.get(key)
        r = window_change(s, end, offset) if s is not None else None
        if r is None:
            return dict(base, status="na")
        chg, z, d = r
        if m["type"] == "yield":
            # ignore tiny rate moves even if the series is unusually calm
            if abs(chg) < MIN_BP * np.sqrt(max(getattr(offset, "months", 1) or 1, 1)):
                z = 0.0
            value, unit = round(chg, 1), "bp"
        else:
            value, unit = round((np.exp(chg) - 1) * 100, 2), "%"
        return dict(base, value=value, unit=unit, z=round(z, 2), actual=arrow(z),
                    status=status_for(expect, z), date=d.strftime("%Y-%m-%d"))

    def quadrant(self, q, end, offset):
        sigs = [self.signal(k, lab, exp, end, offset) for k, lab, exp in q["signals"]]
        live = [s for s in sigs if s["status"] not in ("na", "context")]
        n = len(live)
        match = sum(s["status"] == "match" for s in live)
        against = sum(s["status"] == "against" for s in live)
        net = (match - against) / n if n else 0.0
        return dict(key=q["key"], name=q["name"], curve=q["curve"], blurb=q["blurb"],
                    n=n, match=match, against=against, neutral=n - match - against,
                    net=round(net, 3), signals=sigs)

    def curve(self, end, offset):
        y2, y10 = self.idx.get("Y2"), self.idx.get("NY")
        if y2 is None or y10 is None:
            return None
        a, b = window_change(y2, end, offset), window_change(y10, end, offset)
        if a is None or b is None:
            return None
        d2, d10 = a[0], b[0]
        level, slope = (d2 + d10) / 2, d10 - d2
        bull, steep = level < 0, slope > 0
        dead = DEAD_BP * np.sqrt(max(getattr(offset, "months", 1) or 1, 1))
        cl, cs = bool(abs(level) >= dead), bool(abs(slope) >= dead)
        return dict(d2=round(d2, 1), d10=round(d10, 1), level=round(level, 1), slope=round(slope, 1),
                    name=("Bull" if bull else "Bear") + (" steepener" if steep else " flattener"),
                    quad=CURVE_TO_QUAD[(bull, steep)], clear=cl and cs,
                    clear_level=cl, clear_slope=cs, dead=round(float(dead), 1))

    def evaluate(self, end, offset):
        quads = [self.quadrant(q, end, offset) for q in config.QUADRANTS]
        qual = self.quadrant(config.QUALITY, end, offset)
        net = {q["key"]: q["net"] for q in quads}
        ax = (net["riskon"] + net["value"] - net["growth"] - net["riskoff"]) / 2
        ay = (net["growth"] + net["riskon"] - net["riskoff"] - net["value"]) / 2
        # best score wins; more confirming signals breaks a score tie; anything still level is a tie
        ranked = sorted(quads, key=lambda q: (q["net"], q["match"]), reverse=True)
        top = ranked[0]
        tied = [q["key"] for q in ranked if abs(q["net"] - top["net"]) < 1e-9 and q["match"] == top["match"]]
        runner = next((q for q in ranked if q["key"] not in tied), ranked[1])
        return dict(quadrants=quads, quality=qual, curve=self.curve(end, offset),
                    assets=dict(x=round(float(np.clip(ax, -1, 1)), 3), y=round(float(np.clip(ay, -1, 1)), 3),
                                leader="tie" if len(tied) > 1 else top["key"], tied=tied if len(tied) > 1 else [],
                                first=top["key"], second=runner["key"],
                                margin=round(top["net"] - runner["net"], 3)))


# ------------------------------------------------------------- narrative ---

def _bp(x):
    x = round(float(x))
    return "0bp" if x == 0 else f"{x:+.0f}bp".replace("-", "−")


def _val(s):
    v = s["value"]
    if s["unit"] == "bp":
        return _bp(v)
    if s["unit"] == "σ":
        return f"{v:+.1f}σ".replace("-", "−")
    if s["unit"] == "% q/q":
        return f"{v:+.1f}% q/q".replace("-", "−")
    return f"{v:+.1f}%".replace("-", "−")


def _list(items):
    items = list(items)
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def _pct(x, dp=1):
    return f"{x:+.{dp}f}%".replace("-", "\u2212")


def streak(trail, key):
    n = 0
    for p in reversed(trail):
        if p["asset_quad"] == key:
            n += 1
        else:
            break
    return n


def stock_trend(prices, end):
    """S&P 500 versus its 200-day average: the growth filter that splits the curve shapes."""
    col = "^GSPC" if "^GSPC" in prices.columns else "SPY"
    s = prices[col].dropna()
    s = s[s.index <= end]
    if len(s) < 200:
        return None
    sma, last = float(s.iloc[-200:].mean()), float(s.iloc[-1])
    return dict(up=bool(last > sma), pct=round((last / sma - 1) * 100, 1))


def curve_context(c, tr):
    """The 3-month curve shape, split by the stock trend, with what followed historically."""
    if not c:
        return None
    out = dict(d2=c["d2"], d10=c["d10"], clear=c["clear"], quad=c["quad"], avg=config.CURVE_AVG,
               trend=None if tr is None else ("up" if tr["up"] else "down"),
               trend_pct=None if tr is None else tr["pct"])
    if not c["clear"]:
        parallel = c["clear_level"]
        out.update(shape="Parallel move" if parallel else "No clear move", next3m=config.CURVE_FLAT[0],
                   weeks=config.CURVE_FLAT[1], parallel=parallel,
                   note="Yields moved together, so the curve's shape gives no read." if parallel
                   else "Yields barely moved, so the curve gives no read.")
        return out
    info = config.CURVE_SHAPES[c["quad"]]
    out.update(shape=info["name"], during=info["during"], note=info["note"])
    if tr is not None:
        k = "up" if tr["up"] else "down"
        out.update(next3m=info[k][0], weeks=info[k][1], label=info[f"{k}_label"])
    return out


def week_complete(last_date, now=None):
    """True once the Friday close of last_date's week has passed (4:15pm New York), so a
    Thursday-before-a-holiday week also completes."""
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("America/New_York")
        now = (now or pd.Timestamp.now(tz="UTC")).tz_convert(tz)
        friday = (pd.Timestamp(last_date) + pd.Timedelta(days=4 - pd.Timestamp(last_date).weekday())).normalize()
        cutoff = pd.Timestamp(friday.year, friday.month, friday.day, 16, 15, tz=tz)
    except Exception:  # no tz database: fall back to a fixed 4-hour offset
        now = (now or pd.Timestamp.now(tz="UTC")).tz_convert(None) - pd.Timedelta(hours=4)
        friday = (pd.Timestamp(last_date) + pd.Timedelta(days=4 - pd.Timestamp(last_date).weekday())).normalize()
        cutoff = friday + pd.Timedelta(hours=16, minutes=15)
    return bool(now >= cutoff)


def alert(trail, res, now=None):
    """Risk OFF alert: Risk OFF leads the 3-month checklist (the one call with a tested edge).
    It is official only at a week's close, as in the backtest; mid-week it is provisional."""
    nets = {q["key"]: q["net"] for q in res["quadrants"]}
    first = res["assets"]["first"]
    complete = week_complete(trail[-1]["date"], now)
    done = trail if complete else trail[:-1]          # completed weeks only
    off_on = bool(done) and done[-1]["asset_quad"] == "riskoff"
    weeks = streak(done, "riskoff") if off_on else 0
    ranked = sorted(nets, key=nets.get, reverse=True)
    hist = [dict(date=p["date"], on=p["asset_quad"] == "riskoff", tie=p["asset_quad"] == "tie",
                 net=p["nets"]["riskoff"], lead_net=max(p["nets"].values())) for p in trail]
    if not complete and hist:
        hist[-1]["provisional"] = True
    return dict(
        on=off_on, weeks=weeks, since=done[-weeks]["date"] if weeks else None,
        official_date=done[-1]["date"] if done else None,
        last_on=next((p["date"] for p in reversed(done) if p["asset_quad"] == "riskoff"), None),
        provisional=None if complete else dict(on=res["assets"]["leader"] == "riskoff",
                                               tie="riskoff" in res["assets"]["tied"], date=trail[-1]["date"]),
        net=nets["riskoff"], rank=ranked.index("riskoff") + 1, lead=first, lead_net=nets[first],
        tied=res["assets"]["tied"], gap=round(nets[first] - nets["riskoff"], 3),
        net_4w=trail[-5]["nets"]["riskoff"] if len(trail) >= 5 else None,
        hist=hist, track=config.BACKTEST,
        overlay=(config.SITE or {}).get("overlay", []), parking=(config.SITE or {}).get("parking", []),
    )


def follow_line(key):
    """What the backtest says about acting on this call (from research/site_constants.json)."""
    f = ((config.SITE or {}).get("follow") or {}).get(key)
    if not f:
        return None
    if key == "riskoff":
        t = config.BACKTEST
        return (f"**This is the one call with a tested edge.** In the 3 months after Risk OFF led, the S&P returned "
                f"{_pct(t['spx_next3m'])} a year, against {_pct(t['spx_avg3m'])} on average. Staples beat "
                f"discretionary on average, as your chart says, but staples and utilities still lost money; "
                f"T-bills and short Treasuries were the dependable place to park.")
    if abs(f["spx_t"]) >= 1.5:
        more = "more" if f["spx"] > 0 else "less"
        return (f"**No tested edge.** After a {QN[key]} call the S&P returned about {abs(f['spx']):.1f} points a "
                f"year {more} than in other weeks over the next 3 months, but not reliably enough to act on, and "
                f"the playbook itself did not keep paying. Treat it as a description, not a signal.")
    return (f"**No tested edge.** After a {QN[key]} call, its playbook and the S&P did about the same over the next "
            f"3 months as in other weeks. Treat it as a description, not a signal.")


def narrative(win, res, other, trail, macro_rows, fed, ctx):
    wl = "1-month" if win == "1M" else "3-month"
    out = []
    qmap = {q["key"]: q for q in res["quadrants"]}
    A = res["assets"]
    L = qmap[A["first"]]
    S = qmap[A["second"]]
    prov = bool(trail) and not week_complete(trail[-1]["date"])

    if win == "1M":
        out.append("**1-month view.** These calls change every two weeks on average and showed no forward "
                   "value in the backtest. Use the 3-month view for decisions.")
    if A["leader"] == "tie":
        parts = [f"{qmap[k]['name']} ({qmap[k]['match']} of {qmap[k]['n']} confirm, {qmap[k]['against']} "
                 f"contradict)" for k in A["tied"]]
        out.append(f"**Tie on the {wl} checklist:** {_list(parts)} score the same. A tie is not a call; it will "
                   f"break as prices move. Next is {S['name']}: {S['match']} of {S['n']} confirm and "
                   f"{S['against']} contradict.")
    else:
        gap = (f"ahead by {A['margin']:.2f} on score" if A["margin"] > 0
               else "level on score and ahead on confirmations")
        out.append(f"**{L['name']}** fits the {wl} checklist best: {L['match']} of {L['n']} signals confirm and "
                   f"{L['against']} contradict. Next is {S['name']}: {S['match']} of {S['n']} confirm and "
                   f"{S['against']} contradict, so {L['name']} is {gap}.")
        k = streak(trail, L["key"])
        if k >= 2:
            out.append(f"It has been the best fit for {k} straight weeks{', counting this week so far' if prov else ''}.")
        elif len(trail) >= 2:
            prev = trail[-2]["asset_quad"]
            was = "a tie" if prev == "tie" else QN.get(prev, prev)
            out.append(f"It took the lead this week{' (so far)' if prov else ''}; last week the best fit was {was}.")
    if other and other not in (A["first"], "tie") and A["leader"] != "tie":
        if win == "1M":
            out.append(f"The 3-month view says {QN[other]}, so this may be short-term noise.")
        else:
            out.append(f"The last month on its own looks more like {QN[other]}; the 1-month view is noisy, "
                       f"so watch whether that persists.")

    conf_sigs = sorted([s for s in L["signals"] if s["status"] == "match"], key=lambda s: -abs(s["z"]))[:3]
    anti = sorted([s for s in L["signals"] if s["status"] == "against"], key=lambda s: -abs(s["z"]))[:2]
    if conf_sigs:
        line = f"For {L['name']}, strongest confirmations: " + _list(f"{s['label']} {_val(s)}" for s in conf_sigs) + "."
        if anti:
            line += " Pushing against it: " + _list(f"{s['label']} {_val(s)}" for s in anti) + "."
        out.append(line)

    if win == "3M":
        if A["leader"] == "tie":
            if "riskoff" in A["tied"]:
                out.append("Only an outright Risk OFF lead triggers the alert; a tie doesn't count, as in the "
                           "backtest.")
            else:
                out.append("**No tested edge** for any of the tied calls. Treat them as descriptions, not signals.")
        else:
            fl = follow_line(L["key"])
            if fl:
                if L["key"] == "riskoff" and prov:
                    fl += (" The backtest acted only on Friday closes, so this week's reading is provisional "
                           "until Friday's close.")
                out.append(fl)

    sigs = next(q for q in config.QUADRANTS if q["key"] == L["key"])["signals"]
    favors = [lab for k_, lab, e in sigs if e == "up" and config.MEASURES[k_]["type"] not in ("yield", "macro")]
    lags = [lab for k_, lab, e in sigs if e == "down" and config.MEASURES[k_]["type"] not in ("yield", "macro")]
    play = f"Your chart's playbook for {L['name']}: favors {_list(favors)}"
    play += f"; expects weakness in {_list(lags)}." if lags else "."
    out.append(play)

    ctxs = [s for s in L["signals"] if s["status"] == "context"]
    if ctxs:
        out.append("Context, not scored: " + _list(f"{s['label']} {_val(s)}" for s in ctxs) +
                   ". EPS and LEI are revised and published late, so the backtest could not use them.")

    if ctx:
        if not ctx["clear"] and ctx.get("parallel"):
            lvl = (ctx["d2"] + ctx["d10"]) / 2
            out.append(f"Rates backdrop, context only: over 3 months yields {'rose' if lvl > 0 else 'fell'} about "
                       f"{abs(lvl):.0f}bp across the curve ({_bp(ctx['d2'])} on the 2-year, {_bp(ctx['d10'])} on "
                       f"the 10-year) with little change in slope, so there is no curve shape to read.")
        elif not ctx["clear"]:
            out.append(f"Rates backdrop: the curve barely moved over 3 months ({_bp(ctx['d2'])} on the 2-year, "
                       f"{_bp(ctx['d10'])} on the 10-year), so it adds no context right now.")
        elif ctx.get("next3m") is not None:
            pos = "above" if ctx["trend"] == "up" else "below"
            out.append(f"Rates backdrop, context only: over 3 months the curve made a **{ctx['shape'].lower()}** "
                       f"({_bp(ctx['d2'])} on the 2-year, {_bp(ctx['d10'])} on the 10-year) with the S&P "
                       f"{abs(ctx['trend_pct']):.1f}% {pos} its 200-day average. Since 1990, that combination was "
                       f"followed by {_pct(ctx['next3m'])} a year for the S&P over the next 3 months, against "
                       f"{_pct(ctx['avg'])} on average.")

    return dict(paras=out, backdrop=backdrop(macro_rows, fed), margin=A["margin"])


def backdrop(rows, fed):
    """Short macro context bullets from the Macro tab's numbers."""
    b = []
    word = {"improving": "cooling", "worsening": "heating up", "steady": "steady"}
    if fed:
        gap = fed["spread_bp"]
        if gap < -15:
            pricing = f"sits {abs(gap):.0f}bp below fed funds, so the market expects cuts"
        elif gap > 15:
            pricing = f"sits {gap:.0f}bp above fed funds, so the market expects hikes"
        else:
            pricing = "is close to fed funds, so the market expects policy to stay roughly on hold"
        b.append(f"**Fed:** funds rate {fed['ff']:.2f}%. The 2-year at {fed['y2']:.2f}% {pricing}.")
    p = rows.get("PCEPILFE") or rows.get("CPILFESL")
    if p and p["last"] is not None:
        alt = f" ({p['alt']['value']:.1f}% annualized over 3 months)" if p.get("alt") else ""
        b.append(f"**Inflation:** {p['name'].split(' (')[0]} {p['last']:.1f}% y/y{alt} vs the 2% target, "
                 f"{word.get(p['status'], 'mixed')}.")
    u, cl, sahm = rows.get("UNRATE"), rows.get("ICSA"), rows.get("SAHMREALTIME")
    if u and u["last"] is not None:
        t = f"**Labor:** unemployment {u['last']:.1f}%"
        if cl and cl.get("alt"):
            t += f", initial claims {cl['alt']['value']:.0f}k (4-week avg)"
        if sahm and sahm["last"] is not None:
            s = sahm["last"]
            t += (", Sahm rule at the recession trigger" if s >= 0.5 else
                  f", Sahm rule elevated at {s:.2f}" if s >= 0.3 else f", Sahm rule calm at {s:.2f}")
        b.append(t + ".")
    g, lei = rows.get("GDPNOW"), rows.get("LEI_PROXY")
    if g and g["last"] is not None:
        t = f"**Growth:** GDPNow {g['last']:.1f}%".replace("-", "−")
        if lei and lei["last"] is not None:
            z = f"{lei['last']:+.1f}".replace("-", "−")
            t += f", leading-index proxy {z}σ ({'improving' if lei['last'] > 0 else 'softening'})"
        b.append(t + ".")
    hy = rows.get("BAMLH0A0HYM2")
    if hy and hy["last"] is not None:
        st = {"improving": "tightening", "worsening": "widening"}.get(hy["status"], "stable")
        b.append(f"**Credit:** high-yield spread {hy['last']:.2f}pp, {st}.")
    return b


# ----------------------------------------------------------------- build ---

def weekly_dates(prices, weeks=52):
    ref = prices["SPY"].dropna() if "SPY" in prices.columns else prices.dropna(how="all").iloc[:, 0]
    wk = ref.groupby(ref.index.to_period("W")).apply(lambda s: s.index[-1])
    return list(wk.iloc[-weeks:])


def build(prices, fred, derived, macro_json):
    eng = Engine(prices, fred, derived)
    rows = {r["id"]: r for g in macro_json["groups"] for r in g["rows"]}
    end = prices["SPY"].dropna().index[-1] if "SPY" in prices.columns else prices.index[-1]

    fed = None
    if "DFF" in fred and "DGS2" in fred:
        ff, y2 = float(fred["DFF"].dropna().iloc[-1]), float(fred["DGS2"].dropna().iloc[-1])
        fed = dict(ff=ff, y2=y2, spread_bp=round((y2 - ff) * 100, 1))

    dates = weekly_dates(prices)
    results, trails = {}, {}
    for win, off_kw in config.WINDOWS.items():
        off = pd.DateOffset(**off_kw)
        res = eng.evaluate(end, off)
        trail = []
        for d in dates:
            r = eng.evaluate(d, off)
            trail.append(dict(date=d.strftime("%Y-%m-%d"), ax=r["assets"]["x"], ay=r["assets"]["y"],
                              asset_quad=r["assets"]["leader"],
                              nets={q["key"]: q["net"] for q in r["quadrants"]}))
        results[win], trails[win] = res, trail

    tr = stock_trend(prices, end)
    ctx = curve_context(results["3M"]["curve"], tr) if "3M" in results else None
    leaders = {w: r["assets"]["leader"] for w, r in results.items()}
    out = dict(asof=end.strftime("%Y-%m-%d"), fed=fed, windows={}, default_window=config.DEFAULT_WINDOW,
               trend=tr, curve_context=ctx, alert=alert(trails["3M"], results["3M"]),
               curve_table=[dict(quad=k, chart_label=QN[k], **{x: v for x, v in config.CURVE_SHAPES[k].items()})
                            for k in ("riskon", "growth", "riskoff", "value")],
               curve_avg=config.CURVE_AVG)
    for win, res in results.items():
        other = leaders["3M" if win == "1M" else "1M"]
        res["story"] = narrative(win, res, other, trails[win], rows, fed, ctx)
        res["trail"] = trails[win]
        out["windows"][win] = res
    out["band"] = dict(z=config.Z_BAND, strong=config.Z_STRONG)
    out["follow"] = (config.SITE or {}).get("follow", {})
    return out
