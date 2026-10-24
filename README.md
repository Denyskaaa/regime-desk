# Regime Desk

A free, self-updating market dashboard with three tabs:

- **Overview**: where the market sits on the Growth / Risk ON / Risk OFF / Value regime map, how many of each quadrant's ▲/▼ signals the market is confirming, a plain-English read, and a year of weekly regime history.
- **Markets**: indices, sectors (heat map), styles and factors, international, rates, bonds and credit, FX, commodities and crypto, with 1D / 1W / 1M / 3M / YTD / 1Y moves.
- **Macro**: about 60 US indicators grouped as housing, consumption, labor, production, prices, growth, and rates & the Fed, each with its latest reading, trend and five years of history.

It runs entirely on GitHub: a scheduled Action pulls data, builds JSON, and deploys the static site to GitHub Pages. There is no server and no cost.

## How it works

```
GitHub Actions, about every 15 minutes in US trading hours
  ├─ triggers: GitHub's schedule (:07 and :37), an external cron-job.org call (:22 and :52),
  │            one run after the close and one on Saturday
  └─ python -m pipeline.run
       ├─ fetch.py    Yahoo Finance prices (yfinance, chart-API fallback); FRED series
       │              (API key, public CSV fallback, Treasury.gov fallback for yields)
       ├─ markets.py  → docs/data/market.json
       ├─ macro.py    → docs/data/macro.json   (incl. derived: real wages, LEI proxy)
       └─ regime.py   → docs/data/regime.json  (checklists, Risk OFF alert, the read)
  └─ commits data/ (cache) and deploys docs/ to GitHub Pages
```

Market data refreshes every run. FRED data refreshes when the cached copy is more than 3 hours old. Treasury yields from FRED lag one business day.

## Setup (one time)

1. Push this folder to a **public** GitHub repo (for example `regime-desk`).
2. In the repo: **Settings → Pages → Build and deployment → Source: GitHub Actions**.
3. Add a free FRED API key as a repo secret named `FRED_API_KEY` (Settings → Secrets and variables → Actions). Without it the pipeline falls back to FRED's public CSV download, which is often blocked from GitHub's servers.
4. **Actions** tab → *Update data and deploy* → **Run workflow** (tick "Refresh every FRED series").
5. After 2–4 minutes the site is live at `https://<your-username>.github.io/regime-desk/`.

Optional, for 15-minute refreshes: GitHub's schedule alone runs about every 30 minutes and sometimes late. A free cron-job.org job can call `POST https://api.github.com/repos/<user>/regime-desk/actions/workflows/update.yml/dispatches` with body `{"ref":"main"}` at :22 and :52, using a fine-grained token limited to this repo with Actions read and write. Keep the token in cron-job.org only.

## The regime model

Every ▲ / ▼ / ▶ label from the chart is turned into a measurable signal (`MEASURES` and `QUADRANTS` in `pipeline/config.py`). For example "XLY / XLP ▲" is the relative return of XLY vs XLP. Each move is scored against that measure's own normal volatility over the window (3 months by default): a move bigger than 0.3 standard deviations counts as up or down; smaller is flat.

- **Only market signals are scored.** EPS and LEI are shown as context: they are revised and published late, so the backtest could not use them.
- Each quadrant's score is (confirming − contradicting) ÷ signals scored. The highest score is the best fit. Equal score and equal confirmations is a **tie**, and a tie is not a call.
- The map's "Now" diamond is placed from the four scores.
- The yield curve is shown separately in the Rates panel as context, with its own historical record.

Interpretation choices worth knowing:

- "H.G. / Y.C. Bonds" is read as corporate bonds (IG + HY: LQD, HYG). Its arrows match how corporate bond prices behave in each quadrant.
- "Junk stocks + high short interest" uses ARKK and micro caps vs the S&P as a proxy; there is no free most-shorted basket.
- EPS uses BEA corporate profits (quarterly, lagging). LEI is a free-data proxy built from claims, hours, orders, permits, the S&P 500, the curve and sentiment. Forward P/E has no free source and is left out.
- ISM, Chicago PMI, S&P Global PMIs, NAHB and MBA data are proprietary. Philly Fed and Empire State surveys stand in for ISM.

