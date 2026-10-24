"""What Regime Desk tracks: market tickers, FRED series, and the regime map.

Everything the site shows is defined here, so adding a ticker or an indicator
means adding one line to this file.
"""

# ---------------------------------------------------------------------------
# Markets tab — Yahoo Finance symbols
# kind: "price" (show % moves) or "yield" (show bp moves)
# ---------------------------------------------------------------------------
MARKET_GROUPS = [
    ("US equities", [
        ("^GSPC", "S&P 500"),
        ("^NDX", "Nasdaq 100"),
        ("^DJI", "Dow Jones"),
        ("^RUT", "Russell 2000"),
        ("RSP", "S&P 500 equal weight"),
    ]),
    ("Volatility", [
        ("^VIX", "VIX (equity vol)"),
        ("^MOVE", "MOVE (bond vol)"),
    ]),
    ("Sectors", [
        ("XLK", "Technology"),
        ("XLC", "Communication"),
        ("XLY", "Consumer discretionary"),
        ("XLF", "Financials"),
        ("XLI", "Industrials"),
        ("XLB", "Materials"),
        ("XLE", "Energy"),
        ("XLV", "Health care"),
        ("XLP", "Consumer staples"),
        ("XLU", "Utilities"),
        ("XLRE", "Real estate"),
    ]),
    ("Styles & factors", [
        ("IWF", "Growth (R1000)"),
        ("IWD", "Value (R1000)"),
        ("SPHB", "High beta"),
        ("SPLV", "Low volatility"),
        ("QUAL", "Quality"),
        ("MTUM", "Momentum"),
        ("COWZ", "High free cash flow"),
        ("IWM", "Small caps"),
        ("IWC", "Micro caps"),
        ("ARKK", "Speculative growth"),
    ]),
    ("International", [
        ("EFA", "Developed ex-US"),
        ("EEM", "Emerging markets"),
        ("VGK", "Europe"),
        ("EWJ", "Japan"),
        ("FXI", "China large caps"),
    ]),
    ("Rates", [
        ("^IRX", "3M T-bill", "yield"),
        ("^FVX", "5Y Treasury", "yield"),
        ("^TNX", "10Y Treasury", "yield"),
        ("^TYX", "30Y Treasury", "yield"),
    ]),
    ("Bonds & credit", [
        ("SHY", "1-3Y Treasuries"),
        ("IEF", "7-10Y Treasuries"),
        ("TLT", "20Y+ Treasuries"),
        ("TIP", "TIPS"),
        ("LQD", "IG corporates"),
        ("HYG", "High yield"),
    ]),
    ("Dollar & FX", [
        ("DX-Y.NYB", "Dollar index (DXY)"),
        ("EURUSD=X", "EUR/USD"),
        ("USDJPY=X", "USD/JPY"),
        ("GBPUSD=X", "GBP/USD"),
        ("USDCNY=X", "USD/CNY"),
    ]),
    ("Commodities", [
        ("GC=F", "Gold"),
        ("SI=F", "Silver"),
        ("CL=F", "WTI crude"),
        ("BZ=F", "Brent crude"),
        ("NG=F", "Natural gas"),
        ("HG=F", "Copper"),
        ("LBR=F", "Lumber"),
        ("DBC", "Broad commodities"),
    ]),
    ("Crypto", [
        ("BTC-USD", "Bitcoin"),
        ("ETH-USD", "Ether"),
    ]),
]

# FRED daily series also shown on the Markets tab (prior close, 1-day lag)
MARKET_FRED_RATES = [
    ("DGS2", "2Y Treasury (FRED)"),
    ("DFII10", "10Y real yield (TIPS)"),
    ("T10YIE", "10Y breakeven inflation"),
    ("T10Y2Y", "10Y minus 2Y spread"),
]

# Extra tickers the regime engine needs that are not displayed
EXTRA_TICKERS = ["SPY"]


def all_tickers():
    seen, out = set(), []
    for _, items in MARKET_GROUPS:
        for it in items:
            if it[0] not in seen:
                seen.add(it[0]); out.append(it[0])
    for t in EXTRA_TICKERS:
        if t not in seen:
            seen.add(t); out.append(t)
    return out


