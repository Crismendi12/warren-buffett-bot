"""
markets.py — Multi-market universe manager.

Provides curated lists of quality tickers per global market, with
Wikipedia scraping for major indices where available.

yfinance ticker format by exchange:
  US (NYSE/NASDAQ):  AAPL, MSFT, KO
  Germany (XETRA):   SAP.DE, SIE.DE
  UK (LSE):          AZN.L, SHEL.L
  France (Euronext): TTE.PA, MC.PA
  Brazil (Bovespa):  VALE3.SA, ITUB4.SA
  Mexico (BMV):      GRUMAB.MX, FEMSA.MX
  Colombia (BVC):    Limited — mainly ADRs (EC, CIB, GEB.CO)
  India (NSE):       RELIANCE.NS, TCS.NS
  Hong Kong (HKEX):  0005.HK, 0700.HK
"""

import logging
from io import StringIO
from typing import List, Dict

import pandas as pd
import requests

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Market definitions
# ---------------------------------------------------------------------------

MARKET_DEFS: Dict[str, dict] = {
    "us_sp500": {
        "name": "S&P 500 (USA)",
        "region": "Norteamerica",
        "currency": "USD",
        "wikipedia_url": "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
        "wikipedia_col": "Symbol",
        "dot_replace": True,  # Replace . with - in tickers
        "fallback": [
            "AAPL", "MSFT", "AMZN", "GOOGL", "JNJ", "V", "PG", "JPM", "UNH", "MA",
            "HD", "MRK", "KO", "PEP", "TMO", "ABBV", "COST", "CVX", "ACN", "MCD",
            "DHR", "ABT", "NEE", "LIN", "HON", "PM", "IBM", "CAT", "GE", "MMM",
            "MCO", "SPGI", "ICE", "AXP", "BLK", "GS", "WFC", "USB", "AFL", "AIG",
            "ECL", "EMR", "ITW", "PH", "ROK", "WMT", "TGT", "ROST", "TJX", "NKE",
        ],
    },
    "us_nasdaq100": {
        "name": "Nasdaq 100 (USA)",
        "region": "Norteamerica",
        "currency": "USD",
        "wikipedia_url": "https://en.wikipedia.org/wiki/Nasdaq-100",
        "wikipedia_col": "Ticker",
        "dot_replace": True,
        "fallback": [
            "AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "TSLA", "AVGO", "COST",
            "NFLX", "ASML", "AMD", "QCOM", "INTU", "TXN", "AMAT", "ADI", "MU", "LRCX",
            "REGN", "VRTX", "GILD", "BIIB", "AMGN", "ISRG", "ADP", "PAYX", "CDNS",
            "SNPS", "ANSS", "KLAC", "FTNT", "PANW", "CRWD", "ZS", "DDOG", "ADBE",
        ],
    },
    "us_russell1000": {
        "name": "Russell 1000 (USA mid/large caps)",
        "region": "Norteamerica",
        "currency": "USD",
        "wikipedia_url": None,
        "fallback": [
            "BRK-B", "LLY", "ELV", "CI", "CVS", "HUM", "MOH", "CNC", "UHS", "HCA",
            "DG", "DLTR", "YUM", "CMG", "MCD", "SYY", "GIS", "K", "CPB", "SJM",
            "LOW", "HD", "BBWI", "PVH", "RL", "VFC", "TPR", "NKE", "FL", "GPS",
            "OXY", "COP", "DVN", "EOG", "PXD", "MPC", "VLO", "PSX", "HES", "BKR",
            "AMT", "PLD", "EQIX", "CCI", "DLR", "SPG", "O", "VTR", "WELL", "ARE",
        ],
    },
    "europe_dax": {
        "name": "DAX 40 (Alemania)",
        "region": "Europa",
        "currency": "EUR",
        "wikipedia_url": "https://en.wikipedia.org/wiki/DAX",
        "wikipedia_col": "Ticker",
        "dot_replace": False,
        "fallback": [
            "SAP.DE", "SIE.DE", "ALV.DE", "DTE.DE", "MUV2.DE", "BMW.DE", "MBG.DE",
            "BAS.DE", "BAYN.DE", "ADS.DE", "EOAN.DE", "RWE.DE", "HEN3.DE", "FRE.DE",
            "MRK.DE", "DBK.DE", "CON.DE", "BEI.DE", "ZAL.DE", "HNR1.DE",
            "DHER.DE", "IFX.DE", "QIA.DE", "VNA.DE", "SHL.DE", "MTX.DE",
        ],
    },
    "europe_ftse100": {
        "name": "FTSE 100 (Reino Unido)",
        "region": "Europa",
        "currency": "GBP",
        "wikipedia_url": "https://en.wikipedia.org/wiki/FTSE_100_Index",
        "wikipedia_col": "Ticker",
        "suffix": ".L",
        "dot_replace": False,
        "fallback": [
            "SHEL.L", "AZN.L", "HSBA.L", "ULVR.L", "BP.L", "RIO.L", "DGE.L",
            "GSK.L", "REL.L", "VOD.L", "LSEG.L", "BT-A.L", "BA.L", "LLOY.L",
            "BATS.L", "IMB.L", "STAN.L", "ABF.L", "EXPN.L", "IHG.L",
            "CPG.L", "SGE.L", "RKT.L", "WPP.L", "PSON.L", "SKG.L",
        ],
    },
    "europe_cac40": {
        "name": "CAC 40 (Francia)",
        "region": "Europa",
        "currency": "EUR",
        "wikipedia_url": "https://en.wikipedia.org/wiki/CAC_40",
        "wikipedia_col": "Ticker",
        "dot_replace": False,
        "fallback": [
            "MC.PA", "TTE.PA", "SAN.PA", "AI.PA", "OR.PA", "RI.PA", "BN.PA",
            "STM.PA", "SU.PA", "CAP.PA", "ATO.PA", "SW.PA", "PUB.PA", "HO.PA",
            "AC.PA", "DG.PA", "CS.PA", "VIE.PA", "SGO.PA", "TEP.PA",
        ],
    },
    "latam_brazil": {
        "name": "Bovespa Top (Brasil)",
        "region": "Latinoamerica",
        "currency": "BRL",
        "wikipedia_url": None,
        "fallback": [
            "VALE3.SA", "ITUB4.SA", "BBDC4.SA", "PETR4.SA", "ABEV3.SA", "B3SA3.SA",
            "WEGE3.SA", "RENT3.SA", "RDOR3.SA", "HAPV3.SA", "FLRY3.SA", "TOTS3.SA",
            "SBSP3.SA", "BRFS3.SA", "MRFG3.SA", "JBSS3.SA", "EMBR3.SA", "CSAN3.SA",
            "PRIO3.SA", "EGIE3.SA", "TAEE11.SA", "CMIG4.SA", "CPFE3.SA", "EQTL3.SA",
        ],
    },
    "latam_mexico": {
        "name": "IPC Top (Mexico)",
        "region": "Latinoamerica",
        "currency": "MXN",
        "wikipedia_url": None,
        "fallback": [
            "GRUMAB.MX", "WALMEX.MX", "FEMSAUBD.MX", "AMXL.MX", "GFINBURO.MX",
            "GFNORTEO.MX", "BIMBOA.MX", "CEMEXCPO.MX", "PINFRA.MX", "KIMBERA.MX",
            "GMEXICOB.MX", "ALSEA.MX", "MEGACPO.MX", "LIVEPOLC-1.MX", "SORIANA.MX",
        ],
    },
    "latam_colombia": {
        "name": "BVC / ADRs Colombia",
        "region": "Latinoamerica",
        "currency": "COP",
        "wikipedia_url": None,
        "fallback": [
            # ADRs / US-listed Colombian companies
            "EC",      # Ecopetrol ADR
            "CIB",     # Bancolombia ADR
            "ENIA",    # Enel Americas
            # Tickers directos BVC (cobertura limitada en yfinance)
            "GEB.CO", "ISA.CO", "NUTRESA.CO", "CELSIA.CO", "PFBCOLOM.CO",
            "ÉXITO.CO", "CLH.CO", "BOGOTA.CO",
        ],
    },
    "asia_india": {
        "name": "Nifty 50 (India)",
        "region": "Asia",
        "currency": "INR",
        "wikipedia_url": "https://en.wikipedia.org/wiki/Nifty_50",
        "wikipedia_col": "Symbol",
        "suffix": ".NS",
        "dot_replace": False,
        "fallback": [
            "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
            "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BAJFINANCE.NS", "BHARTIARTL.NS",
            "WIPRO.NS", "HCLTECH.NS", "ASIANPAINT.NS", "LT.NS", "AXISBANK.NS",
            "MARUTI.NS", "TITAN.NS", "SUNPHARMA.NS", "ULTRACEMCO.NS", "NESTLEIND.NS",
            "POWERGRID.NS", "NTPC.NS", "ONGC.NS", "COALINDIA.NS", "DIVISLAB.NS",
        ],
    },
    "asia_hongkong": {
        "name": "Hang Seng Top (Hong Kong)",
        "region": "Asia",
        "currency": "HKD",
        "wikipedia_url": None,
        "fallback": [
            "0005.HK",  # HSBC
            "0700.HK",  # Tencent
            "0941.HK",  # China Mobile
            "1299.HK",  # AIA Group
            "0388.HK",  # HK Exchanges
            "2318.HK",  # Ping An Insurance
            "0939.HK",  # CCB
            "1398.HK",  # ICBC
            "3988.HK",  # Bank of China
            "0883.HK",  # CNOOC
            "0002.HK",  # CLP
            "0003.HK",  # HK and China Gas
            "0011.HK",  # Hang Seng Bank
            "0066.HK",  # MTR
            "1177.HK",  # Sino Biopharmaceutical
            "2388.HK",  # BOC Hong Kong
            "0006.HK",  # Power Assets
        ],
    },
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_tickers(market_key: str) -> List[str]:
    """
    Return the ticker list for a given market key.
    Tries Wikipedia first, falls back to hardcoded list.
    """
    mdef = MARKET_DEFS.get(market_key)
    if not mdef:
        logger.warning(f"Unknown market key: {market_key}")
        return []

    wiki_url = mdef.get("wikipedia_url")
    if wiki_url:
        try:
            tickers = _fetch_from_wikipedia(
                url=wiki_url,
                col=mdef.get("wikipedia_col", "Symbol"),
                suffix=mdef.get("suffix", ""),
                dot_replace=mdef.get("dot_replace", False),
            )
            if tickers:
                logger.info(f"[{market_key}] Loaded {len(tickers)} tickers from Wikipedia")
                return tickers
        except Exception as e:
            logger.warning(f"[{market_key}] Wikipedia fetch failed: {e}. Using fallback.")

    fallback = mdef.get("fallback", [])
    logger.info(f"[{market_key}] Using fallback list ({len(fallback)} tickers)")
    return fallback


def get_tickers_multi(market_keys: List[str]) -> List[str]:
    """Return combined, deduplicated ticker list for multiple markets."""
    seen = set()
    result = []
    for key in market_keys:
        for ticker in get_tickers(key):
            if ticker not in seen:
                seen.add(ticker)
                result.append(ticker)
    return result


def all_market_keys() -> List[str]:
    return list(MARKET_DEFS.keys())


def market_name(key: str) -> str:
    return MARKET_DEFS.get(key, {}).get("name", key)


def markets_by_region() -> Dict[str, List[str]]:
    """Return {region: [market_key, ...]} grouping."""
    result: Dict[str, List[str]] = {}
    for key, mdef in MARKET_DEFS.items():
        region = mdef.get("region", "Otros")
        result.setdefault(region, []).append(key)
    return result


def get_currency(market_key: str) -> str:
    return MARKET_DEFS.get(market_key, {}).get("currency", "USD")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_WIKI_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def _fetch_from_wikipedia(url: str, col: str, suffix: str = "", dot_replace: bool = False) -> List[str]:
    """Fetch index constituents from Wikipedia using a browser User-Agent to avoid 403."""
    response = requests.get(url, headers=_WIKI_HEADERS, timeout=20)
    response.raise_for_status()
    tables = pd.read_html(StringIO(response.text), flavor="html5lib")
    for table in tables:
        if col in table.columns:
            raw = table[col].astype(str).tolist()
            tickers = []
            for t in raw:
                t = t.strip()
                if dot_replace:
                    t = t.replace(".", "-")
                if suffix and not t.endswith(suffix):
                    t = t + suffix
                if t and t != "nan":
                    tickers.append(t)
            return tickers
    raise ValueError(f"Column '{col}' not found in any table at {url}")
