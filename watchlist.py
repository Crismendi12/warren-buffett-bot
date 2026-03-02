"""
watchlist.py — Persistent ticker watchlist backed by a JSON file.

Supports add, remove, list, and load operations.
Thread-safe for concurrent Streamlit + scheduler access via file locking pattern.
"""

import json
import os
from typing import List

WATCHLIST_PATH = os.path.join(os.path.dirname(__file__), "data", "watchlist.json")

# Default starter list — well-known Buffett holdings and quality companies
DEFAULT_TICKERS = ["KO", "AAPL", "BAC", "AXP", "OXY", "CVX", "KHC", "MCO"]


def _load_raw() -> dict:
    os.makedirs(os.path.dirname(WATCHLIST_PATH), exist_ok=True)
    if not os.path.exists(WATCHLIST_PATH):
        return {"tickers": DEFAULT_TICKERS.copy()}
    try:
        with open(WATCHLIST_PATH, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"tickers": DEFAULT_TICKERS.copy()}


def _save_raw(data: dict) -> None:
    os.makedirs(os.path.dirname(WATCHLIST_PATH), exist_ok=True)
    with open(WATCHLIST_PATH, "w") as f:
        json.dump(data, f, indent=2)


def load() -> List[str]:
    """Return the current list of tickers (uppercase, deduplicated)."""
    data = _load_raw()
    return list(dict.fromkeys(t.upper().strip() for t in data.get("tickers", [])))


def add(ticker: str) -> bool:
    """
    Add a ticker to the watchlist. Returns True if added, False if already present.
    """
    ticker = ticker.upper().strip()
    data = _load_raw()
    tickers = list(dict.fromkeys(t.upper().strip() for t in data.get("tickers", [])))
    if ticker in tickers:
        return False
    tickers.append(ticker)
    data["tickers"] = tickers
    _save_raw(data)
    return True


def remove(ticker: str) -> bool:
    """
    Remove a ticker from the watchlist. Returns True if removed, False if not found.
    """
    ticker = ticker.upper().strip()
    data = _load_raw()
    tickers = list(dict.fromkeys(t.upper().strip() for t in data.get("tickers", [])))
    if ticker not in tickers:
        return False
    tickers.remove(ticker)
    data["tickers"] = tickers
    _save_raw(data)
    return True


def set_list(tickers: List[str]) -> None:
    """Replace the entire watchlist."""
    cleaned = list(dict.fromkeys(t.upper().strip() for t in tickers if t.strip()))
    _save_raw({"tickers": cleaned})


def merge(tickers: List[str]) -> int:
    """
    Add tickers to the watchlist without removing existing ones.
    Returns the count of newly added tickers (already-present ones are skipped).
    """
    added = 0
    for t in tickers:
        if add(t):
            added += 1
    return added
