"""
pipeline.py — Full automation pipeline: screener → watchlist → analysis → ranking.

This module contains the core logic for the automated investment pipeline.
Both scheduler.py (background process) and app.py ("Ejecutar ahora" button)
call run_full_pipeline() to trigger the complete cycle.

Pipeline steps:
  1. Screener on ALL markets (fresh data, no cache)
  2. Merge candidates into watchlist (never removes existing tickers)
  3. Batch Buffett analysis on the full watchlist
  4. Save automation_status.json with metadata
"""

import datetime
import json
import logging
import os
import warnings
from typing import Callable, Optional

import batch
import markets as mkt
import screener
import watchlist

logger = logging.getLogger(__name__)

STATUS_FILE = os.path.join(os.path.dirname(__file__), "data", "automation_status.json")


def run_full_pipeline(
    progress_callback: Optional[Callable] = None,
) -> dict:
    """
    Execute the complete automated investment pipeline.

    Args:
        progress_callback: Optional callable(message: str, pct: float).
                           pct is 0.0-1.0. Used to update UI progress bars.

    Returns:
        Status dict with metadata about the completed cycle.
    """
    t0 = datetime.datetime.now()

    def _log(msg: str, pct: float = 0.0) -> None:
        logger.info(msg)
        if progress_callback is not None:
            try:
                progress_callback(msg, pct)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Step 1: Screener on ALL markets
    # ------------------------------------------------------------------
    _log("Ejecutando screener en todos los mercados...", 0.03)
    all_market_keys = mkt.all_market_keys()

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            candidates = screener.get_candidates(
                markets="all",
                use_cache=False,   # always fresh data every 15-day cycle
                cache_hours=0,
            )
    except Exception as exc:
        logger.error(f"Screener failed: {exc}")
        candidates = []

    _log(
        f"Screener completado: {len(candidates)} candidatos de {len(all_market_keys)} mercados.",
        0.40,
    )

    # ------------------------------------------------------------------
    # Step 2: Merge candidates into watchlist (non-destructive)
    # ------------------------------------------------------------------
    _log("Actualizando watchlist con candidatos nuevos...", 0.42)
    wl_before = len(watchlist.load())
    added = watchlist.merge(candidates)
    wl_after_list = watchlist.load()
    _log(
        f"Watchlist: {wl_before} → {len(wl_after_list)} empresas "
        f"({added} nuevas agregadas del screener).",
        0.46,
    )

    # ------------------------------------------------------------------
    # Step 3: Batch Buffett analysis on the full watchlist
    # ------------------------------------------------------------------
    _log(f"Iniciando analisis Buffett de {len(wl_after_list)} empresas...", 0.50)

    def _batch_cb(current, total, ticker, status):
        pct = 0.50 + (current / max(total, 1)) * 0.45
        _log(f"[{current}/{total}] {ticker}: {status}", pct)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        batch.run(
            tickers=wl_after_list,
            use_cache_age_hours=0,       # force full re-analysis
            progress_callback=_batch_cb,
        )

    # ------------------------------------------------------------------
    # Step 4: Save automation status
    # ------------------------------------------------------------------
    duration = (datetime.datetime.now() - t0).total_seconds()
    next_run_dt = t0 + datetime.timedelta(days=15)

    status = {
        "last_run_at": t0.isoformat(),
        "next_run_at": next_run_dt.isoformat(),
        "markets_scanned": all_market_keys,
        "candidates_found": len(candidates),
        "added_to_watchlist": added,
        "watchlist_size": len(wl_after_list),
        "duration_seconds": round(duration, 1),
    }

    try:
        os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
        with open(STATUS_FILE, "w") as f:
            json.dump(status, f, indent=2)
    except Exception as exc:
        logger.warning(f"Could not save automation status: {exc}")

    _log(
        f"Pipeline completado en {duration/60:.1f} min. "
        f"Proximo ciclo: {next_run_dt.strftime('%Y-%m-%d')}.",
        1.0,
    )
    return status


def load_status() -> dict:
    """
    Load the metadata from the last pipeline run.
    Returns an empty dict if the pipeline has never been executed.
    """
    try:
        with open(STATUS_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
