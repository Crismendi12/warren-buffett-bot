"""
screener.py — Automatic candidate discovery from multi-market universe.

Workflow:
  1. Fetch constituent lists from Wikipedia (or fallback) via markets.py.
  2. Apply a fast pre-filter using only yfinance .info (1 request per ticker).
  3. Return filtered list to batch.py for full Buffett analysis.

Pre-filter criteria:
  - ROE >= 12%
  - Debt/Equity < 1.5
  - Market cap >= $300M  (lowered from $1B to support LatAm/emerging markets)
  - Profit margin > 0

Usage:
  get_candidates()                          # S&P 500 only
  get_candidates(markets=["us_sp500", "europe_dax", "latam_brazil"])
  get_candidates(markets="all")             # all configured markets
"""

import time
import logging
from typing import List, Optional, Union

import pandas as pd
import yfinance as yf

import markets as mkt

logger = logging.getLogger(__name__)


def get_sp500_tickers() -> List[str]:
    """Fetch S&P 500 via markets.py (Wikipedia with fallback)."""
    return mkt.get_tickers("us_sp500")


def pre_filter(tickers: List[str], delay: float = 0.3,
               min_cap: float = 300_000_000) -> List[str]:
    """
    Run fast pre-filter on each ticker using only yfinance .info.

    Args:
        tickers: List of ticker symbols.
        delay: Sleep between calls (rate limit protection).
        min_cap: Minimum market cap. Default $300M (supports non-US markets).
    """
    candidates = []
    total = len(tickers)

    for i, ticker in enumerate(tickers):
        try:
            info = yf.Ticker(ticker).info

            if not info or info.get("marketCap") is None:
                continue

            market_cap = info.get("marketCap", 0) or 0
            roe = info.get("returnOnEquity") or 0
            de_raw = info.get("debtToEquity")
            de = (de_raw / 100) if de_raw is not None else None
            profit_margin = info.get("profitMargins") or 0
            quote_type = str(info.get("quoteType", "")).lower()

            if quote_type not in ("equity", "stock", ""):
                continue
            if market_cap < min_cap:
                continue
            if roe < 0.12:
                continue
            if de is not None and de > 1.5:
                continue
            if profit_margin <= 0:
                continue

            candidates.append(ticker)
            logger.debug(f"[{i+1}/{total}] {ticker} PASS — ROE:{roe*100:.1f}%")

        except Exception as e:
            logger.debug(f"[{i+1}/{total}] {ticker} ERROR — {e}")

        time.sleep(delay)

    logger.info(f"Pre-filter: {len(candidates)}/{total} passed")
    return candidates


def get_candidates(
    markets: Union[List[str], str] = "us_sp500",
    use_cache: bool = True,
    cache_hours: int = 24,
) -> List[str]:
    """
    Return candidate tickers from the screener.

    Args:
        markets: One market key, a list of market keys, or "all".
        use_cache: Use file cache if fresh.
        cache_hours: How old a cache can be before refreshing.
    """
    import os, json
    from datetime import datetime, timedelta

    # Normalize markets arg
    if markets == "all":
        market_keys = mkt.all_market_keys()
    elif isinstance(markets, str):
        market_keys = [markets]
    else:
        market_keys = list(markets)

    cache_key = "_".join(sorted(market_keys))
    cache_path = os.path.join(
        os.path.dirname(__file__), "data",
        f"screener_cache_{cache_key}.json",
    )
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)

    if use_cache and os.path.exists(cache_path):
        try:
            with open(cache_path) as f:
                cached = json.load(f)
            age = datetime.now() - datetime.fromisoformat(cached["timestamp"])
            if age < timedelta(hours=cache_hours):
                logger.info(
                    f"Using screener cache [{cache_key}] "
                    f"({len(cached['candidates'])} candidates, {age.seconds//3600}h old)"
                )
                return cached["candidates"]
        except Exception:
            pass

    logger.info(f"Running screener on markets: {market_keys}")
    universe = mkt.get_tickers_multi(market_keys)
    logger.info(f"Universe: {len(universe)} tickers")
    candidates = pre_filter(universe)

    try:
        with open(cache_path, "w") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "markets": market_keys,
                "total_universe": len(universe),
                "candidates": candidates,
            }, f, indent=2)
    except Exception as e:
        logger.warning(f"Could not save screener cache: {e}")

    return candidates

