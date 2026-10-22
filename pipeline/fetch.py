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
                     params={"id": sid, "cosd": FRED_START}, headers=UA, timeout=30)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text), na_values=[".", ""])
    df.columns = ["date", "value"]
    s = pd.Series(df["value"].values, index=pd.to_datetime(df["date"]), dtype="float64").dropna()
    return s


def fetch_fred():
    key = os.environ.get("FRED_API_KEY", "").strip()
    os.makedirs(FRED_DIR, exist_ok=True)
    errors = []
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
                time.sleep(1.5)
        time.sleep(0.25)
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
