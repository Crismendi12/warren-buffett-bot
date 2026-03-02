"""
batch.py — Multi-ticker analysis engine with persistent JSON cache.

Runs firewall + full analysis on a list of tickers, saves results to
data/results_cache.json. Results can be loaded by the Streamlit app
without re-fetching.

Usage:
    python3 batch.py                    # analyze watchlist only
    python3 batch.py --screener         # watchlist + screener candidates
    python3 batch.py --tickers AAPL KO  # specific tickers
"""

import argparse
import json
import logging
import os
import time
from datetime import datetime
from typing import List, Optional

import numpy as np


class _SafeEncoder(json.JSONEncoder):
    """Handle numpy scalars and other non-standard types from yfinance/pandas."""
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)

import firewall
import analysis
import insider as insider_mod
import capital as capital_mod
import metrics as metrics_mod
import watchlist as wl

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

CACHE_PATH = os.path.join(os.path.dirname(__file__), "data", "results_cache.json")
DELAY_BETWEEN_TICKERS = 1.0  # seconds between yfinance calls


def load_cache() -> dict:
    """Load existing results cache. Returns empty structure if not found."""
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH) as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_run": None, "results": {}}


def save_cache(cache: dict) -> None:
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2, cls=_SafeEncoder)


def result_to_dict(r: analysis.AnalysisResult) -> dict:
    """Serialize an AnalysisResult to a JSON-compatible dict."""
    def section_dict(s):
        return {
            "name": s.name,
            "score": s.score,
            "max_score": s.max_score,
            "pct": s.pct,
            "criteria": [
                {
                    "name": c.name,
                    "raw_label": c.raw_label,
                    "threshold": c.threshold,
                    "source": c.source,
                    "points_earned": c.points_earned,
                    "points_max": c.points_max,
                    "passed": c.passed,
                    "explanation": c.explanation,
                }
                for c in s.criteria
            ],
        }

    return {
        "symbol": r.symbol,
        "company_name": r.company_name,
        "sector": r.sector,
        "industry": r.industry,
        "current_price": r.current_price,
        "market_cap": r.market_cap,
        "total_score": r.total_score,
        "total_max": r.total_max,
        "total_pct": r.total_pct,
        "verdict": r.verdict,
        "intrinsic_value": r.intrinsic_value,
        "moat": section_dict(r.moat),
        "valuation": section_dict(r.valuation),
        "health": section_dict(r.health),
        "growth": section_dict(r.growth),
        "analyzed_at": datetime.now().isoformat(),
    }


