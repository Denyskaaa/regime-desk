"""Download raw data into data/ (cached, so a failed run keeps the last good copy).

- Market prices: Yahoo Finance via yfinance, with a direct chart-API fallback.
- Macro series: FRED. Uses the API if FRED_API_KEY is set, otherwise FRED's
  public CSV download (no key needed).
"""
import io
import os
import time
import urllib.parse
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests

from . import config

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
FRED_DIR = os.path.join(DATA, "fred")
PRICES_CSV = os.path.join(DATA, "prices.csv")
UA = {"User-Agent": "Mozilla/5.0 (regime-desk; +https://github.com)"}
BROWSER = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/126.0 Safari/537.36",
    "Accept": "text/csv,text/plain,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
FRED_START = "2010-01-01"


def set_data_dir(path):
    """Point the cache somewhere else (used for the offline sample preview)."""
    global DATA, FRED_DIR, PRICES_CSV
    DATA = path
    FRED_DIR = os.path.join(path, "fred")
    PRICES_CSV = os.path.join(path, "prices.csv")


# ---------------------------------------------------------------- prices ---

def _yf_download(tickers, period):
    import yfinance as yf  # imported here so the rest works without it
    df = yf.download(tickers, period=period, interval="1d", auto_adjust=True,
                     progress=False, threads=True, group_by="column")
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        close = df["Close"]
    else:  # single ticker
        close = df[["Close"]].rename(columns={"Close": tickers[0]})
    close.index = pd.to_datetime(close.index).tz_localize(None).normalize()
    return close


def _yahoo_chart(ticker, rng):
    url = "https://query1.finance.yahoo.com/v8/finance/chart/" + urllib.parse.quote(ticker)
    r = requests.get(url, params={"range": rng, "interval": "1d"}, headers=UA, timeout=20)
    r.raise_for_status()
    res = r.json()["chart"]["result"][0]
    ts = res.get("timestamp") or []
    ind = res["indicators"]
    vals = (ind.get("adjclose") or [{}])[0].get("adjclose") or ind["quote"][0]["close"]
    off = res["meta"].get("gmtoffset", 0)
    idx = pd.to_datetime([t + off for t in ts], unit="s").normalize()
    s = pd.Series(vals, index=idx, dtype="float64").dropna()
    return s[~s.index.duplicated(keep="last")]


def fetch_prices(period="3y"):
    """Fetch daily closes for every ticker and merge into data/prices.csv."""
    tickers = config.all_tickers()
    errors = []
    got = pd.DataFrame()
    for attempt in range(3):
        try:
            got = _yf_download(tickers, period)
            break
        except Exception as e:  # rate limits etc.
            errors.append(f"yfinance attempt {attempt + 1}: {e}")
            time.sleep(5 * (attempt + 1))

    missing = [t for t in tickers if t not in got.columns or got[t].dropna().empty]
    for t in missing:
        try:
            s = _yahoo_chart(t, period)
            if not s.empty:
                got = got.reindex(got.index.union(s.index)) if not got.empty else pd.DataFrame(index=s.index)
                got[t] = s
            time.sleep(0.4)
        except Exception as e:
            errors.append(f"{t}: {e}")

    still_missing = [t for t in tickers if t not in got.columns or got[t].dropna().empty]
    cached = load_prices()
    if got.empty:
        return cached, errors + ["no prices downloaded; kept cached copy"], still_missing

    merged = got.combine_first(cached) if not cached.empty else got
    merged = merged.sort_index()
    merged = merged[[c for c in tickers if c in merged.columns]]
    merged.index.name = "date"
    merged.to_csv(PRICES_CSV, float_format="%.6g")
    return merged, errors, still_missing


def load_prices():
    if not os.path.exists(PRICES_CSV):
        return pd.DataFrame()
    df = pd.read_csv(PRICES_CSV, index_col=0, parse_dates=True)
    return df.sort_index()


# ------------------------------------------------------------------ FRED ---

def _fred_api(sid, key):
    r = requests.get("https://api.stlouisfed.org/fred/series/observations",
                     params=dict(series_id=sid, api_key=key, file_type="json",
                                 observation_start=FRED_START), timeout=30)
    r.raise_for_status()
    obs = r.json()["observations"]
    s = pd.Series({o["date"]: o["value"] for o in obs})
    s = pd.to_numeric(s, errors="coerce").dropna()
    s.index = pd.to_datetime(s.index)
    return s


