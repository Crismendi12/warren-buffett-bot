"""
preferences.py — Lightweight persistent user preferences across sessions.

Stores arbitrary key-value pairs in data/preferences.json so settings
(selected markets, ETF watchlist, etc.) survive browser reloads.
"""

import json
import os
from typing import Any

PREFS_PATH = os.path.join(os.path.dirname(__file__), "data", "preferences.json")


def load() -> dict:
    os.makedirs(os.path.dirname(PREFS_PATH), exist_ok=True)
    if not os.path.exists(PREFS_PATH):
        return {}
    try:
        with open(PREFS_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def get(key: str, default: Any = None) -> Any:
    return load().get(key, default)


def set_pref(key: str, value: Any) -> None:
    prefs = load()
    prefs[key] = value
    os.makedirs(os.path.dirname(PREFS_PATH), exist_ok=True)
    with open(PREFS_PATH, "w") as f:
        json.dump(prefs, f, indent=2)
