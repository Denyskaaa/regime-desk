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

The quadrant descriptions on the site are the chart's own claims. Only the Risk OFF call has a tested edge.

## The Risk OFF alert

The alert is **on** when Risk OFF is the outright best fit on the 3-month checklist at a Friday close (4:15pm New York; the following Friday if the market closed early). That is the rule the backtest used, trading at the next day's close. Mid-week the panel shows a **provisional** reading on the latest data; it becomes official only at Friday's close, and the history strip marks the current week as provisional until then.

When it is on, the panel shows what historically helped: moving stocks and high-yield bonds into T-bills or short Treasuries, which holdings that helped, and where money sat best while out.

## What the backtest found (research/, Oct 2026)

Weekly point-in-time calls, next-day execution, 5bp per trade. Curve 1990–2026; checklist Jul 2008 – Oct 2026, also split into 2008–16 and 2017–26 to check each result holds in both halves.

- **The 3-month Risk OFF call is the one tested edge.** After it fired, the S&P returned −10.8% a year over the next 3 months, against +12.8% on average. Holding cash during alerts: 16.4% a year vs 12.5% buy-and-hold, Sharpe 0.93 vs 0.62, worst drop −34% vs −47%, and better in both halves. 23 alerts, 13% of weeks, usually 3 weeks long. 10 were false alarms (the S&P rose +2.4% on average while out); the other 13 avoided an average −6.0%. It missed the COVID crash.
- **Growth, Risk ON and Value had no tested edge.** After those calls, the S&P and each quadrant's playbook did about the same over the next 3 months as in other weeks. Growth came closest (S&P +7.9 points a year better, t 1.8) but its own playbook did not keep paying (t 0.4).
- **The switch raised the Sharpe ratio of every stock fund tested except energy**, in both halves, from the S&P 500 and Nasdaq-100 to small caps, ex-US, emerging markets and each sector, and of high-yield and investment-grade corporate bonds. It did not reliably help energy, commodities, gold or Treasuries.
- **Where to park:** only T-bills, short Treasuries and the dollar were positive in both halves while the alert was on. Staples and utilities still lost money; long Treasuries and gold flipped sign between the halves.
- **Nothing else held up in both halves:** none of 117 single playbook-item trades; fixed Risk OFF score thresholds (all worse than "Risk OFF leads"); credit, staples-vs-discretionary, copper/gold, dollar, commodity and gold trend filters; sector and dual momentum. Moving to cash after a VIX spike helped a little in both halves (Sharpe +0.1), a third of the alert's gain.
- **The 1-month view is noise**: calls change every ~2 weeks and showed no forward value.
- **The yield curve alone had no timing value**, and the chart mislabels the bull steepener: stocks fell while it formed. Splitting by the S&P's 200-day average separates good cuts (+12.6% a year next 3 months) from bad cuts (+1.2%).

To refresh the research: run the *Research data* workflow (or `python -m research.fetch_history`), then `python -m research.backtest`, `python -m research.strategies`, `python -m research.trades` and `python -m research.site_constants`. The last one writes `research/out/site_constants.json`, which the site reads for every backtest figure it shows; the curve figures live in `CURVE_SHAPES` in `pipeline/config.py`.

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
