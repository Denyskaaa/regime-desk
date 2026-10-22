"""Synthetic data for previewing the site without network access.

Everything here is made up. The site shows a SAMPLE DATA banner whenever
it was built from this generator.
"""
import os

import numpy as np
import pandas as pd

from . import config, fetch

RNG = np.random.default_rng(7)


def _factors(idx):
    """Daily factor moves with a scripted last month (a bull steepener with
    risk-on assets) so the preview shows a realistic, coherent read."""
    n = len(idx)
    f = pd.DataFrame(index=idx)
    f["MKT"] = RNG.normal(0.0004, 0.010, n)
    f["SIZE"] = RNG.normal(0, 0.005, n)
    f["Y2"] = RNG.normal(0, 0.035, n)  # percentage points per day
    f["SLOPE"] = RNG.normal(0, 0.02, n)
    f["USD"] = RNG.normal(0, 0.004, n)
    f["COMM"] = RNG.normal(0, 0.009, n)
    last = idx >= idx[-1] - pd.DateOffset(months=1)
    k = last.sum()
    f.loc[last, "MKT"] += 0.0015
    f.loc[last, "SIZE"] += 0.0012
    f.loc[last, "Y2"] += -0.22 / k
    f.loc[last, "SLOPE"] += 0.14 / k
    f.loc[last, "USD"] += -0.0008
    f.loc[last, "COMM"] += 0.0012
    return f


# ticker: (start level, beta MKT, beta SIZE, duration, beta USD, beta COMM, idio vol)
SPEC = {
    "^GSPC": (5600, 1.0, 0, 0, 0, 0, .002), "^NDX": (19800, 1.25, 0, 0, 0, 0, .004),
    "^DJI": (41000, .9, 0, 0, 0, 0, .003), "^RUT": (2150, 1.2, 1, 0, 0, 0, .004),
    "RSP": (175, 1.0, .3, 0, 0, 0, .003), "SPY": (560, 1.0, 0, 0, 0, 0, .0005),
    "XLK": (225, 1.25, 0, 0, 0, 0, .006), "XLC": (95, 1.1, 0, 0, 0, 0, .006),
    "XLY": (210, 1.2, .2, 0, 0, 0, .006), "XLF": (48, 1.05, .3, 0, 0, 0, .006),
    "XLI": (135, 1.0, .2, 0, 0, .1, .005), "XLB": (90, 1.0, .2, 0, 0, .35, .006),
    "XLE": (88, .8, 0, 0, 0, .9, .008), "XLV": (145, .65, 0, 0, 0, 0, .005),
    "XLP": (80, .55, 0, 0, 0, 0, .004), "XLU": (78, .5, 0, 0, 0, 0, .006),
    "XLRE": (42, .9, .2, 0, 0, 0, .007),
    "IWF": (380, 1.2, 0, 0, 0, 0, .004), "IWD": (190, .9, .1, 0, 0, .1, .004),
    "SPHB": (95, 1.6, .3, 0, 0, .1, .006), "SPLV": (72, .55, 0, 0, 0, 0, .003),
    "QUAL": (180, .95, 0, 0, 0, 0, .003), "MTUM": (210, 1.1, 0, 0, 0, 0, .006),
    "COWZ": (58, .9, .1, 0, 0, .2, .005), "IWM": (215, 1.15, 1, 0, 0, 0, .004),
    "IWC": (125, 1.3, 1.3, 0, 0, 0, .006), "ARKK": (55, 1.8, .8, 0, 0, 0, .014),
    "EFA": (82, .8, 0, 0, -.5, 0, .005), "EEM": (44, .85, 0, 0, -1.0, .2, .007),
    "VGK": (70, .8, 0, 0, -.6, 0, .005), "EWJ": (72, .7, 0, 0, -.3, 0, .006),
    "FXI": (32, .7, 0, 0, -.8, 0, .012),
    "SHY": (82, 0, 0, 1.9, 0, 0, .0004), "IEF": (95, 0, 0, 7.5, 0, 0, .0010),
    "TLT": (92, 0, 0, 16.5, 0, 0, .0020), "TIP": (109, 0, 0, 6.5, 0, .05, .0015),
    "LQD": (110, .08, 0, 8.4, 0, 0, .0015), "HYG": (79, .3, .05, 3.6, 0, 0, .0015),
    "DX-Y.NYB": (101, 0, 0, 0, 1.0, 0, .001), "EURUSD=X": (1.10, 0, 0, 0, -.9, 0, .001),
    "USDJPY=X": (148, 0, 0, 0, .8, 0, .003), "GBPUSD=X": (1.30, 0, 0, 0, -.8, 0, .002),
    "USDCNY=X": (7.15, 0, 0, 0, .25, 0, .001),
    "GC=F": (2550, .05, 0, 2.0, -.6, .3, .008), "SI=F": (30, .3, 0, 1.5, -.8, .6, .015),
    "CL=F": (72, .3, 0, 0, -.3, 1.4, .015), "BZ=F": (76, .3, 0, 0, -.3, 1.4, .014),
    "NG=F": (2.8, .1, 0, 0, 0, 1.0, .03), "HG=F": (4.3, .4, 0, 0, -.5, 1.1, .009),
    "LBR=F": (560, .5, .2, 0, 0, .8, .016), "DBC": (23, .2, 0, 0, -.3, 1.0, .004),
    "BTC-USD": (62000, 2.0, .5, 0, -.5, 0, .025), "ETH-USD": (2600, 2.3, .6, 0, -.5, 0, .03),
}