# ---------------------------------------------------------------------------
# Macro tab — FRED series
# transform: level | yoy (% vs 12 months ago) | mom (% vs prior period)
#            | diff (change vs prior period) | qoq_ann (already annualized)
# good: "up" / "down" / None (neutral — just show rising/falling)
# ---------------------------------------------------------------------------
MACRO_GROUPS = [
    ("Rates & the Fed", "Where policy is and what the bond market expects next", [
        dict(id="DFF", name="Fed funds rate (effective)", transform="level", unit="%", dp=2, good=None),
        dict(id="DGS2", name="2Y Treasury yield", transform="level", unit="%", dp=2, good=None),
        dict(id="DGS10", name="10Y Treasury yield", transform="level", unit="%", dp=2, good=None),
        dict(id="T10Y2Y", name="10Y minus 2Y curve", transform="level", unit="pp", dp=2, good=None),
        dict(id="T10Y3M", name="10Y minus 3M curve", transform="level", unit="pp", dp=2, good=None),
        dict(id="DFII10", name="10Y real yield (TIPS)", transform="level", unit="%", dp=2, good=None),
        dict(id="BAMLH0A0HYM2", name="High-yield credit spread", transform="level", unit="pp", dp=2, good="down"),
        dict(id="BAMLC0A0CM", name="Investment-grade credit spread", transform="level", unit="pp", dp=2, good="down"),
        dict(id="NFCI", name="Chicago Fed financial conditions", transform="level", unit="idx", dp=2, good="down",
             note="Below 0 = looser than average"),
        dict(id="WALCL", name="Fed balance sheet", transform="level", unit="$tn", dp=2, good=None, scale=1e-6),
    ]),
    ("Growth", "Output and the outlook", [
        dict(id="GDPNOW", name="GDPNow (Atlanta Fed nowcast)", transform="level", unit="%", dp=1, good="up"),
        dict(id="A191RL1Q225SBEA", name="Real GDP growth", transform="level", unit="% ann.", dp=1, good="up"),
        dict(id="CP", name="Corporate profits (after tax)", transform="yoy", unit="% y/y", dp=1, good="up"),
        dict(id="LEI_PROXY", name="Leading index (free-data proxy)", transform="level", unit="z", dp=2, good="up",
             note="Average of claims, hours, orders, permits, S&P 500 and the curve. Conference Board LEI is paid."),
    ]),
    ("Prices", "Inflation, from the data and from markets", [
        dict(id="CPIAUCSL", name="CPI", transform="yoy", unit="% y/y", dp=1, good="down", alt="ann3m"),
        dict(id="CPILFESL", name="Core CPI", transform="yoy", unit="% y/y", dp=1, good="down", alt="ann3m"),
        dict(id="PCEPI", name="PCE price index", transform="yoy", unit="% y/y", dp=1, good="down"),
        dict(id="PCEPILFE", name="Core PCE (Fed target)", transform="yoy", unit="% y/y", dp=1, good="down", alt="ann3m"),
        dict(id="PPIFIS", name="PPI final demand", transform="yoy", unit="% y/y", dp=1, good="down"),
        dict(id="ECIALLCIV", name="Employment cost index", transform="yoy", unit="% y/y", dp=1, good=None),
        dict(id="REAL_AHE", name="Real hourly earnings", transform="level", unit="% y/y", dp=1, good="up",
             note="Hourly earnings growth minus CPI inflation"),
        dict(id="T10YIE", name="10Y breakeven inflation", transform="level", unit="%", dp=2, good=None),
        dict(id="MICH", name="Consumers' 1Y inflation expectation", transform="level", unit="%", dp=1, good="down"),
    ]),
    ("Labor market", "Hiring, layoffs and wages", [
        dict(id="PAYEMS", name="Nonfarm payrolls", transform="diff", unit="k m/m", dp=0, good="up"),
        dict(id="UNRATE", name="Unemployment rate", transform="level", unit="%", dp=1, good="down"),
        dict(id="SAHMREALTIME", name="Sahm rule recession gauge", transform="level", unit="pp", dp=2, good="down",
             note="0.50 or higher has marked the start of every recession since 1970"),
        dict(id="ICSA", name="Initial jobless claims", transform="level", unit="k", dp=0, good="down", scale=1e-3, ma=4),
        dict(id="CCSA", name="Continuing jobless claims", transform="level", unit="k", dp=0, good="down", scale=1e-3),
        dict(id="CIVPART", name="Participation rate", transform="level", unit="%", dp=1, good="up"),
        dict(id="CES0500000003", name="Average hourly earnings", transform="yoy", unit="% y/y", dp=1, good=None),
        dict(id="AWHAETP", name="Average weekly hours", transform="level", unit="hrs", dp=1, good="up"),
        dict(id="JTSJOL", name="JOLTS job openings", transform="level", unit="m", dp=2, good="up", scale=1e-3),
        dict(id="JTSQUL", name="JOLTS quits", transform="level", unit="m", dp=2, good="up", scale=1e-3),
        dict(id="ADPMNUSNERSA", name="ADP private employment", transform="diff", unit="k m/m", dp=0, good="up", scale=1e-3),
    ]),
    ("Consumption", "Household income and spending", [
        dict(id="RSAFS", name="Retail sales", transform="mom", unit="% m/m", dp=1, good="up"),
        dict(id="RSFSXMV", name="Retail sales ex autos", transform="mom", unit="% m/m", dp=1, good="up"),
        dict(id="PI", name="Personal income", transform="mom", unit="% m/m", dp=1, good="up"),
        dict(id="PCE", name="Personal spending", transform="mom", unit="% m/m", dp=1, good="up"),
        dict(id="PSAVERT", name="Personal saving rate", transform="level", unit="%", dp=1, good=None),
        dict(id="TOTALSA", name="Vehicle sales", transform="level", unit="m ann.", dp=1, good="up"),
        dict(id="UMCSENT", name="Consumer sentiment (UMich)", transform="level", unit="idx", dp=1, good="up"),
    ]),
    ("Housing", "The most rate-sensitive corner of the economy", [
        dict(id="MORTGAGE30US", name="30Y mortgage rate", transform="level", unit="%", dp=2, good="down"),
        dict(id="PERMIT", name="Building permits", transform="level", unit="k ann.", dp=0, good="up"),
        dict(id="HOUST", name="Housing starts", transform="level", unit="k ann.", dp=0, good="up"),
        dict(id="HSN1F", name="New home sales", transform="level", unit="k ann.", dp=0, good="up"),
        dict(id="EXHOSLUSM495S", name="Existing home sales", transform="level", unit="m ann.", dp=2, good="up", scale=1e-6),
        dict(id="TTLCONS", name="Construction spending", transform="mom", unit="% m/m", dp=1, good="up"),
        dict(id="CSUSHPINSA", name="Home prices (Case-Shiller)", transform="yoy", unit="% y/y", dp=1, good=None),
    ]),
    ("Production", "Factories, orders and inventories", [
        dict(id="GACDFSA066MSFRBPHI", name="Philly Fed manufacturing", transform="level", unit="idx", dp=1, good="up",
             note="Free stand-in for ISM manufacturing. Above 0 = expanding"),
        dict(id="GACDISA066MSFRBNY", name="Empire State manufacturing", transform="level", unit="idx", dp=1, good="up",
             note="Above 0 = expanding"),
        dict(id="INDPRO", name="Industrial production", transform="yoy", unit="% y/y", dp=1, good="up"),
        dict(id="IPMAN", name="Manufacturing production", transform="yoy", unit="% y/y", dp=1, good="up"),
        dict(id="TCU", name="Capacity utilization", transform="level", unit="%", dp=1, good="up"),
        dict(id="DGORDER", name="Durable goods orders", transform="mom", unit="% m/m", dp=1, good="up"),
        dict(id="AMTMNO", name="Factory orders", transform="mom", unit="% m/m", dp=1, good="up"),
        dict(id="BUSINV", name="Business inventories", transform="mom", unit="% m/m", dp=1, good=None),
        dict(id="RETAILIMSA", name="Retail inventories", transform="mom", unit="% m/m", dp=1, good=None),
        dict(id="WHLSLRIMSA", name="Wholesale inventories", transform="mom", unit="% m/m", dp=1, good=None),
    ]),
]

