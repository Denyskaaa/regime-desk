# Regime Desk

A free, self-updating market dashboard with three tabs:

- **Overview**: where the market sits on the Growth / Risk ON / Risk OFF / Value regime map, how many of each quadrant's ▲/▼ signals the market is confirming, a plain-English read, and a year of weekly regime history.
- **Markets**: indices, sectors (heat map), styles and factors, international, rates, bonds and credit, FX, commodities and crypto, with 1D / 1W / 1M / 3M / YTD / 1Y moves.
- **Macro**: about 60 US indicators grouped as housing, consumption, labor, production, prices, growth, and rates & the Fed, each with its latest reading, trend and five years of history.

It runs entirely on GitHub: a scheduled Action pulls data, builds JSON, and deploys the static site to GitHub Pages. There is no server and no cost.

## How it works

```
GitHub Actions (every 30 min in US trading hours)
  └─ python -m pipeline.run
       ├─ fetch.py    Yahoo Finance prices (yfinance, chart-API fallback), FRED series
       ├─ markets.py  → docs/data/market.json
       ├─ macro.py    → docs/data/macro.json   (incl. derived: real wages, LEI proxy)
       └─ regime.py   → docs/data/regime.json  (map position, checklists, narrative)
  └─ commits data/ (cache) and deploys docs/ to GitHub Pages
```

Market data refreshes every run. FRED data refreshes when the cached copy is more than 3 hours old. Treasury yields from FRED lag one business day.

## Setup (one time)

1. Push this folder to a **public** GitHub repo (for example `regime-desk`).
2. In the repo: **Settings → Pages → Build and deployment → Source: GitHub Actions**.
3. **Actions** tab → *Update data and deploy* → **Run workflow** (tick "Refresh every FRED series").
4. After 2–4 minutes the site is live at `https://<your-username>.github.io/regime-desk/`.

Optional: add a free FRED API key as a repo secret named `FRED_API_KEY` (Settings → Secrets and variables → Actions). Without it the pipeline uses FRED's public CSV download, which works but is a little slower.

## The regime model

Your chart has two axes. Both are measured from the Treasury curve:

| Axis | Measured as | Direction |
|---|---|---|
| Fed policy (vertical) | average change in 2Y and 10Y yields | yields falling = up (easier) |
| Macro sentiment (horizontal) | change in the 10Y − 2Y slope | steepening = right (stronger) |

So the curve alone lands in a quadrant: bull flattener → **Growth**, bull steepener → **Risk ON**, bear flattener → **Risk OFF**, bear steepener → **Value**. That is the round dot on the map.

Every ▲ / ▼ / ▶ label from the chart is then turned into a measurable signal (see `MEASURES` and `QUADRANTS` in `pipeline/config.py`). For example "XLY / XLP ▲" is the relative return of XLY vs XLP. Each move is scored against that measure's own normal volatility over the window: a move bigger than 0.3 standard deviations counts as up or down; smaller is flat. Each quadrant gets a score of confirming minus contradicting signals. That is the diamond on the map and the score bars.

When the curve and the cross-asset checklist point to the same quadrant, confidence is high.

Interpretation choices worth knowing:

- "H.G. / Y.C. Bonds" is read as corporate bonds (IG + HY: LQD, HYG). Its arrows match how corporate bond prices behave in each quadrant.
- "Junk stocks + high short interest" uses ARKK and micro caps vs the S&P as a proxy; there is no free most-shorted basket.
- EPS uses BEA corporate profits (quarterly, lagging). LEI is a free-data proxy built from claims, hours, orders, permits, the S&P 500, the curve and sentiment. Forward P/E has no free source and is left out.
- ISM, Chicago PMI, S&P Global PMIs, NAHB and MBA data are proprietary. Philly Fed and Empire State surveys stand in for ISM.

**This describes what markets are pricing now. It is not a forecast.**

## What the backtest found (research/, Oct 2026)

Weekly point-in-time calls, next-day execution, 5bp per trade. Curve 1990–2026; checklist 2008–2026.

- **The 3-month Risk OFF call is the one tested edge.** After it fired, the S&P returned −11.6% a year over the next 3 months (average +11.4%). Holding cash during alerts: 16.5% a year vs 12.5% buy-and-hold, Sharpe 0.94 vs 0.62. It missed the COVID crash.
- **The 1-month view is noise**: calls change every ~2 weeks and showed no forward value.
- **The yield curve alone had no timing value**, and the chart mislabels the bull steepener: stocks fell while it formed. Splitting by the S&P's 200-day average separates good cuts (+12.6% a year next 3 months) from bad cuts (+1.2%).

The site reflects this: 3 months is the default, the Risk OFF alert is the headline, and the curve is shown as context with its historical record. The figures live in `BACKTEST` and `CURVE_SHAPES` in `pipeline/config.py`; rerun `python -m research.backtest` and `python -m research.strategies` to refresh them.

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
