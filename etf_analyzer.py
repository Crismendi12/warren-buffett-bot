"""
etf_analyzer.py — Dividend ETF quality scoring engine.

Scores dividend-paying ETFs across 5 pillars (100 pts total):
  - Rendimiento / Yield     (30 pts): yield actual + crecimiento del dividendo 3a
  - Costo                   (25 pts): expense ratio (menor = mejor)
  - Escala y Liquidez       (20 pts): activos bajo gestion (AUM)
  - Consistencia            (15 pts): anos pagando + sin recortes
  - Crecimiento total       (10 pts): retorno total 3 anos

Usage:
    result = etf_analyzer.run("SCHD")
    results = etf_analyzer.run_batch(["SCHD", "VYM", "VIG"])
"""

import logging
import time as _time
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

import yfinance as yf
import pandas as pd

logger = logging.getLogger(__name__)

# Popular dividend ETFs shown by default in the dashboard
POPULAR_ETFS: List[str] = [
    "SCHD", "VYM", "VIG", "DGRO", "HDV",
    "DVY", "NOBL", "SDY", "JEPI", "DIVO",
    "IDV", "PEY", "FVD", "FDVV", "JEPQ",
]


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ETFCriterion:
    name: str
    points_earned: int
    points_max: int
    raw_value: Optional[float]
    raw_label: str
    threshold: str
    explanation: str
    passed: bool


@dataclass
class ETFSection:
    name: str
    score: int
    max_score: int
    criteria: List[ETFCriterion]

    @property
    def pct(self) -> float:
        return self.score / self.max_score if self.max_score else 0


@dataclass
class ETFAnalysis:
    symbol: str
    name: str
    category: str
    fund_family: str
    total_assets: Optional[float]
    expense_ratio: Optional[float]
    dividend_yield: Optional[float]
    dividend_growth_3y: Optional[float]
    distribution_frequency: str
    years_paying: int

    yield_section: ETFSection
    cost_section: ETFSection
    scale_section: ETFSection
    consistency_section: ETFSection
    growth_section: ETFSection

    total_score: int
    total_max: int = 100

    @property
    def total_pct(self) -> float:
        return self.total_score / self.total_max if self.total_max else 0

    @property
    def verdict(self) -> str:
        if self.total_score >= 80:
            return "ETF de primera clase"
        elif self.total_score >= 65:
            return "Buena opcion"
        elif self.total_score >= 50:
            return "Aceptable con reservas"
        else:
            return "No recomendado para dividendos"

    @property
    def verdict_color(self) -> str:
        if self.total_score >= 80:   return "#2ecc71"
        elif self.total_score >= 65: return "#3498db"
        elif self.total_score >= 50: return "#e67e22"
        else:                        return "#e74c3c"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _dividend_growth_cagr(dividends: pd.Series, years: int = 3) -> Optional[float]:
    """Annualized dividend growth over the past N years using annual sums."""
    if dividends is None or dividends.empty:
        return None
    try:
        annual = dividends.groupby(dividends.index.year).sum()
        if len(annual) < 2:
            return None
        recent = annual.tail(years + 1)
        if len(recent) < 2:
            return None
        start_val = float(recent.iloc[0])
        end_val   = float(recent.iloc[-1])
        n = len(recent) - 1
        if start_val <= 0:
            return None
        return (end_val / start_val) ** (1.0 / n) - 1.0
    except Exception:
        return None


def _years_paying(dividends: pd.Series) -> int:
    if dividends is None or dividends.empty:
        return 0
    try:
        return int(dividends.index.year.nunique())
    except Exception:
        return 0


def _no_cuts(dividends: pd.Series, years: int = 3) -> bool:
    """True if annual dividends have not been cut >20% in the past N years."""
    if dividends is None or dividends.empty:
        return False
    try:
        now = pd.Timestamp.now(tz="UTC")
        cutoff = now - pd.DateOffset(years=years)
        recent = dividends[dividends.index >= cutoff]
        if recent.empty:
            return False
        annual = recent.groupby(recent.index.year).sum()
        if len(annual) < 2:
            return True
        for i in range(1, len(annual)):
            prev = float(annual.iloc[i - 1])
            curr = float(annual.iloc[i])
            if prev > 0 and (curr / prev) < 0.80:
                return False
        return True
    except Exception:
        return False