# Indicators from the slide that have no free source
NOT_FREE = {
    "Housing": ["NAHB Housing Market Index", "MBA mortgage applications"],
    "Production": ["ISM manufacturing & services PMIs", "Chicago PMI", "S&P Global PMIs"],
    "Growth": ["Conference Board LEI", "Forward EPS and forward P/E"],
}

# FRED series used only for derived indicators (not shown as rows)
HELPER_SERIES = ["AWHMAN", "NEWORDER", "T10YFF", "SP500"]

# Derived (computed) indicators and what they need
DERIVED = {
    "REAL_AHE": ["CES0500000003", "CPIAUCSL"],
    "LEI_PROXY": ["AWHMAN", "ICSA", "NEWORDER", "PERMIT", "SP500", "T10YFF", "UMCSENT"],
}


def all_fred_series():
    ids = []
    for _, _, rows in MACRO_GROUPS:
        for r in rows:
            if r["id"] in DERIVED:
                ids.extend(DERIVED[r["id"]])
            else:
                ids.append(r["id"])
    ids += [s for s, _ in MARKET_FRED_RATES] + HELPER_SERIES
    seen, out = set(), []
    for s in ids:
        if s not in seen and s not in DERIVED:
            seen.add(s); out.append(s)
    return out


# ---------------------------------------------------------------------------
# Regime map — your quadrant chart, made measurable
#
# Axes (as on the chart):
#   vertical   = Fed policy: easing (+, up) vs tightening (-, down).
#                Measured as the average move in 2Y and 10Y yields, sign flipped:
#                yields falling = market pricing easier policy = "bull".
#   horizontal = Macro sentiment: + right, - left.
#                Measured as the change in the 10Y-2Y slope: steepening = right.
#
# So the yield curve alone places us in a quadrant:
#   bull flattener -> Growth   (top-left)     bull steepener -> Risk ON (top-right)
#   bear flattener -> Risk OFF (bottom-left)  bear steepener -> Value   (bottom-right)
#
# The cross-asset checklists below then confirm or contradict that read.
# ---------------------------------------------------------------------------

