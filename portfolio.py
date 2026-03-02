"""
portfolio.py — Portfolio-level analysis.

Lets the user define their holdings (ticker + weight %) and computes:
  - Weighted Buffett score
  - Sector/region/score-category distribution
  - Diversification assessment
  - Aggregate health indicators
  - Cost basis, unrealized P&L and annualized return per holding
  - Alpha vs S&P500 since oldest entry date
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import List, Optional, Dict

PORTFOLIO_PATH = os.path.join(os.path.dirname(__file__), "data", "portfolio.json")


@dataclass
class Holding:
    symbol: str
    weight: float                          # 0.0 – 1.0
    company_name: str = ""
    sector: str = ""
    buffett_score: Optional[int] = None
    verdict: str = ""
    current_price: Optional[float] = None
    market_cap: Optional[float] = None
    entry_price: Optional[float] = None    # cost basis per share
    entry_date: Optional[str] = None       # ISO "YYYY-MM-DD"
    unrealized_pnl_pct: Optional[float] = None
    annualized_return_pct: Optional[float] = None


@dataclass
class PortfolioAnalysis:
    holdings: List[Holding]
    total_weight: float
    weighted_score: Optional[float]
    sector_weights: Dict[str, float]
    score_category_weights: Dict[str, float]  # "Solido", "Radar", "Precaucion", "Descartado"
    top_holding: Optional[Holding]
    weakest_holding: Optional[Holding]
    diversification_score: str   # "Alta", "Moderada", "Baja"
    alerts: List[str]
    summary: str
    sp500_return_pct: Optional[float] = None   # annualized S&P500 since oldest entry
    portfolio_alpha: Optional[float] = None    # portfolio annualized - sp500 annualized


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def load() -> List[dict]:
    """Load portfolio holdings as list of dicts."""
    os.makedirs(os.path.dirname(PORTFOLIO_PATH), exist_ok=True)
    if not os.path.exists(PORTFOLIO_PATH):
        return []
    try:
        with open(PORTFOLIO_PATH) as f:
            data = json.load(f)
        return data.get("holdings", [])
    except (json.JSONDecodeError, IOError):
        return []


def save(holdings: List[dict]) -> None:
    """Save portfolio holdings."""
    os.makedirs(os.path.dirname(PORTFOLIO_PATH), exist_ok=True)
    # Normalize weights
    total = sum(h.get("weight", 0) for h in holdings)
    if total > 0:
        for h in holdings:
            h["weight"] = round(h["weight"] / total, 4)
    with open(PORTFOLIO_PATH, "w") as f:
        json.dump({"holdings": holdings}, f, indent=2)


def upsert(symbol: str, weight_pct: float) -> None:
    """Add or update a holding. weight_pct is 0-100."""
    holdings = load()
    symbol = symbol.upper().strip()
    for h in holdings:
        if h["symbol"] == symbol:
            h["weight"] = weight_pct / 100
            save(holdings)
            return
    holdings.append({"symbol": symbol, "weight": weight_pct / 100})
    save(holdings)


def upsert_with_basis(symbol: str, weight_pct: float,
                      entry_price: Optional[float] = None,
                      entry_date: Optional[str] = None) -> None:
    """Add or update a holding with optional cost basis. weight_pct is 0-100."""
    holdings = load()
    symbol = symbol.upper().strip()
    for h in holdings:
        if h["symbol"] == symbol:
            h["weight"] = weight_pct / 100
            if entry_price is not None:
                h["entry_price"] = entry_price
            if entry_date is not None:
                h["entry_date"] = entry_date
            save(holdings)
            return
    new_h: dict = {"symbol": symbol, "weight": weight_pct / 100}
    if entry_price is not None:
        new_h["entry_price"] = entry_price
    if entry_date is not None:
        new_h["entry_date"] = entry_date
    holdings.append(new_h)
    save(holdings)


def remove(symbol: str) -> bool:
    symbol = symbol.upper().strip()
    holdings = load()
    new = [h for h in holdings if h["symbol"] != symbol]
    if len(new) == len(holdings):
        return False
    save(new)
    return True


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def analyze() -> Optional[PortfolioAnalysis]:
    """
    Build a PortfolioAnalysis from the saved holdings + batch cache.
    Returns None if portfolio is empty.
    """
    import batch as batch_module
    import yfinance as yf

    raw = load()
    if not raw:
        return None

    cache_results = batch_module.load_cache().get("results", {})
    total_raw_weight = sum(h.get("weight", 0) for h in raw)

    holdings: List[Holding] = []
    for h in raw:
        sym = h["symbol"].upper()
        w = h.get("weight", 0)
        if total_raw_weight > 0:
            w = w / total_raw_weight  # normalize to sum=1

        cached = cache_results.get(sym)
        if cached and not cached.get("blocked") and not cached.get("error"):
            holdings.append(Holding(
                symbol=sym,
                weight=w,
                company_name=cached.get("company_name", sym),
                sector=cached.get("sector", "N/A"),
                buffett_score=cached.get("total_score"),
                verdict=cached.get("verdict", ""),
                current_price=cached.get("current_price"),
                market_cap=cached.get("market_cap"),
            ))
        else:
            holdings.append(Holding(
                symbol=sym,
                weight=w,
                company_name=sym,
                sector="Sin analisis",
                buffett_score=None,
                verdict="Pendiente de analisis",
            ))

    if not holdings:
        return None

    # --- Cost basis & P&L ---
    today = date.today()
    raw_by_sym = {h["symbol"].upper(): h for h in raw}

    for holding in holdings:
        raw_h = raw_by_sym.get(holding.symbol, {})
        ep = raw_h.get("entry_price")
        ed = raw_h.get("entry_date")
        holding.entry_price = float(ep) if ep is not None else None
        holding.entry_date = ed if isinstance(ed, str) else None

        if holding.entry_price and holding.current_price and holding.entry_price > 0:
            pnl = (holding.current_price - holding.entry_price) / holding.entry_price
            holding.unrealized_pnl_pct = round(pnl * 100, 2)
            if holding.entry_date:
                try:
                    entry_dt = datetime.strptime(holding.entry_date, "%Y-%m-%d").date()
                    days = (today - entry_dt).days
                    if days > 1:
                        years = days / 365.25
                        annual = ((1 + pnl) ** (1.0 / years) - 1) * 100
                        holding.annualized_return_pct = round(annual, 2)
                except (ValueError, ZeroDivisionError):
                    pass

    # --- Alpha vs S&P500 ---
    sp500_return_pct: Optional[float] = None
    portfolio_alpha: Optional[float] = None

    dated = [h for h in holdings if h.entry_date and h.annualized_return_pct is not None]
    if dated:
        try:
            oldest_date_str = min(h.entry_date for h in dated)
            spy_hist = yf.download(
                "^GSPC", start=oldest_date_str, end=str(today),
                auto_adjust=True, progress=False
            )
            if spy_hist is not None and not spy_hist.empty:
                # yfinance 1.x may return MultiIndex columns even for a single ticker
                import pandas as _pd_port
                if isinstance(spy_hist.columns, _pd_port.MultiIndex):
                    spy_hist.columns = spy_hist.columns.get_level_values(-1)
                sp_start = float(spy_hist["Close"].iloc[0])
                sp_end   = float(spy_hist["Close"].iloc[-1])
                oldest_date = datetime.strptime(oldest_date_str, "%Y-%m-%d").date()
                years_total = (today - oldest_date).days / 365.25
                if years_total > 0:
                    sp_total = (sp_end - sp_start) / sp_start
                    sp500_annual = ((1 + sp_total) ** (1.0 / years_total) - 1) * 100
                    sp500_return_pct = round(sp500_annual, 2)

                    # Weighted portfolio annualized return
                    total_w = sum(h.weight for h in dated)
                    if total_w > 0:
                        port_annual = sum(
                            h.annualized_return_pct * h.weight for h in dated
                        ) / total_w
                        portfolio_alpha = round(port_annual - sp500_annual, 2)
        except Exception:
            pass

    # --- Weighted Buffett score ---
    scored = [h for h in holdings if h.buffett_score is not None]
    if scored:
        scored_weight = sum(h.weight for h in scored)
        weighted_score = (
            sum(h.buffett_score * h.weight for h in scored) / scored_weight
            if scored_weight > 0 else None
        )
    else:
        weighted_score = None

    # --- Sector distribution ---
    sector_weights: Dict[str, float] = {}
    for h in holdings:
        sector_weights[h.sector] = sector_weights.get(h.sector, 0) + h.weight

    # --- Score category distribution ---
    cat_weights: Dict[str, float] = {
        "Candidato solido": 0, "En radar": 0,
        "Con precaucion": 0, "No cumple": 0, "Sin analisis": 0,
    }
    for h in holdings:
        if h.buffett_score is None:
            cat_weights["Sin analisis"] += h.weight
        elif h.buffett_score >= 80:
            cat_weights["Candidato solido"] += h.weight
        elif h.buffett_score >= 60:
            cat_weights["En radar"] += h.weight
        elif h.buffett_score >= 40:
            cat_weights["Con precaucion"] += h.weight
        else:
            cat_weights["No cumple"] += h.weight

    # --- Top and weakest ---
    scored_sorted = sorted(scored, key=lambda h: h.buffett_score, reverse=True)
    top  = scored_sorted[0]  if scored_sorted else None
    weak = scored_sorted[-1] if scored_sorted else None

    # --- Diversification ---
    num_sectors = len([s for s, w in sector_weights.items() if w > 0.05])
    max_weight = max(h.weight for h in holdings) if holdings else 1.0
    if num_sectors >= 5 and max_weight <= 0.25:
        divers = "Alta"
    elif num_sectors >= 3 and max_weight <= 0.40:
        divers = "Moderada"
    else:
        divers = "Baja"

    # --- Alerts ---
    alerts = []
    if max_weight > 0.30:
        top_h = max(holdings, key=lambda h: h.weight)
        alerts.append(f"Concentracion alta: {top_h.symbol} representa el {top_h.weight*100:.0f}% del portafolio.")
    if num_sectors < 3:
        alerts.append("Poca diversificacion sectorial. Considera empresas de sectores distintos.")
    weak_quality = cat_weights.get("No cumple", 0) + cat_weights.get("Con precaucion", 0)
    if weak_quality > 0.40:
        alerts.append(f"{weak_quality*100:.0f}% del portafolio en empresas de baja puntuacion Buffett.")
    if weighted_score and weighted_score < 50:
        alerts.append("El score ponderado del portafolio es bajo. Revisa las posiciones debiles.")

    # --- Summary ---
    if weighted_score:
        if weighted_score >= 70:
            summary = f"Portafolio de ALTA CALIDAD. Score ponderado: {weighted_score:.0f}/100. Diversificacion: {divers}."
        elif weighted_score >= 55:
            summary = f"Portafolio ACEPTABLE. Score ponderado: {weighted_score:.0f}/100. Hay margen de mejora."
        else:
            summary = f"Portafolio DEBIL segun criterios Buffett. Score ponderado: {weighted_score:.0f}/100. Revisa las posiciones."
    else:
        summary = f"Portafolio con {len(holdings)} posiciones. Ejecuta un analisis batch para ver scores."

    return PortfolioAnalysis(
        holdings=holdings,
        total_weight=sum(h.weight for h in holdings),
        weighted_score=weighted_score,
        sector_weights=sector_weights,
        score_category_weights={k: v for k, v in cat_weights.items() if v > 0},
        top_holding=top,
        weakest_holding=weak,
        diversification_score=divers,
        alerts=alerts,
        summary=summary,
        sp500_return_pct=sp500_return_pct,
        portfolio_alpha=portfolio_alpha,
    )