def _distribution_freq(dividends: pd.Series) -> str:
    if dividends is None or dividends.empty:
        return "Desconocida"
    try:
        last_year = dividends[dividends.index.year == dividends.index.year.max()]
        count = len(last_year)
        if count >= 11:  return "Mensual"
        elif count >= 3: return "Trimestral"
        elif count >= 1: return "Anual"
        return "Desconocida"
    except Exception:
        return "Desconocida"


def _normalize_expense_ratio(er: Any) -> Optional[float]:
    """
    yfinance returns annualReportExpenseRatio in decimal form (0.0006 = 0.06%).
    If the value is absurdly large (>0.2 = 20%+), assume percentage and divide.
    """
    if er is None:
        return None
    er = float(er)
    if er <= 0:
        return None
    if er > 0.2:        # probably given as "6.0" meaning 6% — divide by 100
        er = er / 100
    return er


def _normalize_yield(info: dict) -> Optional[float]:
    """Get dividend yield in decimal form (0.035 = 3.5%)."""
    val = info.get("yield") or info.get("trailingAnnualDividendYield")
    if val is None:
        return None
    val = float(val)
    # yfinance returns in decimal form; sanity check
    if val > 1.0:   # e.g., returned as 3.5 instead of 0.035
        val = val / 100
    return val if val > 0 else None


# ---------------------------------------------------------------------------
# Scoring sections
# ---------------------------------------------------------------------------

def _score_yield(info: dict, dividends: pd.Series) -> ETFSection:
    criteria = []

    # 1. Current yield (20 pts)
    yld = _normalize_yield(info)
    if yld and yld >= 0.04:
        y_pts = 20
        y_exp = f"Yield del {yld*100:.2f}% — excelente generacion de renta."
    elif yld and yld >= 0.025:
        y_pts = 12
        y_exp = f"Yield del {yld*100:.2f}% — buen rendimiento para dividendos."
    elif yld and yld >= 0.015:
        y_pts = 6
        y_exp = f"Yield del {yld*100:.2f}% — rendimiento moderado."
    else:
        y_pts = 0
        y_exp = (f"Yield del {yld*100:.2f}% — muy bajo para ETF de dividendos." if yld
                 else "Sin datos de yield disponibles.")
    criteria.append(ETFCriterion(
        name="Dividend Yield actual",
        points_earned=y_pts, points_max=20,
        raw_value=yld,
        raw_label=f"{yld*100:.2f}%" if yld else "N/D",
        threshold=">4% = 20pts | >2.5% = 12pts | >1.5% = 6pts",
        explanation=y_exp,
        passed=y_pts >= 12,
    ))

    # 2. Dividend growth 3yr CAGR (10 pts)
    growth = _dividend_growth_cagr(dividends, years=3)
    if growth and growth >= 0.08:
        g_pts = 10
        g_exp = f"Crecimiento del dividendo al {growth*100:.1f}% anual (3a CAGR) — ritmo excelente que protege contra la inflacion."
    elif growth and growth >= 0.04:
        g_pts = 6
        g_exp = f"Crecimiento del dividendo al {growth*100:.1f}% anual — buen ritmo de crecimiento."
    elif growth and growth > 0:
        g_pts = 3
        g_exp = f"Crecimiento del dividendo al {growth*100:.1f}% anual — positivo pero modesto."
    else:
        g_pts = 0
        g_exp = (f"Dividendo sin crecimiento o en contraccion ({growth*100:.1f}% CAGR)." if growth is not None
                 else "Sin historial suficiente para calcular crecimiento del dividendo.")
    criteria.append(ETFCriterion(
        name="Crecimiento del dividendo (3a CAGR)",
        points_earned=g_pts, points_max=10,
        raw_value=growth,
        raw_label=f"{growth*100:.1f}% CAGR" if growth is not None else "N/D",
        threshold=">8% = 10pts | >4% = 6pts | >0% = 3pts",
        explanation=g_exp,
        passed=g_pts >= 6,
    ))

    total = sum(c.points_earned for c in criteria)
    return ETFSection("Rendimiento (Yield)", total, 30, criteria)