# Measures: how each chart label is turned into a number.
#   price  — log return of one ticker
#   basket — average log return of several tickers
#   ratio  — basket(num) minus basket(den), i.e. relative performance
#   yield  — change in a FRED rate, in basis points
#   macro  — latest reading of a derived macro series
MEASURES = {
    "NY":      dict(type="yield", series="DGS10", label="10Y nominal yield"),
    "RY":      dict(type="yield", series="DFII10", label="10Y real yield (TIPS)"),
    "IE":      dict(type="yield", series="T10YIE", label="10Y breakeven inflation"),
    "Y2":      dict(type="yield", series="DGS2", label="2Y yield"),
    "HBLB":    dict(type="ratio", num=["SPHB"], den=["SPLV"], label="High beta vs low vol (SPHB/SPLV)"),
    "HB":      dict(type="price", ticker="SPHB", label="High-beta stocks (SPHB)"),
    "DMEM":    dict(type="ratio", num=["EFA"], den=["EEM"], label="Developed vs emerging (EFA/EEM)"),
    "EMDM":    dict(type="ratio", num=["EEM"], den=["EFA"], label="Emerging vs developed (EEM/EFA)"),
    "EM":      dict(type="price", ticker="EEM", label="Emerging markets (EEM)"),
    "DM":      dict(type="price", ticker="EFA", label="Developed ex-US (EFA)"),
    "GOLD":    dict(type="price", ticker="GC=F", label="Gold"),
    "OIL":     dict(type="price", ticker="CL=F", label="WTI crude"),
    "COMM":    dict(type="price", ticker="DBC", label="Broad commodities (DBC)"),
    "HPE":     dict(type="ratio", num=["IWF"], den=["IWD"], label="Growth vs value (IWF/IWD)"),
    "LPE":     dict(type="ratio", num=["IWD"], den=["IWF"], label="Value vs growth (IWD/IWF)"),
    "LCSC":    dict(type="ratio", num=["SPY"], den=["IWM"], label="Large vs small caps (SPY/IWM)"),
    "SCLC":    dict(type="ratio", num=["IWM"], den=["SPY"], label="Small vs large caps (IWM/SPY)"),
    "SMALL":   dict(type="ratio", num=["IWM", "IWC"], den=["SPY"], label="Small + micro vs S&P (IWM, IWC / SPY)"),
    "LARGE":   dict(type="price", ticker="SPY", label="Large caps (SPY)"),
    "LMGB":    dict(type="basket", tickers=["TLT", "IEF"], label="Long + medium Treasuries (TLT, IEF)"),
    "SGB":     dict(type="price", ticker="SHY", label="Short Treasuries (SHY)"),
    "CORP":    dict(type="basket", tickers=["LQD", "HYG"], label="Corporate bonds, IG + HY (LQD, HYG)"),
    "XLKXLB":  dict(type="ratio", num=["XLK"], den=["XLB"], label="Tech vs materials (XLK/XLB)"),
    "PTECH":   dict(type="ratio", num=["^NDX"], den=["^GSPC"], label="Mega-cap tech vs S&P (NDX/SPX)"),
    "CYC":     dict(type="basket", tickers=["XLY", "XLI", "XLB", "XLF", "XLE"], label="Cyclical sectors"),
    "CYCDEF":  dict(type="ratio", num=["XLY", "XLI", "XLB", "XLF", "XLE"], den=["XLP", "XLU", "XLV"],
                    label="Cyclicals vs defensives"),
    "JUNK":    dict(type="ratio", num=["ARKK", "IWC"], den=["SPY"], label="Speculative + micro vs S&P (ARKK, IWC / SPY)"),
    "XLYXLP":  dict(type="ratio", num=["XLY"], den=["XLP"], label="Discretionary vs staples (XLY/XLP)"),
    "XLPXLY":  dict(type="ratio", num=["XLP"], den=["XLY"], label="Staples vs discretionary (XLP/XLY)"),
    "CULU":    dict(type="basket", tickers=["HG=F", "LBR=F"], label="Copper + lumber"),
    "VIX":     dict(type="price", ticker="^VIX", label="VIX"),
    "USD":     dict(type="price", ticker="DX-Y.NYB", label="Dollar index (DXY)"),
    "MATFIN":  dict(type="ratio", num=["XLB", "XLF"], den=["SPY"], label="Materials + financials vs S&P"),
    "FCF":     dict(type="ratio", num=["COWZ"], den=["SPY"], label="High free cash flow vs S&P (COWZ/SPY)"),
    "LEI":     dict(type="macro", series="LEI_PROXY", label="Leading index (free proxy)"),
    "EPS":     dict(type="macro", series="CP", label="Corporate profits (quarterly, lagging)"),
}