def _prices(idx, f, y2, y10):
    out = {}
    for t, (lvl, bm, bs, dur, bu, bc, iv) in SPEC.items():
        r = (bm * f.MKT + bs * f.SIZE + bu * f.USD + bc * f.COMM
             - dur * y10.diff().fillna(0) / 100 + RNG.normal(0, iv, len(idx)))
        out[t] = lvl * np.exp(r.cumsum())
    vix = 16 + np.zeros(len(idx))
    for i in range(1, len(idx)):
        vix[i] = vix[i - 1] + 0.06 * (16 - vix[i - 1]) - 90 * f.MKT.iloc[i] + RNG.normal(0, .5)
    out["^VIX"] = np.clip(vix, 10, 60)
    out["^MOVE"] = np.clip(95 + 0.6 * (vix - 16) * 3 + RNG.normal(0, 2, len(idx)), 60, 180)
    out["^IRX"] = np.clip(y2 + 0.35, 0.1, None)
    out["^FVX"] = (y2 * .55 + y10 * .45)
    out["^TNX"] = y10
    out["^TYX"] = y10 + 0.45
    return pd.DataFrame(out, index=idx)


def _monthly(start, months, kind, base, mu, sd, rho=0.85):
    idx = pd.date_range(start, periods=months, freq="MS")
    if kind == "growth":
        g = RNG.normal(mu, sd, months)
        return pd.Series(base * np.exp(np.cumsum(g)), index=idx)
    x = np.zeros(months); x[0] = base
    for i in range(1, months):
        x[i] = base + rho * (x[i - 1] - base) + RNG.normal(mu, sd)
    return pd.Series(x, index=idx)