def _score_cost(info: dict) -> ETFSection:
    er_raw = info.get("annualReportExpenseRatio") or info.get("netExpenseRatio")
    er = _normalize_expense_ratio(er_raw)

    if er is not None and er < 0.0008:
        pts = 25
        exp = f"Expense ratio del {er*100:.3f}% — ultra bajo, practicamente gratuito."
    elif er is not None and er <= 0.0015:
        pts = 20
        exp = f"Expense ratio del {er*100:.3f}% — muy competitivo."
    elif er is not None and er <= 0.003:
        pts = 14
        exp = f"Expense ratio del {er*100:.2f}% — razonable para un ETF de dividendos."
    elif er is not None and er <= 0.005:
        pts = 8
        exp = f"Expense ratio del {er*100:.2f}% — aceptable pero existen alternativas mas baratas."
    elif er is not None and er <= 0.008:
        pts = 4
        exp = f"Expense ratio del {er*100:.2f}% — caro. Resta retorno a largo plazo."
    elif er is not None:
        pts = 0
        exp = f"Expense ratio del {er*100:.2f}% — muy alto para un ETF pasivo. Busca alternativas."
    else:
        pts = 0
        exp = "Sin datos de expense ratio. Verifica en el sitio del emisor antes de invertir."

    criterion = ETFCriterion(
        name="Ratio de Gastos (Expense Ratio)",
        points_earned=pts, points_max=25,
        raw_value=er,
        raw_label=f"{er*100:.3f}%" if er is not None else "N/D",
        threshold="<0.08% = 25pts | <0.15% = 20pts | <0.30% = 14pts | <0.50% = 8pts | <0.80% = 4pts",
        explanation=exp,
        passed=pts >= 14,
    )
    return ETFSection("Costo (Expense Ratio)", pts, 25, [criterion])


def _score_scale(info: dict) -> ETFSection:
    aum = info.get("totalAssets")
    if aum:
        aum = float(aum)

    if aum and aum >= 30e9:
        pts = 20
        exp = f"AUM de ${aum/1e9:.1f}B — ETF masivo, maxima liquidez y sin riesgo de cierre."
    elif aum and aum >= 10e9:
        pts = 16
        exp = f"AUM de ${aum/1e9:.1f}B — gran escala, alta liquidez."
    elif aum and aum >= 3e9:
        pts = 10
        exp = f"AUM de ${aum/1e9:.1f}B — escala adecuada para operar sin problemas."
    elif aum and aum >= 1e9:
        pts = 5
        exp = f"AUM de ${aum/1e6:.0f}M — pequeno pero operativo."
    elif aum:
        pts = 0
        exp = f"AUM de ${aum/1e6:.0f}M — muy pequeño. Riesgo de baja liquidez o cierre del ETF."
    else:
        pts = 0
        exp = "Sin datos de AUM. Verifica antes de invertir."

    criterion = ETFCriterion(
        name="Activos Bajo Gestion (AUM)",
        points_earned=pts, points_max=20,
        raw_value=aum,
        raw_label=(f"${aum/1e9:.1f}B" if aum and aum >= 1e9
                   else (f"${aum/1e6:.0f}M" if aum else "N/D")),
        threshold=">$30B = 20pts | >$10B = 16pts | >$3B = 10pts | >$1B = 5pts",
        explanation=exp,
        passed=pts >= 10,
    )
    return ETFSection("Escala y Liquidez (AUM)", pts, 20, [criterion])


def _score_consistency(dividends: pd.Series) -> ETFSection:
    criteria = []

    # 1. Years paying (10 pts)
    yrs = _years_paying(dividends)
    if yrs >= 10:
        yp_pts = 10
        yp_exp = f"Lleva {yrs} anos pagando dividendos — historial solido y probado en multiples ciclos economicos."
    elif yrs >= 5:
        yp_pts = 6
        yp_exp = f"Lleva {yrs} anos pagando dividendos — historial razonable."
    elif yrs >= 3:
        yp_pts = 3
        yp_exp = f"Solo {yrs} anos de historial — insuficiente para confirmar consistencia."
    else:
        yp_pts = 0
        yp_exp = f"Menos de 3 anos de historial de dividendos — muy corto."
    criteria.append(ETFCriterion(
        name="Anos pagando dividendos",
        points_earned=yp_pts, points_max=10,
        raw_value=float(yrs),
        raw_label=f"{yrs} anos",
        threshold=">10a = 10pts | >5a = 6pts | >3a = 3pts",
        explanation=yp_exp,
        passed=yp_pts >= 6,
    ))

    # 2. No cuts (5 pts)
    no_cut = _no_cuts(dividends, years=3)
    nc_pts = 5 if no_cut else 0
    nc_exp = ("Sin recortes del dividendo en los ultimos 3 anos. Distribucion estable." if no_cut
              else "Ha habido recortes significativos (>20%) en el dividendo en los ultimos 3 anos. Señal de alerta.")
    criteria.append(ETFCriterion(
        name="Sin recortes en 3 anos",
        points_earned=nc_pts, points_max=5,
        raw_value=1.0 if no_cut else 0.0,
        raw_label="Sin recortes" if no_cut else "Con recortes",
        threshold="Sin recortes = 5pts | Con recortes = 0pts",
        explanation=nc_exp,
        passed=no_cut,
    ))

    total = sum(c.points_earned for c in criteria)
    return ETFSection("Consistencia del Dividendo", total, 15, criteria)


