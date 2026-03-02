"""
data_sources.py — Free institutional-grade data fallback layer.

Enriches yfinance info dicts with data from:
  1. SEC EDGAR (US stocks only) — same primary source Bloomberg uses, completely free,
     no API key, no rate limit. Covers: sharesOutstanding, trailingEps, bookValue, D/E.
  2. FMP free tier (all markets) — 250 calls/day, requires free API key in .env file.
     Covers the same fields for international stocks that EDGAR cannot reach.

Usage:
    import data_sources
    info = yf.Ticker(symbol).info
    info = data_sources.enrich_info(symbol, info)  # fills None fields, never overwrites
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_DIR        = os.path.dirname(os.path.abspath(__file__))
_CIK_CACHE  = os.path.join(_DIR, "data", "edgar_ciks.json")
_FACT_CACHE = os.path.join(_DIR, "data", "edgar_facts_cache.json")

# ---------------------------------------------------------------------------
# Optional FMP key — loaded once at import from .env file
# ---------------------------------------------------------------------------
_FMP_KEY: Optional[str] = None
_ENV_FILE = os.path.join(_DIR, ".env")
if os.path.exists(_ENV_FILE):
    try:
        for _line in open(_ENV_FILE):
            _line = _line.strip()
            if _line.startswith("FMP_API_KEY=") and not _line.startswith("#"):
                _v = _line.split("=", 1)[1].strip()
                if _v and _v != "your_free_api_key_here":
                    _FMP_KEY = _v
                break
    except Exception:
        pass

# Fallback: variable de entorno (Streamlit Cloud inyecta secretos asi)
if not _FMP_KEY:
    _env_key = os.environ.get("FMP_API_KEY", "").strip()
    if _env_key and _env_key != "your_free_api_key_here":
        _FMP_KEY = _env_key

_EDGAR_HEADERS = {
    "User-Agent": "WarrenBuffettBot/1.0 personal-research",
    "Accept": "application/json",
}

# ---------------------------------------------------------------------------
# EDGAR — CIK map
# ---------------------------------------------------------------------------

def _load_cik_map() -> dict:
    """
    Load ticker→CIK map. Downloads from EDGAR on first call or monthly refresh.
    Returns a dict like {"AAPL": "0000320193", "MSFT": "0000789019", ...}
    """
    if os.path.exists(_CIK_CACHE):
        try:
            data = json.load(open(_CIK_CACHE))
            age = datetime.now() - datetime.fromisoformat(data["cached_at"])
            if age < timedelta(days=30):
                return data["tickers"]
        except Exception:
            pass

    try:
        r = requests.get(
            "https://www.sec.gov/files/company_tickers.json",
            headers=_EDGAR_HEADERS,
            timeout=15,
        )
        r.raise_for_status()
        raw = r.json()
        ticker_map = {
            v["ticker"].upper(): str(v["cik_str"]).zfill(10)
            for v in raw.values()
        }
        os.makedirs(os.path.dirname(_CIK_CACHE), exist_ok=True)
        json.dump(
            {"cached_at": datetime.now().isoformat(), "tickers": ticker_map},
            open(_CIK_CACHE, "w"),
        )
        logger.info(f"EDGAR CIK map downloaded: {len(ticker_map)} tickers")
        return ticker_map
    except Exception as e:
        logger.debug(f"EDGAR CIK map unavailable: {e}")
        return {}


def get_ticker_cik(symbol: str) -> Optional[str]:
    """Return 10-digit zero-padded CIK for a US ticker, or None if not found."""
    return _load_cik_map().get(symbol.upper())


# ---------------------------------------------------------------------------
# EDGAR — company facts
# ---------------------------------------------------------------------------

def _get_edgar_facts(cik: str) -> dict:
    """
    Fetch EDGAR company facts for a CIK. Results cached for 24 hours.
    Returns the facts sub-dict like: {"us-gaap": {...}, "dei": {...}}
    """
    cache: dict = {}
    if os.path.exists(_FACT_CACHE):
        try:
            cache = json.load(open(_FACT_CACHE))
        except Exception:
            cache = {}

    entry = cache.get(cik, {})
    cached_at = entry.get("cached_at")
    if cached_at:
        try:
            age = datetime.now() - datetime.fromisoformat(cached_at)
            if age < timedelta(hours=24):
                return entry.get("facts", {})
        except Exception:
            pass

    try:
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
        r = requests.get(url, headers=_EDGAR_HEADERS, timeout=20)
        if r.status_code == 200:
            facts = r.json().get("facts", {})
            cache[cik] = {"cached_at": datetime.now().isoformat(), "facts": facts}
            os.makedirs(os.path.dirname(_FACT_CACHE), exist_ok=True)
            json.dump(cache, open(_FACT_CACHE, "w"))
            return facts
    except Exception as e:
        logger.debug(f"EDGAR facts unavailable for CIK {cik}: {e}")
    return {}


def _edgar_latest_annual(facts: dict, taxonomy: str, concept: str) -> Optional[float]:
    """
    Extract the most recent 10-K or 20-F annual value for a US-GAAP/DEI concept.
    Returns None if concept not found or no annual filings.
    """
    try:
        units = facts.get(taxonomy, {}).get(concept, {}).get("units", {})
        for unit_key in list(units.keys()):
            entries = [
                e for e in units[unit_key]
                if e.get("form") in ("10-K", "20-F") and "val" in e
            ]
            if entries:
                latest = max(entries, key=lambda x: x.get("end", ""))
                return float(latest["val"])
    except Exception:
        pass
    return None


def _enrich_from_edgar(symbol: str, enriched: dict) -> dict:
    """Fill critical None fields using SEC EDGAR. Only for US-listed stocks."""
    cik = get_ticker_cik(symbol)
    if not cik:
        return enriched

    facts = _get_edgar_facts(cik)
    if not facts:
        return enriched

    # 1. sharesOutstanding — most impactful: unlocks EPS and BVPS calculations
    if not enriched.get("sharesOutstanding"):
        v = (
            _edgar_latest_annual(facts, "dei", "EntityCommonStockSharesOutstanding")
            or _edgar_latest_annual(facts, "us-gaap", "CommonStockSharesOutstanding")
        )
        if v and v > 0:
            enriched["sharesOutstanding"] = int(v)
            logger.debug(f"EDGAR filled sharesOutstanding for {symbol}: {int(v):,}")

    # 2. trailingEps — derived from net income / shares
    if not enriched.get("trailingEps"):
        ni = _edgar_latest_annual(facts, "us-gaap", "NetIncomeLoss")
        sh = enriched.get("sharesOutstanding")
        if ni is not None and sh and sh > 0:
            enriched["trailingEps"] = round(ni / sh, 4)
            logger.debug(f"EDGAR filled trailingEps for {symbol}: {enriched['trailingEps']}")

    # 3. bookValue (book value per share) — stockholders equity / shares
    if not enriched.get("bookValue"):
        eq = (
            _edgar_latest_annual(facts, "us-gaap", "StockholdersEquity")
            or _edgar_latest_annual(
                facts,
                "us-gaap",
                "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
            )
        )
        sh = enriched.get("sharesOutstanding")
        if eq is not None and sh and sh > 0:
            enriched["bookValue"] = round(eq / sh, 4)
            logger.debug(f"EDGAR filled bookValue for {symbol}: {enriched['bookValue']}")

    # 4. debtToEquity — long term debt / equity
    # yfinance reports D/E as a percentage (e.g. 150 = 150% = 1.5x ratio)
    if enriched.get("debtToEquity") is None:
        debt = _edgar_latest_annual(facts, "us-gaap", "LongTermDebt")
        eq   = _edgar_latest_annual(facts, "us-gaap", "StockholdersEquity")
        if debt is not None and eq and eq > 0:
            enriched["debtToEquity"] = round(debt / eq * 100, 2)
            logger.debug(f"EDGAR filled debtToEquity for {symbol}: {enriched['debtToEquity']}")

    return enriched


# ---------------------------------------------------------------------------
# FMP free tier fallback
# ---------------------------------------------------------------------------

def _enrich_from_fmp(symbol: str, enriched: dict) -> dict:
    """
    Fill remaining None fields using FMP free tier (250 calls/day).
    Only active when FMP_API_KEY is present in the .env file.
    Works for international stocks that EDGAR cannot cover.
    """
    if not _FMP_KEY:
        return enriched

    _needs_enrichment = (
        not enriched.get("sharesOutstanding")
        or not enriched.get("trailingEps")
        or not enriched.get("bookValue")
        or enriched.get("debtToEquity") is None
        or enriched.get("currentRatio") is None
    )
    if not _needs_enrichment:
        return enriched

    try:
        url = (
            f"https://financialmodelingprep.com/api/v3/key-metrics/{symbol}"
            f"?limit=1&apikey={_FMP_KEY}"
        )
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return enriched
        data = r.json()
        if not data or not isinstance(data, list):
            return enriched
        m = data[0]

        if not enriched.get("sharesOutstanding") and m.get("sharesOutstanding"):
            enriched["sharesOutstanding"] = int(m["sharesOutstanding"])
        if not enriched.get("trailingEps") and m.get("netIncomePerShare"):
            enriched["trailingEps"] = float(m["netIncomePerShare"])
        if not enriched.get("bookValue") and m.get("bookValuePerShare"):
            enriched["bookValue"] = float(m["bookValuePerShare"])
        # FMP returns D/E as a ratio (1.5), yfinance uses percentage (150)
        if enriched.get("debtToEquity") is None and m.get("debtToEquity") is not None:
            enriched["debtToEquity"] = float(m["debtToEquity"]) * 100
        if enriched.get("currentRatio") is None and m.get("currentRatio"):
            enriched["currentRatio"] = float(m["currentRatio"])

        logger.debug(f"FMP enriched {symbol}")
    except Exception as e:
        logger.debug(f"FMP enrichment failed for {symbol}: {e}")

    return enriched


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def enrich_info(symbol: str, info: dict) -> dict:
    """
    Enrich a yfinance info dict with data from EDGAR (US) and FMP (optional).

    Rules:
    - Only fills fields that are falsy (None, 0, missing) — never overwrites valid data
    - EDGAR runs first (free, no key, US only)
    - FMP runs second (free tier, key optional, all markets)
    - Always returns a dict even on complete failure
    - Never raises exceptions

    Args:
        symbol: Ticker symbol (e.g. "AAPL", "SAP", "GRUMA.MX")
        info:   Raw yfinance .info dict (may have None fields)

    Returns:
        Enriched dict with same field names as yfinance .info
    """
    if not info:
        info = {}
    enriched = dict(info)

    try:
        enriched = _enrich_from_edgar(symbol.upper(), enriched)
    except Exception as e:
        logger.debug(f"EDGAR enrichment error for {symbol}: {e}")

    try:
        enriched = _enrich_from_fmp(symbol.upper(), enriched)
    except Exception as e:
        logger.debug(f"FMP enrichment error for {symbol}: {e}")

    return enriched


def fmp_key_configured() -> bool:
    """Return True if a valid FMP API key is loaded."""
    return bool(_FMP_KEY)