def generate(data_dir):
    fetch.set_data_dir(data_dir)
    os.makedirs(fetch.FRED_DIR, exist_ok=True)
    today = pd.Timestamp("today").normalize()
    idx = pd.bdate_range(today - pd.DateOffset(years=3), today)
    f = _factors(idx)
    y2 = 3.55 + f.Y2.cumsum()
    y10 = y2 + 0.45 + f.SLOPE.cumsum()
    prices = _prices(idx, f, y2, y10)
    prices.index.name = "date"
    prices.to_csv(fetch.PRICES_CSV, float_format="%.6g")

    def save(sid, s):
        s.dropna().rename("value").to_frame().rename_axis("date").to_csv(
            os.path.join(fetch.FRED_DIR, f"{sid}.csv"), float_format="%.6g")

    # Daily FRED series (1-day lag, like the real thing)
    lag = idx[:-1]
    dff = pd.Series(np.where(idx < idx[-1] - pd.DateOffset(months=2), 4.33, 4.08), index=idx)
    real = (y10 - 2.25 + RNG.normal(0, .02, len(idx)).cumsum() * .1)
    hy = 3.1 - 25 * f.MKT.rolling(20).sum().fillna(0) + RNG.normal(0, .03, len(idx))
    daily = {
        "DGS2": y2, "DGS10": y10, "DFF": dff, "DFII10": real, "T10YIE": y10 - real,
        "T10Y2Y": y10 - y2, "T10Y3M": y10 - (y2 + 0.35), "T10YFF": y10 - dff,
        "BAMLH0A0HYM2": hy.clip(2.4), "BAMLC0A0CM": (0.85 + (hy - 3.1) * .25).clip(.6),
        "SP500": prices["^GSPC"],
    }
    for sid, s in daily.items():
        save(sid, s.loc[lag].round(3))

    start = today - pd.DateOffset(years=12)
    m = int((today.year - start.year) * 12 + today.month - start.month) - 1
    monthly = {
        "CPIAUCSL": ("growth", 260, .0024, .0012), "CPILFESL": ("growth", 265, .0025, .0007),
        "PCEPI": ("growth", 110, .0021, .001), "PCEPILFE": ("growth", 112, .0022, .0006),
        "PPIFIS": ("growth", 130, .0020, .003), "CES0500000003": ("growth", 26, .0031, .001),
        "PAYEMS": ("growth", 150000, .0009, .0006), "ADPMNUSNERSA": ("growth", 125000, .0008, .0007),
        "RSAFS": ("growth", 520000, .0035, .006), "RSFSXMV": ("growth", 420000, .0033, .005),
        "PI": ("growth", 17000, .004, .003), "PCE": ("growth", 14000, .0042, .003),
        "TTLCONS": ("growth", 1500000, .004, .006), "CSUSHPINSA": ("growth", 190, .004, .004),
        "INDPRO": ("growth", 100, .0004, .004), "IPMAN": ("growth", 99, .0003, .005),
        "DGORDER": ("growth", 260000, .002, .03), "AMTMNO": ("growth", 520000, .002, .015),
        "BUSINV": ("growth", 2000000, .003, .003), "RETAILIMSA": ("growth", 650000, .003, .004),
        "WHLSLRIMSA": ("growth", 800000, .003, .004), "NEWORDER": ("growth", 70000, .002, .01),
        "UNRATE": ("level", 4.2, 0, .08), "SAHMREALTIME": ("level", .2, 0, .04),
        "CIVPART": ("level", 62.5, 0, .1), "AWHAETP": ("level", 34.3, 0, .08),
        "AWHMAN": ("level", 40.6, 0, .12), "JTSJOL": ("level", 7400, 0, 250),
        "JTSQUL": ("level", 3300, 0, 90), "PSAVERT": ("level", 4.6, 0, .3),
        "TOTALSA": ("level", 15.9, 0, .5), "UMCSENT": ("level", 62, 0, 3),
        "MICH": ("level", 3.3, 0, .2), "PERMIT": ("level", 1420, 0, 45),
        "HOUST": ("level", 1350, 0, 70), "HSN1F": ("level", 680, 0, 40),
        "EXHOSLUSM495S": ("level", 4.05e6, 0, 1.2e5), "GACDFSA066MSFRBPHI": ("level", 2, 0, 9),
        "GACDISA066MSFRBNY": ("level", -2, 0, 9), "TCU": ("level", 77.4, 0, .4),
    }
    for sid, (kind, base, mu, sd) in monthly.items():
        s = _monthly(start, m, kind, base, mu, sd)
        save(sid, s.round(4))

    wk = pd.date_range(today - pd.DateOffset(years=12), today - pd.Timedelta(days=4), freq="W-SAT")
    weekly = {"ICSA": (228000, 9000), "CCSA": (1.9e6, 30000), "MORTGAGE30US": (6.35, .06),
              "NFCI": (-.48, .02), "WALCL": (6.6e6, 15000), "GDPNOW": (2.1, .25)}
    for sid, (base, sd) in weekly.items():
        x = np.zeros(len(wk)); x[0] = base
        for i in range(1, len(wk)):
            x[i] = base + .9 * (x[i - 1] - base) + RNG.normal(0, sd)
        save(sid, pd.Series(x, index=wk).round(3))

    qt = pd.date_range(today - pd.DateOffset(years=12), today - pd.DateOffset(months=4), freq="QS")
    save("A191RL1Q225SBEA", pd.Series(RNG.normal(2.2, 1.3, len(qt)), index=qt).round(1))
    save("CP", pd.Series(2500 * np.exp(np.cumsum(RNG.normal(.012, .03, len(qt)))), index=qt).round(1))
    save("ECIALLCIV", pd.Series(130 * np.exp(np.cumsum(RNG.normal(.009, .002, len(qt)))), index=qt).round(2))
