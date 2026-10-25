"""Download long history for substitutes of the checklist's ETFs, to test 1990-2007 (runs on GitHub Actions).

Most checklist items are ETFs that launched 1998-2011. This pulls older stand-ins:
  Yahoo        indices and Vanguard / Fidelity Select mutual funds (adjusted for distributions)
  FRED         corporate bond yields, oil, Cleveland Fed real-rate and inflation-expectation estimates,
               and monthly unemployment, credit spreads, yields and recession dates back to 1919-1948
  Ken French   daily industry, size and style portfolios (US) and developed ex-US market returns
  Bundesbank   daily London gold price, if available

Writes research/data/long/. Each source is optional: failures are logged and skipped.
"""
import gzip
import io
import os
import time
import zipfile

import pandas as pd
import requests

from pipeline.fetch import BROWSER, _yahoo_chart

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "long")

YAHOO = [
    # indices
    "^GSPC", "^SP500TR", "^RUT", "^NDX", "^IXIC", "^VIX", "^VXO", "DX-Y.NYB", "^SPGSCI", "GC=F", "CL=F", "HG=F",
    # Vanguard index and bond funds
    "VFINX", "NAESX", "VIGRX", "VIVAX", "VEIEX", "VEURX", "VPACX", "VGTSX",
    "VWEHX", "VFICX", "VWESX", "VFISX", "VFITX", "VUSTX", "VGPMX",
    # Fidelity Select sector funds
    "FDFAX", "FSRPX", "FSCPX", "FCYIX", "FSDPX", "FIDSX", "FSENX", "FSUTX", "FSPHX", "FSPTX", "FSAGX",
    # other long-lived funds
    "PCRIX", "DFSCX",
]

FRED_DAILY = ["DBAA", "DAAA", "DCOILWTICO", "DGS2", "DGS5", "DGS7", "DGS10", "DGS20", "DGS30", "DTB3",
              "VIXCLS", "VXOCLS", "DFII10", "T10YIE", "NASDAQCOM",
              "BAMLHYH0A0HYM2TRIV", "BAMLCC0A0CMTRIV", "GOLDAMGBD228NLBM", "GOLDPMGBD228NLBM", "ICSA"]
# century-long monthly series for testing rules across many recessions
FRED_MONTHLY = ["REAINTRATREARAT10Y", "EXPINF10YR", "EXPINF1YR", "MICH",
                "UNRATE", "BAA", "AAA", "GS10", "TB3MS", "USREC", "CPIAUCSL", "INDPRO", "PAYEMS"]

KF_BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
KF = {
    "kf_ind12": ["12_Industry_Portfolios_daily_CSV.zip", "12_Industry_Portfolios_Daily_CSV.zip"],
    "kf_ind49": ["49_Industry_Portfolios_daily_CSV.zip", "49_Industry_Portfolios_Daily_CSV.zip"],
    "kf_6sbm": ["6_Portfolios_2x3_daily_CSV.zip", "6_Portfolios_2x3_Daily_CSV.zip"],
    "kf_me": ["Portfolios_Formed_on_ME_daily_CSV.zip", "Portfolios_Formed_on_ME_Daily_CSV.zip"],
    "kf_ff3": ["F-F_Research_Data_Factors_daily_CSV.zip", "F-F_Research_Data_Factors_Daily_CSV.zip"],
    "kf_dev_xus": ["Developed_ex_US_3_Factors_Daily_CSV.zip", "Developed_ex_US_3_Factors_daily_CSV.zip"],
    "kf_beta": ["Portfolios_Formed_on_BETA_daily_CSV.zip", "Portfolios_Formed_on_BETA_Daily_CSV.zip"],
    "kf_var": ["Portfolios_Formed_on_VAR_daily_CSV.zip", "Portfolios_Formed_on_VAR_Daily_CSV.zip"],
    "kf_ind12_m": ["12_Industry_Portfolios_CSV.zip"],          # monthly, with firm counts and sizes
}

BBK_GOLD = "https://api.statistiken.bundesbank.de/rest/download/BBEX3/D.XAU.USD.EA.AC.C04?format=csv&lang=en"


def log(*a):
    print(*a, flush=True)