# One line on why each measure matters (shown under each signal)
WHY = {
    "NY": "The price of money. Falling yields mean the market expects easier policy or slower growth.",
    "RY": "Yield after inflation. Rising real yields tighten conditions and hurt long-duration assets.",
    "IE": "What bonds price for inflation. Rising breakevens usually mean reflation.",
    "Y2": "Tracks expected Fed policy over the next two years.",
    "HBLB": "Investors reaching for risk push high beta above low volatility.",
    "HB": "The most economically sensitive stocks; they lead in both directions.",
    "DMEM": "Developed markets beating emerging means a defensive, dollar-friendly tape.",
    "EMDM": "EM beating DM signals global growth and a softer dollar.",
    "EM": "Emerging markets need easy dollar liquidity and global demand.",
    "DM": "Steadier developed markets hold up when leadership is unclear.",
    "GOLD": "Rallies when real yields and the dollar fall; a hedge against easy money.",
    "OIL": "Demand plus inflation pressure; a bear-steepener favorite.",
    "COMM": "Real-economy demand and inflation in one basket.",
    "HPE": "Expensive growth stocks win when long yields fall (their cash flows are far out).",
    "LPE": "Cheap stocks win when yields and nominal growth rise.",
    "LCSC": "Large caps beating small caps means investors want balance-sheet safety.",
    "SCLC": "Small caps are domestic and rate-sensitive; they lead when growth improves.",
    "SMALL": "Small and micro caps beating the S&P is classic risk appetite.",
    "LARGE": "Large caps are the market's quality core.",
    "LMGB": "Long Treasuries rally when growth or inflation expectations fall.",
    "SGB": "Short Treasuries fall when the market prices more Fed hikes.",
    "CORP": "Corporate bonds combine rates and credit risk; both turn when conditions do.",
    "XLKXLB": "Tech over materials: growth that doesn't depend on the economic cycle.",
    "PTECH": "Mega-cap tech beating the index: investors pay for profitable growth.",
    "CYC": "Cyclical sectors rise and fall with the economy.",
    "CYCDEF": "Cyclicals over defensives means the market expects stronger growth.",
    "JUNK": "Speculative names rip when liquidity is abundant and shorts get squeezed.",
    "XLYXLP": "Discretionary over staples: consumers expected to spend, not just survive.",
    "XLPXLY": "Staples over discretionary: investors hiding in necessities.",
    "CULU": "Industrial metals and building materials track real activity.",
    "VIX": "Option-implied fear. Falling VIX means calmer markets and more risk-taking.",
    "USD": "A rising dollar tightens global financial conditions.",
    "MATFIN": "Materials and banks benefit from steeper curves and higher nominal growth.",
    "FCF": "Cash-generating companies hold up when the outlook is murky.",
    "LEI": "Leading indicators turn before the economy does.",
    "EPS": "Earnings direction. Uses BEA corporate profits; forward EPS is not free.",
}

