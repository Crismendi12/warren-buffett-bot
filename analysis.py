"""
analysis.py — Warren Buffett scoring engine.

Each of the four principles returns a SectionResult with:
  - score     : points earned
  - max_score : maximum possible points
  - criteria  : list of CriterionResult (one per metric)

Every CriterionResult carries the raw value, the threshold description,
the points earned, and the source so the UI can display full transparency.

Scoring philosophy (from Buffett's letters and 'The Warren Buffett Way'):
  1. Moat     — Durable competitive advantage, measured via ROE and margins.
  2. Value    — Buy at a sensible price vs. intrinsic value (margin of safety).
  3. Health   — Conservative balance sheet; avoid heavy debt.
  4. Growth   — Consistent, compounding earnings and book value growth.
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Any, Optional, List
import metrics
import data_sources


@dataclass
class CriterionResult:
    name: str
    raw_value: Any
    raw_label: str          # human-readable formatted value
    threshold: str          # what criterion was applied
    source: str             # where the data comes from
    points_earned: int
    points_max: int
    passed: bool
    explanation: str        # full plain-language justification


@dataclass
class SectionResult:
    name: str
    score: int
    max_score: int
    criteria: List[CriterionResult] = field(default_factory=list)

    @property
    def pct(self) -> float:
        return self.score / self.max_score if self.max_score else 0


@dataclass
class AnalysisResult:
    symbol: str
    company_name: str
    sector: str
    industry: str
    current_price: Optional[float]
    market_cap: Optional[float]
    moat: SectionResult
    valuation: SectionResult
    health: SectionResult
    growth: SectionResult
    intrinsic_value: Optional[float] = None

    @property
    def total_score(self) -> int:
        return self.moat.score + self.valuation.score + self.health.score + self.growth.score

    @property
    def total_max(self) -> int:
        return self.moat.max_score + self.valuation.max_score + self.health.max_score + self.growth.max_score

    @property
    def total_pct(self) -> float:
        return self.total_score / self.total_max if self.total_max else 0

    @property
    def verdict(self) -> str:
        pct = self.total_pct * 100
        if pct >= 80:
            return "Candidato solido para inversion"
        elif pct >= 60:
            return "Vale la pena seguir de cerca"
        elif pct >= 40:
            return "Proceder con precaucion"
        else:
            return "No cumple criterios de Buffett"

    @property
    def verdict_color(self) -> str:
        pct = self.total_pct * 100
        if pct >= 80:
            return "green"
        elif pct >= 60:
            return "blue"
        elif pct >= 40:
            return "orange"
        else:
            return "red"

    @property
    def signal(self) -> tuple:
        score = self.total_score
        iv = self.intrinsic_value
        price = self.current_price
        buy_target = round(iv * 0.70, 2) if iv and iv > 0 else None
        sell_target = round(iv * 1.20, 2) if iv and iv > 0 else None
        margin = (iv - price) / iv if (iv and iv > 0 and price and price > 0) else None
        if score >= 75 and margin is not None and margin >= 0.35:
            return ("COMPRAR AGRESIVO", "#10b981", buy_target, sell_target)
        elif score >= 65 and margin is not None and margin >= 0.20:
            return ("COMPRAR", "#10b981", buy_target, sell_target)
        elif score >= 60 and margin is not None and margin >= 0.10:
            return ("ACUMULAR", "#3b82f6", buy_target, sell_target)
        elif score < 40 or (margin is not None and margin <= -0.40):
            return ("VENDER", "#ef4444", buy_target, sell_target)
        elif score < 55 or (margin is not None and margin < -0.15):
            return ("REDUCIR", "#f59e0b", buy_target, sell_target)
        elif score >= 55:
            return ("MANTENER", "#f59e0b", buy_target, sell_target)
        else:
            return ("EVALUAR", "#64748b", buy_target, sell_target)


def _fmt_pct(v) -> str:
    if v is None:
        return "N/A"
    return f"{v * 100:.1f}%"


def _fmt_ratio(v) -> str:
    if v is None:
        return "N/A"
    return f"{v:.2f}x"


def _fmt_num(v) -> str:
    if v is None:
        return "N/A"
    if abs(v) >= 1e9:
        return f"${v / 1e9:.1f}B"
    if abs(v) >= 1e6:
        return f"${v / 1e6:.1f}M"
    return f"${v:.0f}"


def _fmt_price(v) -> str:
    if v is None:
        return "N/A"
    return f"${v:.2f}"


# ---------------------------------------------------------------------------
# Section 1: Moat / Competitive Advantage  (25 pts)
# ---------------------------------------------------------------------------

def analyze_moat(symbol: str, info: dict) -> SectionResult:
    criteria = []

    # --- ROE > 15% in each of the last 5 years  (15 pts) ---
    roe_data = metrics.get_roe_history(symbol)
    roe_values = roe_data["values"]
    roe_years = roe_data["years"]

    if roe_values:
        qualifying = sum(1 for r in roe_values if r >= 0.15)
        total = len(roe_values)
        pts = round(15 * (qualifying / max(total, 1)))
        passed = qualifying == total
        yr_labels = ", ".join(
            f"{yr}: {r * 100:.1f}%" for yr, r in zip(roe_years, roe_values)
        )
        criteria.append(CriterionResult(
            name="ROE historico (retorno sobre patrimonio)",
            raw_value=roe_values,
            raw_label=f"{roe_values[0] * 100:.1f}% (ultimo ano)",
            threshold="ROE >= 15% en cada uno de los ultimos 5 anos",
            source=f"yfinance income statement + balance sheet — {min(roe_years) if roe_years else 'N/A'} a {max(roe_years) if roe_years else 'N/A'}",
            points_earned=pts,
            points_max=15,
            passed=passed,
            explanation=(
                f"ROE por ano: {yr_labels}. "
                f"{qualifying} de {total} anos cumplen el umbral del 15%. "
                "Buffett busca ROE alto y sostenido como sena de ventaja competitiva duradera. "
                f"Puntos: {pts}/15."
            ),
        ))
    else:
        criteria.append(CriterionResult(
            name="ROE historico",
            raw_value=None,
            raw_label="N/A",
            threshold="ROE >= 15% en los ultimos 5 anos",
            source="yfinance — datos no disponibles",
            points_earned=0,
            points_max=15,
            passed=False,
            explanation="No se pudieron obtener datos de ROE historico. 0/15 pts.",
        ))

    # --- Net margin > 15%  (5 pts) ---
    net_margin = info.get("profitMargins")
    if net_margin is not None:
        pts = 5 if net_margin >= 0.15 else (3 if net_margin >= 0.08 else 0)
        criteria.append(CriterionResult(
            name="Margen neto",
            raw_value=net_margin,
            raw_label=_fmt_pct(net_margin),
            threshold=">= 15% para puntuacion completa, >= 8% parcial",
            source="yfinance info['profitMargins'] — ultimos 12 meses",
            points_earned=pts,
            points_max=5,
            passed=net_margin >= 0.15,
            explanation=(
                f"Margen neto actual: {_fmt_pct(net_margin)}. "
                "Un margen alto indica poder de fijacion de precios y eficiencia operativa, "
                "caracteristicas que Buffett asocia con negocios excepcionales. "
                f"Puntos: {pts}/5."
            ),
        ))
    else:
        criteria.append(CriterionResult(
            name="Margen neto",
            raw_value=None,
            raw_label="N/A",
            threshold=">= 15%",
            source="yfinance — datos no disponibles",
            points_earned=0,
            points_max=5,
            passed=False,
            explanation="Margen neto no disponible. 0/5 pts.",
        ))

    # --- Operating margin stability (std dev < 5pp over 5y)  (5 pts) ---
    op_margin_data = metrics.get_operating_margin_history(symbol)
    op_values = op_margin_data["values"]
    op_years = op_margin_data["years"]

    if len(op_values) >= 2:
        std_dev = float(np.std(op_values)) * 100  # in percentage points
        pts = 5 if std_dev < 5 else (2 if std_dev < 10 else 0)
        yr_labels = ", ".join(
            f"{yr}: {v * 100:.1f}%" for yr, v in zip(op_years, op_values)
        )
        criteria.append(CriterionResult(
            name="Estabilidad del margen operativo",
            raw_value=std_dev,
            raw_label=f"Desv. estandar: {std_dev:.1f}pp",
            threshold="Desviacion estandar < 5pp (muy estable), < 10pp (aceptable)",
            source=f"yfinance financials — {min(op_years) if op_years else 'N/A'} a {max(op_years) if op_years else 'N/A'}",
            points_earned=pts,
            points_max=5,
            passed=std_dev < 5,
            explanation=(
                f"Margenes operativos por ano: {yr_labels}. "
                f"Desviacion estandar: {std_dev:.1f} puntos porcentuales. "
                "La estabilidad de margenes indica un negocio predecible con barreras de entrada solidas. "
                f"Puntos: {pts}/5."
            ),
        ))
    else:
        criteria.append(CriterionResult(
            name="Estabilidad del margen operativo",
            raw_value=None,
            raw_label="N/A",
            threshold="Desviacion estandar < 5pp",
            source="yfinance — datos insuficientes",
            points_earned=0,
            points_max=5,
            passed=False,
            explanation="Datos de margen operativo insuficientes para calcular estabilidad. 0/5 pts.",
        ))

    score = sum(c.points_earned for c in criteria)
    return SectionResult(name="Moat / Ventaja Competitiva", score=score, max_score=25, criteria=criteria)


# ---------------------------------------------------------------------------
# Section 2: Valuation / Intrinsic Value  (25 pts)
# ---------------------------------------------------------------------------

def _estimate_intrinsic_value(symbol: str, info: dict) -> Optional[float]:
    """
    Multi-model intrinsic value estimate using the median of up to 3 methods.

    Method 1 — Graham-Buffett (owner earnings):
      IV = (Owner Earnings / shares) * (8.5 + 2g)
      where g = 5-year EPS CAGR capped at 20%.
      Tends to be optimistic with high-growth companies.

    Method 2 — Graham Number (conservative ceiling):
      IV = sqrt(22.5 * EPS * BVPS)
      Benjamin Graham's maximum reasonable price. More conservative.

    Method 3 — PEG-implied (Lynch-style):
      IV = EPS * g_pct  (fair value is when P/E equals the growth rate)
      Simple but grounded in real earnings growth.

    Using the median of available estimates makes the result more robust than
    any single formula, and errs toward conservatism when estimates diverge.
    """
    try:
        income = metrics.get_income_statement(symbol)
        cf = metrics.get_cashflow(symbol)
        shares = info.get("sharesOutstanding")

        net_income_s = metrics.extract_series(income, ["Net Income", "NetIncome"])
        da_s = metrics.extract_series(cf, ["Depreciation", "Depreciation And Amortization"])
        capex_s = metrics.extract_series(cf, ["Capital Expenditure", "Capital Expenditures"])

        if net_income_s is None or shares is None or shares == 0:
            return None

        latest_year = sorted(net_income_s.index)[-1]
        ni = net_income_s.get(latest_year, 0) or 0
        da = (da_s.get(latest_year, 0) if da_s is not None else 0) or 0
        cx = (capex_s.get(latest_year, 0) if capex_s is not None else 0) or 0

        eps_hist = metrics.get_eps_history(symbol)
        eps_series = pd.Series(
            eps_hist["values"], index=eps_hist["years"]
        ) if eps_hist["values"] else None
        eps_cagr = metrics.compute_cagr(eps_series, years=5) if eps_series is not None else None
        g = max(0, min((eps_cagr or 0.05) * 100, 20))  # cap at 20%

        estimates = []

        # Method 1: Graham-Buffett owner earnings formula
        owner_earnings = ni + da + cx  # cx is negative in yfinance
        if owner_earnings > 0:
            oe_per_share = owner_earnings / shares
            iv1 = oe_per_share * (8.5 + 2 * g)
            if iv1 > 0:
                estimates.append(iv1)

        # Method 2: Graham Number — sqrt(22.5 * EPS * BVPS)
        eps_val  = metrics._safe(info.get("trailingEps"), float)
        bvps_val = metrics._safe(info.get("bookValue"), float)
        if eps_val and eps_val > 0 and bvps_val and bvps_val > 0:
            iv2 = (22.5 * eps_val * bvps_val) ** 0.5
            if iv2 > 0:
                estimates.append(iv2)

        # Method 3: PEG-implied — fair value when P/E equals growth rate (%)
        if eps_val and eps_val > 0 and g > 0:
            iv3 = eps_val * g  # g is already in % units (e.g. 12 for 12%)
            if iv3 > 0:
                estimates.append(iv3)

        if not estimates:
            return None

        # Return the median — more robust than any single estimate
        estimates_sorted = sorted(estimates)
        median_iv = estimates_sorted[len(estimates_sorted) // 2]
        return median_iv if median_iv > 0 else None

    except Exception:
        return None


def analyze_valuation(symbol: str, info: dict) -> SectionResult:
    criteria = []
    current_price = info.get("currentPrice") or info.get("regularMarketPrice")

    # --- P/E ratio  (10 pts) ---
    pe = info.get("trailingPE")
    if pe is not None and pe > 0:
        if pe <= 15:
            pts = 10
            verdict = "Excelente — precio muy atractivo"
        elif pe <= 25:
            pts = 5
            verdict = "Razonable — dentro del rango aceptable de Buffett"
        else:
            pts = 0
            verdict = "Elevado — paga prima significativa sobre ganancias"
        criteria.append(CriterionResult(
            name="Ratio Precio/Ganancias (P/E trailing)",
            raw_value=pe,
            raw_label=f"{pe:.1f}x",
            threshold="<= 15x: 10pts | <= 25x: 5pts | > 25x: 0pts",
            source="yfinance info['trailingPE'] — ultimos 12 meses (TTM)",
            points_earned=pts,
            points_max=10,
            passed=pe <= 25,
            explanation=(
                f"P/E actual: {pe:.1f}x. {verdict}. "
                "Buffett prefiere pagar precios razonables por empresas excelentes. "
                "Un P/E bajo puede indicar precio atractivo o crecimiento lento esperado. "
                f"Puntos: {pts}/10."
            ),
        ))
    else:
        criteria.append(CriterionResult(
            name="Ratio P/E",
            raw_value=None,
            raw_label="N/A",
            threshold="<= 15x ideal",
            source="yfinance — no disponible (puede ser perdida neta)",
            points_earned=0,
            points_max=10,
            passed=False,
            explanation=(
                "P/E no disponible. Puede indicar perdidas netas (EPS negativo), "
                "o datos faltantes en Yahoo Finance. 0/10 pts."
            ),
        ))

    # --- P/B ratio  (8 pts) ---
    pb = info.get("priceToBook")
    if pb is not None and pb > 0:
        if pb <= 1.5:
            pts = 8
            verdict = "Cotizando cerca o por debajo del valor contable"
        elif pb <= 3.0:
            pts = 4
            verdict = "Valoracion moderada respecto al patrimonio"
        else:
            pts = 0
            verdict = "Premium elevado sobre el valor contable"
        criteria.append(CriterionResult(
            name="Ratio Precio/Valor en Libros (P/B)",
            raw_value=pb,
            raw_label=f"{pb:.2f}x",
            threshold="<= 1.5x: 8pts | <= 3.0x: 4pts | > 3.0x: 0pts",
            source="yfinance info['priceToBook']",
            points_earned=pts,
            points_max=8,
            passed=pb <= 3.0,
            explanation=(
                f"P/B actual: {pb:.2f}x. {verdict}. "
                "El ratio P/B compara el precio de mercado con el valor contable (patrimonio por accion). "
                "Graham — mentor de Buffett — usaba P/B < 1.5 como criterio principal. "
                f"Puntos: {pts}/8."
            ),
        ))
    else:
        criteria.append(CriterionResult(
            name="Ratio P/B",
            raw_value=None,
            raw_label="N/A",
            threshold="<= 1.5x ideal",
            source="yfinance — no disponible",
            points_earned=0,
            points_max=8,
            passed=False,
            explanation="P/B no disponible. 0/8 pts.",
        ))

    # --- Margin of Safety (intrinsic value estimate)  (7 pts) ---
    iv = _estimate_intrinsic_value(symbol, info)
    if iv is not None and current_price is not None and current_price > 0:
        margin = (iv - current_price) / iv
        if current_price <= iv * 0.66:
            pts = 7
            verdict = f"Descuento de {margin * 100:.0f}% sobre valor intrinseco estimado"
        elif current_price <= iv:
            pts = 3
            verdict = f"Por debajo del valor intrinseco estimado (descuento {margin * 100:.0f}%)"
        else:
            pts = 0
            overpaid = ((current_price / iv) - 1) * 100
            verdict = f"Cotiza {overpaid:.0f}% por encima del valor intrinseco estimado"
        criteria.append(CriterionResult(
            name="Margen de seguridad (DCF simplificado)",
            raw_value=iv,
            raw_label=f"IV estimado: {_fmt_price(iv)} | Precio actual: {_fmt_price(current_price)}",
            threshold="Precio <= 66% del IV: 7pts | Precio < IV: 3pts | Precio > IV: 0pts",
            source=(
                "Formula de Graham adaptada: IV = Owner Earnings/accion * (8.5 + 2*g). "
                "Owner Earnings = Net Income + D&A - CapEx. g = CAGR de EPS a 5 anos."
            ),
            points_earned=pts,
            points_max=7,
            passed=current_price <= iv,
            explanation=(
                f"Valor intrinseco estimado: {_fmt_price(iv)} por accion. "
                f"Precio actual: {_fmt_price(current_price)}. {verdict}. "
                "Esta estimacion es indicativa — no es una valoracion profesional. "
                "Buffett exige un 'margen de seguridad' para protegerse del error de estimacion. "
                f"Puntos: {pts}/7."
            ),
        ))
    else:
        criteria.append(CriterionResult(
            name="Margen de seguridad",
            raw_value=None,
            raw_label="No calculable",
            threshold="Precio <= 66% del IV estimado",
            source="Datos insuficientes para DCF simplificado",
            points_earned=0,
            points_max=7,
            passed=False,
            explanation=(
                "No se pudo estimar el valor intrinseco por falta de datos de "
                "flujo de caja, ganancias o precio. 0/7 pts."
            ),
        ))

    score = sum(c.points_earned for c in criteria)
    return SectionResult(name="Valoracion / Valor Intrinseco", score=score, max_score=25, criteria=criteria)


# ---------------------------------------------------------------------------
# Section 3: Debt / Financial Health  (25 pts)
# ---------------------------------------------------------------------------

def analyze_health(symbol: str, info: dict) -> SectionResult:
    criteria = []

    # --- Debt/Equity ratio  (10 pts) ---
    de = info.get("debtToEquity")
    if de is not None:
        de_ratio = de / 100  # yfinance returns as percentage
        if de_ratio < 0.5:
            pts = 10
            verdict = "Deuda muy conservadora"
        elif de_ratio < 1.0:
            pts = 5
            verdict = "Deuda moderada"
        else:
            pts = 0
            verdict = "Deuda elevada — mayor riesgo financiero"
        criteria.append(CriterionResult(
            name="Ratio Deuda/Patrimonio (D/E)",
            raw_value=de_ratio,
            raw_label=f"{de_ratio:.2f}x",
            threshold="< 0.5x: 10pts | < 1.0x: 5pts | >= 1.0x: 0pts",
            source="yfinance info['debtToEquity'] (total debt / shareholders' equity)",
            points_earned=pts,
            points_max=10,
            passed=de_ratio < 1.0,
            explanation=(
                f"Ratio D/E: {de_ratio:.2f}x. {verdict}. "
                "Buffett prefiere empresas que financian su crecimiento con ganancias propias, "
                "no con deuda. Una deuda baja tambien da resiliencia en recesiones. "
                f"Puntos: {pts}/10."
            ),
        ))
    else:
        criteria.append(CriterionResult(
            name="Ratio Deuda/Patrimonio (D/E)",
            raw_value=None,
            raw_label="N/A",
            threshold="< 0.5x ideal",
            source="yfinance — no disponible",
            points_earned=0,
            points_max=10,
            passed=False,
            explanation="Ratio D/E no disponible. 0/10 pts.",
        ))

    # --- Current ratio  (8 pts) ---
    cr = info.get("currentRatio")
    if cr is not None:
        if cr >= 1.5:
            pts = 8
            verdict = "Liquidez solida — puede cubrir obligaciones a corto plazo holgadamente"
        elif cr >= 1.0:
            pts = 4
            verdict = "Liquidez aceptable — cubre obligaciones pero con margen ajustado"
        else:
            pts = 0
            verdict = "Liquidez insuficiente — riesgo de tension de efectivo"
        criteria.append(CriterionResult(
            name="Ratio de Liquidez Corriente (Current Ratio)",
            raw_value=cr,
            raw_label=f"{cr:.2f}x",
            threshold=">= 1.5x: 8pts | >= 1.0x: 4pts | < 1.0x: 0pts",
            source="yfinance info['currentRatio'] (activos corrientes / pasivos corrientes)",
            points_earned=pts,
            points_max=8,
            passed=cr >= 1.0,
            explanation=(
                f"Ratio de liquidez: {cr:.2f}x. {verdict}. "
                "Mide la capacidad de la empresa para pagar deudas que vencen en menos de 1 ano. "
                f"Puntos: {pts}/8."
            ),
        ))
    else:
        criteria.append(CriterionResult(
            name="Ratio de Liquidez Corriente",
            raw_value=None,
            raw_label="N/A",
            threshold=">= 1.5x ideal",
            source="yfinance — no disponible",
            points_earned=0,
            points_max=8,
            passed=False,
            explanation="Ratio de liquidez no disponible. 0/8 pts.",
        ))

    # --- Free Cash Flow positive  (7 pts) ---
    fcf_info = info.get("freeCashflow")
    fcf_hist = metrics.get_free_cashflow_history(symbol)

    fcf_val = fcf_info
    if fcf_val is None and fcf_hist["values"]:
        fcf_val = fcf_hist["values"][0]  # most recent

    if fcf_val is not None:
        pts = 7 if fcf_val > 0 else 0
        verdict = "Genera caja libre positiva" if fcf_val > 0 else "FCF negativo — consume mas caja de la que genera"
        criteria.append(CriterionResult(
            name="Flujo de Caja Libre (FCF)",
            raw_value=fcf_val,
            raw_label=_fmt_num(fcf_val),
            threshold="FCF > 0: 7pts | FCF <= 0: 0pts",
            source="yfinance info['freeCashflow'] o cashflow statement (Op. CF - CapEx)",
            points_earned=pts,
            points_max=7,
            passed=fcf_val > 0,
            explanation=(
                f"FCF: {_fmt_num(fcf_val)}. {verdict}. "
                "El flujo de caja libre es el dinero real que queda despues de inversiones en capital. "
                "Buffett lo llama 'owner earnings' y lo considera mas importante que el beneficio neto. "
                f"Puntos: {pts}/7."
            ),
        ))
    else:
        criteria.append(CriterionResult(
            name="Flujo de Caja Libre (FCF)",
            raw_value=None,
            raw_label="N/A",
            threshold="FCF > 0",
            source="yfinance — no disponible",
            points_earned=0,
            points_max=7,
            passed=False,
            explanation="FCF no disponible. 0/7 pts.",
        ))

    score = sum(c.points_earned for c in criteria)
    return SectionResult(name="Salud Financiera / Deuda", score=score, max_score=25, criteria=criteria)


# ---------------------------------------------------------------------------
# Section 4: Consistent Growth  (25 pts)
# ---------------------------------------------------------------------------

def analyze_growth(symbol: str) -> SectionResult:
    criteria = []

    # --- Revenue 5-year CAGR  (8 pts) ---
    rev_hist = metrics.get_revenue_history(symbol)
    rev_series = pd.Series(rev_hist["values"], index=rev_hist["years"]) if rev_hist["values"] else None
    rev_cagr = metrics.compute_cagr(rev_series, years=5)

    if rev_cagr is not None:
        if rev_cagr >= 0.10:
            pts = 8
            verdict = "Crecimiento de ingresos fuerte y consistente"
        elif rev_cagr >= 0.05:
            pts = 4
            verdict = "Crecimiento moderado de ingresos"
        else:
            pts = 0
            verdict = "Crecimiento de ingresos debil o negativo"
        criteria.append(CriterionResult(
            name="CAGR de Ingresos (5 anos)",
            raw_value=rev_cagr,
            raw_label=_fmt_pct(rev_cagr),
            threshold=">= 10%: 8pts | >= 5%: 4pts | < 5%: 0pts",
            source=f"yfinance financials — {min(rev_hist['years']) if rev_hist['years'] else 'N/A'} a {max(rev_hist['years']) if rev_hist['years'] else 'N/A'}",
            points_earned=pts,
            points_max=8,
            passed=rev_cagr >= 0.05,
            explanation=(
                f"CAGR de ingresos a 5 anos: {_fmt_pct(rev_cagr)}. {verdict}. "
                "El crecimiento de ingresos sostenido indica expansion del negocio y "
                "demanda creciente por los productos/servicios. "
                f"Puntos: {pts}/8."
            ),
        ))
    else:
        criteria.append(CriterionResult(
            name="CAGR de Ingresos",
            raw_value=None,
            raw_label="N/A",
            threshold=">= 10% ideal",
            source="yfinance — datos insuficientes",
            points_earned=0,
            points_max=8,
            passed=False,
            explanation="Datos de ingresos insuficientes para calcular CAGR. 0/8 pts.",
        ))

    # --- EPS 5-year CAGR  (9 pts) ---
    eps_hist = metrics.get_eps_history(symbol)
    eps_series = pd.Series(eps_hist["values"], index=eps_hist["years"]) if eps_hist["values"] else None
    eps_cagr = metrics.compute_cagr(eps_series, years=5)

    if eps_cagr is not None:
        if eps_cagr >= 0.10:
            pts = 9
            verdict = "Crecimiento de ganancias por accion excepcional"
        elif eps_cagr >= 0.05:
            pts = 5
            verdict = "Crecimiento de EPS moderado"
        else:
            pts = 0
            verdict = "Crecimiento de EPS debil o negativo"
        criteria.append(CriterionResult(
            name="CAGR de Ganancias por Accion — EPS (5 anos)",
            raw_value=eps_cagr,
            raw_label=_fmt_pct(eps_cagr),
            threshold=">= 10%: 9pts | >= 5%: 5pts | < 5%: 0pts",
            source=f"yfinance earnings/financials — {min(eps_hist['years']) if eps_hist['years'] else 'N/A'} a {max(eps_hist['years']) if eps_hist['years'] else 'N/A'}",
            points_earned=pts,
            points_max=9,
            passed=eps_cagr >= 0.05,
            explanation=(
                f"CAGR de EPS a 5 anos: {_fmt_pct(eps_cagr)}. {verdict}. "
                "El EPS es la metrica que mas directamente impacta el valor para el accionista. "
                "Buffett llama al crecimiento del EPS 'la locomotora del precio de la accion'. "
                f"Puntos: {pts}/9."
            ),
        ))
    else:
        criteria.append(CriterionResult(
            name="CAGR de EPS",
            raw_value=None,
            raw_label="N/A",
            threshold=">= 10% ideal",
            source="yfinance — datos insuficientes",
            points_earned=0,
            points_max=9,
            passed=False,
            explanation="Datos de EPS insuficientes para calcular CAGR. 0/9 pts.",
        ))

    # --- Book value per share 5-year CAGR  (8 pts) ---
    bvps_hist = metrics.get_book_value_history(symbol)
    bvps_series = pd.Series(bvps_hist["values"], index=bvps_hist["years"]) if bvps_hist["values"] else None
    bvps_cagr = metrics.compute_cagr(bvps_series, years=5)

    if bvps_cagr is not None:
        if bvps_cagr >= 0.07:
            pts = 8
            verdict = "Valor contable creciendo solidamente"
        elif bvps_cagr >= 0.03:
            pts = 4
            verdict = "Crecimiento lento del valor contable"
        else:
            pts = 0
            verdict = "Valor contable estancado o decreciendo"
        criteria.append(CriterionResult(
            name="CAGR del Valor en Libros por Accion (5 anos)",
            raw_value=bvps_cagr,
            raw_label=_fmt_pct(bvps_cagr),
            threshold=">= 7%: 8pts | >= 3%: 4pts | < 3%: 0pts",
            source=f"yfinance balance sheet — {min(bvps_hist['years']) if bvps_hist['years'] else 'N/A'} a {max(bvps_hist['years']) if bvps_hist['years'] else 'N/A'}",
            points_earned=pts,
            points_max=8,
            passed=bvps_cagr >= 0.03,
            explanation=(
                f"CAGR del BVPS a 5 anos: {_fmt_pct(bvps_cagr)}. {verdict}. "
                "Buffett usa el crecimiento del valor contable como proxy del crecimiento "
                "del valor intrinseco. En sus cartas anuales, siempre compara el BVPS de "
                "Berkshire con el S&P 500. "
                f"Puntos: {pts}/8."
            ),
        ))
    else:
        criteria.append(CriterionResult(
            name="CAGR del Valor en Libros por Accion",
            raw_value=None,
            raw_label="N/A",
            threshold=">= 7% ideal",
            source="yfinance — datos insuficientes",
            points_earned=0,
            points_max=8,
            passed=False,
            explanation="Datos de BVPS insuficientes para calcular CAGR. 0/8 pts.",
        ))

    score = sum(c.points_earned for c in criteria)
    return SectionResult(name="Crecimiento Consistente", score=score, max_score=25, criteria=criteria)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run(symbol: str) -> AnalysisResult:
    info = metrics.get_info(symbol)
    info = data_sources.enrich_info(symbol, info)

    company_name = info.get("longName") or info.get("shortName") or symbol.upper()
    sector = info.get("sector") or "N/A"
    industry = info.get("industry") or "N/A"
    current_price = info.get("currentPrice") or info.get("regularMarketPrice")
    market_cap = info.get("marketCap")

    moat = analyze_moat(symbol, info)
    valuation = analyze_valuation(symbol, info)
    health = analyze_health(symbol, info)
    growth = analyze_growth(symbol)
    iv = _estimate_intrinsic_value(symbol, info)

    return AnalysisResult(
        symbol=symbol.upper(),
        company_name=company_name,
        sector=sector,
        industry=industry,
        current_price=current_price,
        market_cap=market_cap,
        moat=moat,
        valuation=valuation,
        health=health,
        growth=growth,
        intrinsic_value=iv,
    )
