"""The regime engine: your quadrant chart, turned into numbers.

Two independent reads of where the market is on the map:
  1. The yield curve (2Y and 10Y moves) places a dot on the map directly.
  2. The cross-asset checklist for each quadrant counts how many of the
     chart's ▲/▼ calls the market is actually confirming.
When the two agree, the read is stronger.
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
    def __init__(self, prices, fred, derived):
        self.prices, self.fred, self.derived = prices, fred, derived
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
            return dict(base, value=round(v, 2), unit=unit, z=round(z, 2), actual=arrow(z),
                        status=status_for(expect, z), date=d.strftime("%Y-%m-%d"))
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
        live = [s for s in sigs if s["status"] != "na"]
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
        ranked = sorted(quads, key=lambda q: (q["net"], q["match"]), reverse=True)
        return dict(quadrants=quads, quality=qual, curve=self.curve(end, offset),
                    assets=dict(x=round(float(np.clip(ax, -1, 1)), 3), y=round(float(np.clip(ay, -1, 1)), 3),
                                leader=ranked[0]["key"], second=ranked[1]["key"]))


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


def strength(res):
    """How clear the lead is: descriptive, not a probability."""
    qs = sorted(res["quadrants"], key=lambda q: (q["net"], q["match"]), reverse=True)
    lead, second = qs[0], qs[1]
    margin = lead["net"] - second["net"]
    if lead["net"] >= 0.4 and margin >= 0.15:
        return "strong"
    if lead["net"] >= 0.2 and margin >= 0.05:
        return "moderate"
    return "weak"


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


def alert(trail, res):
    """Risk OFF alert: Risk OFF leads the 3-month checklist (the one call with a tested edge)."""
    nets = {q["key"]: q["net"] for q in res["quadrants"]}
    lead = res["assets"]["leader"]
    on = lead == "riskoff"
    weeks = streak(trail, "riskoff") if on else 0
    ranked = sorted(nets, key=nets.get, reverse=True)
    return dict(
        on=on, weeks=weeks, since=trail[-weeks]["date"] if weeks else None,
        last_on=next((p["date"] for p in reversed(trail) if p["asset_quad"] == "riskoff"), None),
        net=nets["riskoff"], rank=ranked.index("riskoff") + 1, lead=lead, lead_net=nets[lead],
        gap=round(nets[lead] - nets["riskoff"], 3),
        net_4w=trail[-5]["nets"]["riskoff"] if len(trail) >= 5 else None,
        hist=[dict(date=p["date"], on=p["asset_quad"] == "riskoff", net=p["nets"]["riskoff"],
                   lead_net=max(p["nets"].values())) for p in trail],
        track=config.BACKTEST,
    )


def narrative(win, res, other, trail, macro_rows, fed, ctx):
    wl = "1-month" if win == "1M" else "3-month"
    out = []
    qmap = {q["key"]: q for q in res["quadrants"]}
    L = qmap[res["assets"]["leader"]]
    S = qmap[res["assets"]["second"]]
    st = strength(res)

    if win == "1M":
        out.append("**1-month view.** These calls change every two weeks on average and showed no forward "
                   "value in the backtest. Use the 3-month view for decisions.")
    out.append(f"**{L['name']}** leads the {wl} checklist: {L['match']} of {L['n']} signals confirm and "
               f"{L['against']} contradict. {S['name']} is next at {S['match']} of {S['n']}. "
               f"That is a **{st}** lead.")

    k = streak(trail, L["key"])
    if k >= 2:
        out.append(f"It has been the best fit for {k} straight weeks.")
    elif other and other != L["key"]:
        if win == "1M":
            out.append(f"The 3-month view still says {QN[other]}, so this may be short-term noise.")
        else:
            out.append(f"The last month on its own looks more like {QN[other]}; the 1-month view is noisy, "
                       f"so watch whether that persists.")

    conf_sigs = sorted([s for s in L["signals"] if s["status"] == "match"], key=lambda s: -abs(s["z"]))[:3]
    anti = sorted([s for s in L["signals"] if s["status"] == "against"], key=lambda s: -abs(s["z"]))[:2]
    if conf_sigs:
        line = "Strongest confirmations: " + _list(f"{s['label']} {_val(s)}" for s in conf_sigs) + "."
        if anti:
            line += " Pushing against it: " + _list(f"{s['label']} {_val(s)}" for s in anti) + "."
        out.append(line)

    if st == "weak":
        Q = res["quality"]
        out.append(f"No quadrant has a clear lead, which puts the market near the center of your map. "
                   f"There, Quality tends to hold up: {Q['match']} of {Q['n']} quality signals confirm.")

    sigs = next(q for q in config.QUADRANTS if q["key"] == L["key"])["signals"]
    favors = [lab for k_, lab, e in sigs if e == "up" and config.MEASURES[k_]["type"] not in ("yield", "macro")]
    lags = [lab for k_, lab, e in sigs if e == "down" and config.MEASURES[k_]["type"] not in ("yield", "macro")]
    play = f"Your map's playbook for {L['name']}: favors {_list(favors)}"
    play += f"; expects weakness in {_list(lags)}." if lags else "."
    out.append(play)

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
                       f"followed by {ctx['next3m']:+.1f}% a year for the S&P over the next 3 months, against "
                       f"{ctx['avg']:+.1f}% on average.".replace("+-", "−").replace("-", "−")
                       .replace("200−day", "200-day").replace("2−year", "2-year").replace("10−year", "10-year"))

    return dict(paras=out, backdrop=backdrop(macro_rows, fed), strength=st)


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
    return out