The quadrant descriptions on the site are the chart's own claims. None of the four calls has an edge that held in both eras (see below).

## The Risk OFF alert

Every trading day the 3-month checklist is scored. The alert is **on** when Risk OFF has the highest average score over the last 5 trading days (`ALERT_DAYS` in `pipeline/config.py`). The backtest traded at the next day's close and moved back the day after it cleared. During the trading day the latest reading is shown as provisional; it becomes official at the close.

Why an average of 5 days: with a single day's reading, the day you happened to check changed the result a lot. On 2008–2026 data the Sharpe ratio was 0.95 checking on Mondays and 0.94 on Fridays, but 0.76–0.80 on Tuesday to Thursday. The 5-day average gives 0.87–0.90 whichever day you check and 0.93 acting daily, and a one-day spike can't trigger it.

When it is on, the panel shows what helped after 2008: which holdings the switch to T-bills improved and where money sat best.

## What the backtest found (research/, Oct 2026)

Point-in-time daily scores, next-day execution, 5bp per trade, tested in two eras:

- **2008–2026, the checklist as the site computes it.** After an alert the S&P returned −9.2% a year over the next 3 months, against +12.7% on average. Holding cash during alerts: 16.4% a year vs 12.5% buy-and-hold, Sharpe 0.93 vs 0.62, worst drop −34% vs −47%. 33 alerts, 15 of them false alarms. It missed the fast crashes of 2020 and 2025.
- **1990–2008, rebuilt with stand-ins** (`research/long_test.py`): the checklist's ETFs didn't exist, so sectors and styles use Ken French's industry and size/value portfolios, SPY/IWM use Vanguard index funds, LQD/HYG use Vanguard bond funds, DBC uses the S&P GSCI, Treasury ETFs use returns implied by Treasury yields, and TIPS yields before 2003 use the Cleveland Fed's real-rate estimates. The stand-ins reproduce the real checklist after 2008 (Risk OFF score correlation 0.98, same leader on 89% of days, same alert results). **Before 2008 the alert failed:** the S&P returned +23.3% a year after alerts against +9.8% on average; cash during alerts made 7.7% a year vs 9.6% buy-and-hold (Sharpe 0.30 vs 0.40); it missed the 1990, 1998, 2000–02 and 2007–08 falls. In 1994–2006 rising real yields came with strong growth and stocks kept rising, while the 2000–02 and 2007–08 bear markets came with falling yields, which the chart calls Growth.
- **Per quadrant**, S&P over the next 3 months vs other weeks, 1990–2008 / since 2008: Growth +12 / +7 points a year (the only call that held in both eras, but trading on it lost to buy-and-hold); Risk ON −9 / +4; Risk OFF +13 / −25; Value −6 / +2.
- **Simple price rules:** going to cash when the S&P is 10%+ below its 52-week high beat buy-and-hold on risk in both eras (1990–2026 worst drop −21% vs −55%) but gave up about half a point of return a year, and its Sharpe ratio ranged from 0.52 to 0.64 depending on the day checked (buy-and-hold 0.52). Selling after a red week was the worst rule tested (0.6% a year since 2008).
- **Nothing else held up:** none of 117 single playbook-item trades; fixed score thresholds; credit, staples-vs-discretionary, copper/gold, dollar and commodity-trend filters; sector and dual momentum. The 1-month view is noise. The yield curve alone had no timing value.

To refresh the research: run the *Research data* and *Research data (long history)* workflows (or `python -m research.fetch_history` and `python -m research.fetch_long`), then `python -m research.backtest`, `python -m research.strategies`, `python -m research.trades` and `python -m research.site_constants`. The last one writes `research/out/site_constants.json`, which the site reads for every backtest figure it shows.

## Customizing

- Add or remove a ticker: edit `MARKET_GROUPS` in `pipeline/config.py`.
- Add an indicator: add a line to `MACRO_GROUPS` with its FRED series ID.
- Change a regime signal: edit `MEASURES` / `QUADRANTS`.
- Sensitivity: `Z_BAND` (default 0.3σ) in `config.py`.

## Local preview without network

```
python -m pipeline.run --sample /tmp/rd-sample   # synthetic data, shows a SAMPLE banner
python tools/preview.py preview.html             # single-file preview
```