def yahoo():
    import yfinance as yf
    frames = {}
    for t in YAHOO:
        s = None
        for attempt in range(3):
            try:
                df = yf.download(t, period="max", interval="1d", auto_adjust=True, progress=False, threads=False)
                c = df["Close"]
                if isinstance(c, pd.DataFrame):
                    c = c.iloc[:, 0]
                s = c.dropna()
                if not s.empty:
                    break
            except Exception as e:
                log("yf", t, attempt + 1, e)
            time.sleep(2 * (attempt + 1))
        if s is None or s.empty:
            try:
                s = _yahoo_chart(t, "max")
            except Exception as e:
                log("chart api", t, e)
        if s is not None and not s.empty:
            s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
            frames[t] = s[~s.index.duplicated(keep="last")]
            log("yahoo", t, str(s.index[0])[:10], len(s))
        else:
            log("yahoo MISSING", t)
        time.sleep(0.7)
    df = pd.DataFrame(frames).sort_index()
    df.index.name = "date"
    df.to_csv(os.path.join(OUT, "yahoo.csv.gz"), float_format="%.6g")


def fred_series(sid):
    key = os.environ.get("FRED_API_KEY", "").strip()
    if key:
        r = requests.get("https://api.stlouisfed.org/fred/series/observations",
                         params=dict(series_id=sid, api_key=key, file_type="json"),  # full history
                         timeout=60)
        r.raise_for_status()
        obs = r.json()["observations"]
        s = pd.Series({o["date"]: o["value"] for o in obs})
    else:
        r = requests.get("https://fred.stlouisfed.org/graph/fredgraph.csv", params={"id": sid},
                         headers=BROWSER, timeout=60)
        r.raise_for_status()
        d = pd.read_csv(io.StringIO(r.text))
        s = pd.Series(d.iloc[:, 1].values, index=d.iloc[:, 0].values)
    s.index = pd.to_datetime(s.index)
    return pd.to_numeric(s, errors="coerce").dropna()


def fred():
    for name, ids in [("fred_daily", FRED_DAILY), ("fred_monthly", FRED_MONTHLY)]:
        frames = {}
        for sid in ids:
            for attempt in range(3):
                try:
                    s = fred_series(sid)
                    frames[sid] = s
                    log("fred", sid, str(s.index[0])[:10] if len(s) else "empty", len(s))
                    break
                except Exception as e:
                    log("fred", sid, attempt + 1, e)
                    time.sleep(3)
            time.sleep(0.6)
        df = pd.DataFrame(frames).sort_index()
        df.index.name = "date"
        df.to_csv(os.path.join(OUT, f"{name}.csv.gz"), float_format="%.6g")


def ken_french():
    for name, files in KF.items():
        ok = False
        for f in files:
            try:
                r = requests.get(KF_BASE + f, headers=BROWSER, timeout=120)
                r.raise_for_status()
                z = zipfile.ZipFile(io.BytesIO(r.content))
                inner = z.namelist()[0]
                raw = z.read(inner).decode("latin-1")
                with open(os.path.join(OUT, f"{name}.csv"), "w") as fh:
                    fh.write(raw)
                log("kf", name, f, len(raw))
                ok = True
                break
            except Exception as e:
                log("kf", name, f, e)
            time.sleep(1)
        if not ok:
            log("kf MISSING", name)


def gold_bbk():
    try:
        r = requests.get(BBK_GOLD, headers=BROWSER, timeout=60)
        r.raise_for_status()
        with open(os.path.join(OUT, "gold_bbk.csv"), "w") as fh:
            fh.write(r.text)
        log("bundesbank gold", len(r.text))
    except Exception as e:
        log("bundesbank gold MISSING", e)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for step in (ken_french, fred, gold_bbk, yahoo):
        try:
            step()
        except Exception as e:
            log("STEP FAILED", step.__name__, e)
    # raw Ken French text compresses well; keep the repo small
    for f in os.listdir(OUT):
        if f.endswith(".csv") and f.startswith(("kf_", "gold_")):
            p = os.path.join(OUT, f)
            with open(p, "rb") as src, gzip.open(p + ".gz", "wb") as dst:
                dst.write(src.read())
            os.remove(p)
    log("files:", sorted(os.listdir(OUT)))
