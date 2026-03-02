"""
metrics.py — Raw financial data extraction from yfinance.

All functions return None-safe values. Missing data is returned as None,
not raised as an exception, so callers can handle gaps gracefully.
"""

import yfinance as yf
import pandas as pd
from typing import Any, Optional, List


def _safe(value: Any, cast=None) -> Any:
    """Return None if value is falsy/NaN, optionally cast."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if cast is not None:
        try:
            return cast(value)
        except (TypeError, ValueError):
            return None
    return value


def get_ticker(symbol: str) -> yf.Ticker:
    return yf.Ticker(symbol.upper().strip())


def get_info(symbol: str) -> dict:
    """Return the yfinance .info dict, with all missing keys defaulting to None."""
    try:
        info = get_ticker(symbol).info
        if not info or info.get("trailingPE") is None and info.get("marketCap") is None:
            # yfinance returns a minimal dict for invalid tickers
            return {}
        return info
    except Exception:
        return {}


def get_income_statement(symbol: str) -> pd.DataFrame:
    """Annual income statement, columns = fiscal years (most recent first)."""
    try:
        df = get_ticker(symbol).financials
        return df if df is not None and not df.empty else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def get_balance_sheet(symbol: str) -> pd.DataFrame:
    try:
        df = get_ticker(symbol).balance_sheet
        return df if df is not None and not df.empty else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def get_cashflow(symbol: str) -> pd.DataFrame:
    try:
        df = get_ticker(symbol).cashflow
        return df if df is not None and not df.empty else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def get_price_history(symbol: str, period: str = "5y") -> pd.DataFrame:
    try:
        df = get_ticker(symbol).history(period=period)
        return df if df is not None and not df.empty else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def extract_series(df: pd.DataFrame, row_names: List[str]) -> Optional[pd.Series]:
    """
    Try each name in row_names until one is found in df.index.
    Returns a pd.Series indexed by year, most recent first, or None.
    """
    if df.empty:
        return None
    for name in row_names:
        matches = [idx for idx in df.index if name.lower() in str(idx).lower()]
        if matches:
            series = df.loc[matches[0]]
            series.index = pd.to_datetime(series.index).year
            return series.dropna()
    return None


def compute_cagr(series: pd.Series, years: int = 5) -> Optional[float]:
    """
    Compute CAGR over `years` periods from a time-indexed series.
    Returns None if insufficient data or start value <= 0.
    """
    if series is None or len(series) < 2:
        return None
    sorted_s = series.sort_index()
    available = min(years, len(sorted_s) - 1)
    if available < 1:
        return None
    start = sorted_s.iloc[-(available + 1)]
    end = sorted_s.iloc[-1]
    if start is None or end is None or start <= 0:
        return None
    try:
        return (end / start) ** (1 / available) - 1
    except (ZeroDivisionError, TypeError):
        return None


def get_roe_history(symbol: str) -> dict:
    """
    Returns dict with keys: values (list of floats), years (list of ints).
    ROE = Net Income / Shareholders' Equity.
    """
    income = get_income_statement(symbol)
    balance = get_balance_sheet(symbol)

    net_income = extract_series(income, ["Net Income", "NetIncome"])
    equity = extract_series(balance, ["Stockholders Equity", "Total Stockholders Equity",
                                      "Common Stock Equity", "Total Equity Gross Minority Interest"])

    if net_income is None or equity is None:
        return {"values": [], "years": []}

    common_years = sorted(set(net_income.index) & set(equity.index), reverse=True)[:5]
    roe_values = []
    years = []
    for yr in common_years:
        ni = net_income.get(yr)
        eq = equity.get(yr)
        if ni is not None and eq is not None and eq != 0:
            roe_values.append(ni / eq)
            years.append(yr)

    return {"values": roe_values, "years": years}


def get_revenue_history(symbol: str) -> dict:
    """Returns revenue series as {values: [...], years: [...]}."""
    income = get_income_statement(symbol)
    rev = extract_series(income, ["Total Revenue", "Revenue"])
    if rev is None or rev.empty:
        return {"values": [], "years": []}
    rev_sorted = rev.sort_index(ascending=True)
    return {"values": list(rev_sorted.values), "years": list(rev_sorted.index)}


def get_eps_history(symbol: str) -> dict:
    """EPS history derived from net income / shares outstanding."""
    income = get_income_statement(symbol)
    info = get_info(symbol)
    shares = _safe(info.get("sharesOutstanding"), float)
    net_income = extract_series(income, ["Net Income", "NetIncome"])
    if net_income is None or shares is None or shares == 0:
        return {"values": [], "years": []}
    eps = net_income / shares
    eps_sorted = eps.sort_index(ascending=True)
    return {"values": list(eps_sorted.values), "years": list(eps_sorted.index)}


def get_book_value_history(symbol: str) -> dict:
    """Book value per share history."""
    balance = get_balance_sheet(symbol)
    info = get_info(symbol)
    shares = _safe(info.get("sharesOutstanding"), float)
    equity = extract_series(balance, ["Stockholders Equity", "Total Stockholders Equity",
                                      "Common Stock Equity", "Total Equity Gross Minority Interest"])
    if equity is None or shares is None or shares == 0:
        return {"values": [], "years": []}
    bvps = equity / shares
    bvps_sorted = bvps.sort_index(ascending=True)
    return {"values": list(bvps_sorted.values), "years": list(bvps_sorted.index)}


def get_operating_margin_history(symbol: str) -> dict:
    """Operating margin = Operating Income / Total Revenue, per year."""
    income = get_income_statement(symbol)
    op_income = extract_series(income, ["Operating Income", "EBIT"])
    revenue = extract_series(income, ["Total Revenue", "Revenue"])
    if op_income is None or revenue is None:
        return {"values": [], "years": []}
    common_years = sorted(set(op_income.index) & set(revenue.index), reverse=True)[:5]
    values, years = [], []
    for yr in common_years:
        oi = op_income.get(yr)
        rv = revenue.get(yr)
        if oi is not None and rv is not None and rv != 0:
            values.append(oi / rv)
            years.append(yr)
    return {"values": values, "years": years}


def get_free_cashflow_history(symbol: str) -> dict:
    """FCF = Operating Cash Flow - CapEx, per year."""
    cf = get_cashflow(symbol)
    op_cf = extract_series(cf, ["Operating Cash Flow", "Total Cash From Operating Activities"])
    capex = extract_series(cf, ["Capital Expenditure", "Capital Expenditures"])
    if op_cf is None:
        return {"values": [], "years": []}

    common_years = sorted(op_cf.index, reverse=True)[:5]
    values, years = [], []
    for yr in common_years:
        ocf = op_cf.get(yr)
        cx = capex.get(yr) if capex is not None else 0
        if ocf is not None:
            cx = cx if cx is not None else 0
            values.append(ocf + cx)  # capex is negative in yfinance
            years.append(yr)
    return {"values": values, "years": years}


def get_price_metrics(symbol: str) -> dict:
    """
    Returns timing signals using already-available fields from yfinance .info.
    No extra API calls — all fields are fetched as part of the standard info dict.

    Fields computed:
    - pct_from_52w_low: 0% = at 52-week low, 100% = at 52-week high
    - dist_from_200dma_pct: negative = price is below the 200-day moving average
    - trend: 'alcista' if MA50 > MA200 (golden cross), 'bajista' otherwise
    """
    info = get_info(symbol)
    price  = _safe(info.get("currentPrice") or info.get("regularMarketPrice"), float) or 0
    high52 = _safe(info.get("fiftyTwoWeekHigh"), float) or 0
    low52  = _safe(info.get("fiftyTwoWeekLow"), float) or 0
    ma200  = _safe(info.get("twoHundredDayAverage"), float) or 0
    ma50   = _safe(info.get("fiftyDayAverage"), float) or 0

    pct_from_low = None
    if high52 > low52 and price > 0:
        pct_from_low = round((price - low52) / (high52 - low52) * 100, 1)

    dist_200 = None
    if ma200 > 0 and price > 0:
        dist_200 = round((price - ma200) / ma200 * 100, 1)

    trend = None
    if ma50 > 0 and ma200 > 0:
        trend = "alcista" if ma50 > ma200 else "bajista"

    return {
        "price": price,
        "high_52w": high52,
        "low_52w": low52,
        "pct_from_52w_low": pct_from_low,
        "dist_from_200dma_pct": dist_200,
        "ma_200": ma200,
        "ma_50": ma50,
        "trend": trend,
    }