def run(
    tickers: List[str],
    use_cache_age_hours: Optional[float] = 12,
    progress_callback=None,
) -> dict:
    """
    Run analysis on each ticker. Skips tickers whose cached result is fresh.

    Args:
        tickers: List of ticker symbols.
        use_cache_age_hours: Skip analysis if cached result is newer than this.
                             Pass None to force re-analysis of all tickers.
        progress_callback: Optional callable(current, total, ticker, status).

    Returns:
        dict of {ticker: result_dict} — fresh and cached combined.
    """
    cache = load_cache()
    results = cache.get("results", {})
    now = datetime.now()
    total = len(tickers)

    for i, ticker in enumerate(tickers):
        ticker = ticker.upper().strip()

        # Skip if cached result is fresh enough
        if use_cache_age_hours is not None and ticker in results:
            cached_at = results[ticker].get("analyzed_at")
            if cached_at:
                try:
                    age = now - datetime.fromisoformat(cached_at)
                    if age.total_seconds() / 3600 < use_cache_age_hours:
                        logger.info(f"[{i+1}/{total}] {ticker} — using cache ({age.seconds//60}m old)")
                        if progress_callback:
                            progress_callback(i + 1, total, ticker, "cached")
                        continue
                except Exception:
                    pass

        logger.info(f"[{i+1}/{total}] Analyzing {ticker}...")
        if progress_callback:
            progress_callback(i + 1, total, ticker, "analyzing")

        # Firewall check
        fw = firewall.run(ticker)
        if fw.status == "BLOCK":
            reason = fw.block_issues[0].message if fw.block_issues else "Blocked by firewall"
            logger.info(f"  BLOCKED: {reason}")
            results[ticker] = {
                "symbol": ticker,
                "blocked": True,
                "block_reason": reason,
                "analyzed_at": now.isoformat(),
            }
            if progress_callback:
                progress_callback(i + 1, total, ticker, "blocked")
            time.sleep(DELAY_BETWEEN_TICKERS)
            continue

        # Full analysis
        try:
            result = analysis.run(ticker)
            results[ticker] = result_to_dict(result)
            results[ticker]["firewall_warnings"] = [
                {"code": w.code, "message": w.message}
                for w in fw.warn_issues
            ]

            # Enrich with insider signal and capital quality for conviction scoring
            try:
                results[ticker]["insider"] = insider_mod.get_insider_signal(ticker)
            except Exception as ie:
                logger.debug(f"  insider enrichment skipped: {ie}")
                results[ticker]["insider"] = {"signal": "NEUTRAL", "error": str(ie)}
            try:
                results[ticker]["capital"] = capital_mod.get_capital_quality(ticker)
            except Exception as ce:
                logger.debug(f"  capital enrichment skipped: {ce}")
                results[ticker]["capital"] = {"roic_vs_wacc": None, "roic_avg": None, "error": str(ce)}
            try:
                results[ticker]["price_metrics"] = metrics_mod.get_price_metrics(ticker)
            except Exception as pe:
                logger.debug(f"  price_metrics enrichment skipped: {pe}")
                results[ticker]["price_metrics"] = {}

            logger.info(
                f"  Score: {result.total_score}/100 — {result.verdict}"
            )
            if progress_callback:
                progress_callback(i + 1, total, ticker, f"{result.total_score}/100")
        except Exception as e:
            logger.error(f"  ERROR: {e}")
            results[ticker] = {
                "symbol": ticker,
                "error": str(e),
                "analyzed_at": now.isoformat(),
            }
            if progress_callback:
                progress_callback(i + 1, total, ticker, "error")

        # Save incrementally so partial runs aren't lost
        cache["results"] = results
        cache["last_run"] = now.isoformat()
        save_cache(cache)

        time.sleep(DELAY_BETWEEN_TICKERS)

    cache["results"] = results
    cache["last_run"] = now.isoformat()
    save_cache(cache)
    return results


def get_ranked_results(min_score: int = 0) -> list:
    """
    Load cached results and return them sorted by score, descending.
    Excludes blocked/errored tickers.
    """
    cache = load_cache()
    results = cache.get("results", {})
    ranked = [
        r for r in results.values()
        if not r.get("blocked") and not r.get("error")
        and r.get("total_score", -1) >= min_score
    ]
    ranked.sort(key=lambda x: x.get("total_score", 0), reverse=True)
    return ranked


def get_last_run_time() -> Optional[str]:
    cache = load_cache()
    return cache.get("last_run")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch Buffett analysis")
    parser.add_argument("--screener", action="store_true",
                        help="Include screener candidates (S&P 500 pre-filter)")
    parser.add_argument("--tickers", nargs="+", metavar="TICKER",
                        help="Specific tickers to analyze (overrides watchlist)")
    parser.add_argument("--force", action="store_true",
                        help="Force re-analysis even if cache is fresh")
    parser.add_argument("--min-score", type=int, default=0,
                        help="Print only results above this score")
    args = parser.parse_args()

    # Build ticker list
    if args.tickers:
        tickers = args.tickers
    else:
        tickers = wl.load()
        if args.screener:
            import screener
            screener_candidates = screener.get_candidates()
            # Merge without duplicates
            existing = set(tickers)
            tickers = tickers + [t for t in screener_candidates if t not in existing]

    logger.info(f"Starting batch analysis on {len(tickers)} tickers")
    logger.info(f"Source: {'custom list' if args.tickers else 'watchlist' + (' + screener' if args.screener else '')}")

    cache_hours = None if args.force else 12
    results = run(tickers, use_cache_age_hours=cache_hours)

    # Print ranking
    ranked = get_ranked_results(min_score=args.min_score)
    print(f"\n{'='*60}")
    print(f"RANKING — {len(ranked)} empresas analizadas")
    print(f"{'='*60}")
    print(f"{'Ticker':<8} {'Empresa':<30} {'Score':<8} Veredicto")
    print(f"{'-'*70}")
    for r in ranked:
        score = r.get("total_score", 0)
        name = r.get("company_name", r["symbol"])[:28]
        verdict = r.get("verdict", "")
        print(f"{r['symbol']:<8} {name:<30} {score:<8} {verdict}")