def _fred_csv(sid):
    r = requests.get("https://fred.stlouisfed.org/graph/fredgraph.csv",
                     params={"id": sid, "cosd": FRED_START}, headers=BROWSER, timeout=30)
    r.raise_for_status()
    head = r.text.lstrip()[:200]
    if head.startswith("<") or "," not in head.split("\n", 1)[0]:
        snippet = " ".join(head.split())[:160]
        raise ValueError(f"FRED sent a web page instead of CSV (HTTP {r.status_code}): {snippet}")
    df = pd.read_csv(io.StringIO(r.text), na_values=[".", ""])
    df.columns = ["date", "value"]
    s = pd.Series(df["value"].values, index=pd.to_datetime(df["date"]), dtype="float64").dropna()
    return s


# --------------------------------------------------- Treasury fallback ---
# If FRED is unreachable, rebuild the rate series the regime map needs from
# the Treasury's own daily yield-curve files (no key needed).
TSY_URL = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
           "daily-treasury-rates.csv/{y}/all")


def _tsy_year(kind, year):
    r = requests.get(TSY_URL.format(y=year), headers=BROWSER, timeout=40,
                     params={"type": kind, "field_tdr_date_value": year, "page": "", "_format": "csv"})
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    df["Date"] = pd.to_datetime(df["Date"], format="mixed")
    return df.set_index("Date").sort_index()


def fetch_treasury(years=7):
    this = datetime.now(timezone.utc).year
    nom, real = [], []
    for y in range(this - years, this + 1):
        nom.append(_tsy_year("daily_treasury_yield_curve", y))
        real.append(_tsy_year("daily_treasury_real_yield_curve", y))
        time.sleep(0.3)
    n = pd.concat(nom).sort_index()
    rl = pd.concat(real).sort_index()
    n = n[~n.index.duplicated(keep="last")]
    rl = rl[~rl.index.duplicated(keep="last")]
    col = lambda df, *names: next(df[c] for c in df.columns if c.strip().lower() in names)
    y3m, y2, y10 = col(n, "3 mo"), col(n, "2 yr"), col(n, "10 yr")
    r10 = col(rl, "10 yr")
    return {
        "DGS2": y2, "DGS10": y10, "DFII10": r10,
        "T10Y2Y": y10 - y2, "T10Y3M": y10 - y3m, "T10YIE": (y10 - r10),
    }


def fetch_fred():
    key = os.environ.get("FRED_API_KEY", "").strip()
    os.makedirs(FRED_DIR, exist_ok=True)
    errors, failed = [], []
    for sid in config.all_fred_series():
        for attempt in range(2):
            try:
                s = _fred_api(sid, key) if key else _fred_csv(sid)
                if s.empty:
                    raise ValueError("empty series")
                s.rename("value").to_frame().rename_axis("date").to_csv(
                    os.path.join(FRED_DIR, f"{sid}.csv"), float_format="%.6g")
                break
            except Exception as e:
                if attempt == 1:
                    errors.append(f"{sid}: {e}")
                    failed.append(sid)
                time.sleep(1.5)
        time.sleep(0.25)
        # If the first few series all fail the same way, FRED is blocking us; stop early
        if len(failed) >= 4 and len(failed) == len(errors) and failed == config.all_fred_series()[:len(failed)]:
            errors.append("FRED unreachable; skipped the remaining series")
            break
    tsy_needed = [k for k in ("DGS2", "DGS10", "DFII10", "T10Y2Y", "T10Y3M", "T10YIE") if k in failed
                  or not os.path.exists(os.path.join(FRED_DIR, f"{k}.csv"))]
    if tsy_needed or len(failed) >= 4:
        try:
            for sid, s in fetch_treasury().items():
                if sid in failed or sid in tsy_needed:
                    s.dropna().rename("value").to_frame().rename_axis("date").to_csv(
                        os.path.join(FRED_DIR, f"{sid}.csv"), float_format="%.6g")
            errors.append("Treasury yields filled from home.treasury.gov")
        except Exception as e:
            errors.append(f"Treasury fallback failed: {e}")
    return errors


def load_fred():
    out = {}
    if not os.path.isdir(FRED_DIR):
        return out
    for f in os.listdir(FRED_DIR):
        if f.endswith(".csv"):
            df = pd.read_csv(os.path.join(FRED_DIR, f), index_col=0, parse_dates=True)
            out[f[:-4]] = df.iloc[:, 0].astype("float64").dropna().sort_index()
    return out


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