# expect: up | down | flat | flat_down   (chart arrows ▲ ▼ ▶ ▶▼)
QUADRANTS = [
    dict(key="growth", name="Growth", curve="Bull flattener", pos=(-1, 1),
         blurb="Yields fall, long end leads. Long-duration growth and quality tech win; commodities lag.",
         signals=[
             ("NY", "N. Yields", "down"), ("RY", "R. Yields", "flat_down"), ("IE", "Inf. exp.", "flat"),
             ("HBLB", "Highβ / Lowβ", "down"), ("DMEM", "DM / EM", "up"), ("GOLD", "Gold", "up"),
             ("COMM", "Commodities", "down"), ("HPE", "High P/E", "up"), ("LCSC", "Large / Small cap", "up"),
             ("LMGB", "Long + Med. Gov. bonds", "up"), ("XLKXLB", "XLK / XLB", "up"),
             ("PTECH", "Highly profitable tech", "up"),
         ]),
    dict(key="riskon", name="Risk ON", curve="Bull steepener", pos=(1, 1),
         blurb="Easier policy plus improving growth. Be fully invested: small caps, high beta, cyclicals, EM.",
         signals=[
             ("EPS", "EPS", "up"), ("LEI", "LEI", "up"),
             ("NY", "N. Yields", "down"), ("RY", "R. Yields", "down"), ("IE", "Inf. exp.", "up"),
             ("SMALL", "Small + Micro cap", "up"), ("HB", "Highβ", "up"), ("GOLD", "Gold", "up"),
             ("COMM", "Commodities", "up"), ("EM", "EM", "up"), ("CYC", "Cyclicals", "up"),
             ("JUNK", "Junk + high short interest", "up"), ("XLYXLP", "XLY / XLP", "up"),
             ("CULU", "Copper + Lumber", "up"), ("CORP", "Corporate bonds", "up"),
             ("VIX", "VIX", "down"), ("USD", "Dollar", "down"),
         ]),
    dict(key="riskoff", name="Risk OFF", curve="Bear flattener", pos=(-1, -1),
         blurb="Tightening into a slowdown. Be defensive: dollar and cash up, staples over discretionary.",
         signals=[
             ("EPS", "EPS", "down"), ("LEI", "LEI", "down"),
             ("NY", "N. Yields", "up"), ("IE", "Inf. exp.", "down"), ("RY", "R. Yields", "up"),
             ("XLPXLY", "XLP / XLY", "up"), ("SGB", "Short Gov. bonds", "down"),
             ("CORP", "Corporate bonds", "down"), ("HB", "Highβ", "down"), ("CYC", "Cyclicals", "down"),
             ("GOLD", "Gold", "down"), ("COMM", "Commodities", "down"),
             ("USD", "Dollar", "up"), ("VIX", "VIX", "up"),
         ]),
    dict(key="value", name="Value", curve="Bear steepener", pos=(1, -1),
         blurb="Yields rise on growth and inflation. Value, small caps, materials, financials and oil lead.",
         signals=[
             ("NY", "N. Yields", "up"), ("IE", "Inf. exp.", "up"), ("RY", "R. Yields", "flat_down"),
             ("SCLC", "Small / Large cap", "up"), ("LMGB", "Long + Med. Gov. bonds", "down"),
             ("CORP", "Corporate bonds", "down"), ("MATFIN", "XLB + XLF / SPY", "up"),
             ("LPE", "Low P/E", "up"), ("CYCDEF", "Cyclicals / non-cyclicals", "up"),
             ("HBLB", "Highβ / Lowβ", "up"), ("GOLD", "Gold", "down"), ("OIL", "Oil", "up"),
             ("COMM", "Commodities", "up"), ("EMDM", "EM / DM", "up"),
         ]),
]