def _score_growth(info: dict) -> ETFSection:
    r3y = info.get("threeYearAverageReturn")
    if r3y:
        r3y = float(r3y)

    if r3y and r3y >= 0.08:
        pts = 10
        exp = f"Retorno total anualizado 3a del {r3y*100:.1f}% — excelente apreciacion de capital ademas de los dividendos."
    elif r3y and r3y >= 0.05:
        pts = 6
        exp = f"Retorno total anualizado 3a del {r3y*100:.1f}% — bueno."
    elif r3y and r3y >= 0:
        pts = 3
        exp = f"Retorno total anualizado 3a del {r3y*100:.1f}% — positivo pero modesto."
    elif r3y is not None:
        pts = 0
        exp = f"Retorno total anualizado 3a del {r3y*100:.1f}% — negativo. Perdida de capital a pesar de los dividendos."
    else:
        pts = 0
        exp = "Sin datos de retorno total a 3 anos."

    criterion = ETFCriterion(
        name="Retorno Total Anualizado 3 anos",
        points_earned=pts, points_max=10,
        raw_value=r3y,
        raw_label=f"{r3y*100:.1f}%" if r3y is not None else "N/D",
        threshold=">8% = 10pts | >5% = 6pts | >0% = 3pts",
        explanation=exp,
        passed=pts >= 6,
    )
    return ETFSection("Crecimiento Total", pts, 10, [criterion])


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run(symbol: str) -> Optional[ETFAnalysis]:
    """Analyze a single dividend ETF. Returns None on error."""
    symbol = symbol.upper().strip()
    try:
        tk = yf.Ticker(symbol)
        info = tk.info or {}

        if not info or not info.get("longName"):
            logger.warning(f"{symbol}: no info returned from yfinance")
            return None

        dividends = tk.dividends  # pd.Series with DatetimeIndex (UTC)

        y_sec    = _score_yield(info, dividends)
        c_sec    = _score_cost(info)
        sc_sec   = _score_scale(info)
        co_sec   = _score_consistency(dividends)
        gr_sec   = _score_growth(info)

        total = y_sec.score + c_sec.score + sc_sec.score + co_sec.score + gr_sec.score

        return ETFAnalysis(
            symbol=symbol,
            name=info.get("longName") or info.get("shortName") or symbol,
            category=info.get("category") or "ETF",
            fund_family=info.get("fundFamily") or "—",
            total_assets=info.get("totalAssets"),
            expense_ratio=_normalize_expense_ratio(
                info.get("annualReportExpenseRatio") or info.get("netExpenseRatio")
            ),
            dividend_yield=_normalize_yield(info),
            dividend_growth_3y=_dividend_growth_cagr(dividends, 3),
            distribution_frequency=_distribution_freq(dividends),
            years_paying=_years_paying(dividends),
            yield_section=y_sec,
            cost_section=c_sec,
            scale_section=sc_sec,
            consistency_section=co_sec,
            growth_section=gr_sec,
            total_score=total,
        )
    except Exception as e:
        logger.error(f"Error analyzing ETF {symbol}: {e}")
        return None


def run_batch(
    symbols: List[str],
    progress_callback=None,
) -> Dict[str, Optional[ETFAnalysis]]:
    """Analyze multiple ETFs with optional per-ticker progress callback."""
    results: Dict[str, Optional[ETFAnalysis]] = {}
    total = len(symbols)
    for i, sym in enumerate(symbols):
        results[sym] = run(sym)
        if progress_callback:
            progress_callback(i + 1, total, sym)
        _time.sleep(0.4)   # be respectful to Yahoo Finance rate limits
    return results
