"""Download long history for backtesting the regime map (runs on GitHub Actions).

Writes research/data/:
  prices_max.csv.gz      daily adjusted closes, every ticker, max history
  tsy_nominal.csv.gz     Treasury par yield curve, 1990+
  tsy_real.csv.gz        Treasury real (TIPS) yield curve, 2003+
"""
import io
import os
import time
from datetime import datetime, timezone

import pandas as pd
import requests

from pipeline import config
from pipeline.fetch import BROWSER, TSY_URL, _yahoo_chart

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
EXTRA = ["^SP500TR", "QQQ", "BIL", "SPY", "GLD", "VNQ", "XLRE", "UUP"]


def prices():
    import yfinance as yf
    tickers = list(dict.fromkeys(config.all_tickers() + EXTRA))
    df = yf.download(tickers, period="max", interval="1d", auto_adjust=True,
                     progress=False, threads=True, group_by="column")
    close = df["Close"] if isinstance(df.columns, pd.MultiIndex) else df
    close.index = pd.to_datetime(close.index).tz_localize(None).normalize()
    for t in tickers:  # fill anything yfinance missed
        if t not in close.columns or close[t].dropna().empty:
            try:
                s = _yahoo_chart(t, "max")
                close = close.reindex(close.index.union(s.index))
                close[t] = s
            except Exception as e:
                print("missing", t, e)
            time.sleep(0.5)
    close = close.sort_index()
    close = close[close.index >= "1985-01-01"]
    close.index.name = "date"
    close.to_csv(os.path.join(OUT, "prices_max.csv.gz"), float_format="%.6g")
    print("prices", close.shape, {c: str(close[c].first_valid_index())[:10] for c in close.columns})


def treasury(kind, start):
    frames = []
    for y in range(start, datetime.now(timezone.utc).year + 1):
        for attempt in range(3):
            try:
                r = requests.get(TSY_URL.format(y=y), headers=BROWSER, timeout=60,
                                 params={"type": kind, "field_tdr_date_value": y, "page": "", "_format": "csv"})
                r.raise_for_status()
                d = pd.read_csv(io.StringIO(r.text))
                d["Date"] = pd.to_datetime(d["Date"], format="mixed")
                d.columns = [c.strip().upper().replace("MONTH", "MO").replace("YEAR", "YR") for c in d.columns]
                frames.append(d.set_index("DATE"))
                break
            except Exception as e:
                print(kind, y, "attempt", attempt + 1, e)
                time.sleep(3)
        time.sleep(0.4)
    df = pd.concat(frames).sort_index()
    df = df[~df.index.duplicated(keep="last")]
    df.index.name = "date"
    return df


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    nom = treasury("daily_treasury_yield_curve", 1990)
    nom.to_csv(os.path.join(OUT, "tsy_nominal.csv.gz"))
    print("nominal", nom.shape, list(nom.columns))
    real = treasury("daily_treasury_real_yield_curve", 2003)
    real.to_csv(os.path.join(OUT, "tsy_real.csv.gz"))
    print("real", real.shape, list(real.columns))
    prices()