QUALITY = dict(key="quality", name="Quality", curve="Transition",
               blurb="The center of the map. When no quadrant dominates, quality usually holds up best.",
               signals=[
                   ("FCF", "High FCF", "up"), ("DM", "DM", "up"),
                   ("LPE", "Low P/E / High P/E", "up"), ("LARGE", "Large cap", "up"),
               ])

# Windows the regime is measured over (calendar offsets)
WINDOWS = {"1M": dict(months=1), "3M": dict(months=3)}

# A move counts as up/down when it is larger than this many standard deviations
# of that measure's own typical move over the window (z-score band).
Z_BAND = 0.3
Z_STRONG = 1.0

# ---------------------------------------------------------------------------
# Backtest results shown on the site so each call carries its track record.
# research/site_constants.py writes research/out/site_constants.json, which
# replaces these at the bottom of this file; the values here are only a
# fallback copy of the Oct 2026 run.
# ---------------------------------------------------------------------------
DEFAULT_WINDOW = "3M"   # the steadier look-back; 1M is shown as noisy
ALERT_DAYS = 5          # the alert uses the average of the last 5 daily scores, so no weekday matters

BACKTEST = dict(  # the Risk OFF alert: highest 5-day average score on the 3-month checklist, since Jul 2008
    period="Jul 2008 – Oct 2026", episodes=33, share_of_days=13, median_weeks=1,
    spx_next3m=-9.2, spx_avg3m=12.7, cash_cagr=16.39, cash_sharpe=0.93, cash_maxdd=-34,
    bh_cagr=12.47, bh_sharpe=0.62, bh_maxdd=-47,
    false_alarms=15, false_cost=1.8, real_alerts=18, real_saved=-4.7,
    missed="the fast crashes of early 2020 and spring 2025",
)

# Yield-curve shapes over 3-month windows, 1990–2026. "during" = S&P 500 total
# return while the shape formed; up/down = S&P return over the NEXT 3 months
# when the S&P was above/below its 200-day average (annualized %, weeks).
CURVE_AVG = 11.2
CURVE_FLAT = (12.6, 480)  # weeks with no clear shape (parallel or tiny moves): next-3M S&P, weeks
CURVE_SHAPES = {
    "riskon": dict(name="Bull steepener", during=-5.9, up=(12.6, 195), down=(1.2, 145),
                   up_label="good cuts: stocks holding up", down_label="bad cuts: cutting into weakness",
                   note="Short rates falling fastest, so the market expects Fed cuts. Your chart calls this "
                        "Risk ON, but stocks fell on average while it happened, and what came next depended "
                        "on whether growth was holding up."),
    "growth": dict(name="Bull flattener", during=9.8, up=(14.8, 299), down=(28.4, 80),
                   up_label="stocks in an uptrend", down_label="stocks in a downtrend",
                   note="Long yields falling fastest. Matches the chart's Growth playbook, and the best "
                        "stretch for stocks afterwards."),
    "riskoff": dict(name="Bear flattener", during=10.1, up=(6.9, 295), down=(-2.8, 89),
                    up_label="stocks in an uptrend", down_label="stocks in a downtrend",
                    note="Short rates rising fastest, so the Fed is tightening. Stocks often keep rising "
                         "at first; the following 3 months were the weakest of the four shapes."),
    "value": dict(name="Bear steepener", during=23.2, up=(14.9, 266), down=(10.1, 34),
                  up_label="stocks in an uptrend", down_label="stocks in a downtrend",
                  note="Long yields rising fastest: reflation. Matches the chart's Value playbook, and "
                       "often Risk ON's too."),
}

# The research job writes every displayed backtest figure to this file
# (python -m research.site_constants). When present it overrides the defaults above.
import json as _json
import os as _os

_SITE_CONSTANTS = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
                                "research", "out", "site_constants.json")
try:
    with open(_SITE_CONSTANTS) as _f:
        SITE = _json.load(_f)
    BACKTEST = SITE["track"]
except (OSError, ValueError, KeyError):
    SITE = None
