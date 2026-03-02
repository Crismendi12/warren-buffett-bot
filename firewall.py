"""
firewall.py — Investment quality and ethics pre-screening gate.

Runs before any Buffett analysis. Returns a FirewallResult that tells the
app whether to PASS (full analysis), WARN (show analysis + banner), or
BLOCK (halt with explanation).

Why this exists:
  Buffett's methodology only works on businesses with real, measurable
  economics. Applying it to shell companies, leveraged ETFs, or penny stocks
  produces meaningless scores. The firewall prevents misleading output.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal, List
import metrics


# Sectors/industries flagged for ethical transparency.
# These are not automatically blocked — Buffett himself owns some of these —
# but the user deserves to know what they are analyzing.
ETHICS_FLAGGED_INDUSTRIES = {
    "tobacco", "cigarette", "alcohol", "beverage—brewers", "gambling",
    "casinos", "defense", "aerospace & defense", "weapons", "arms",
    "adult entertainment", "pornography",
}

# Sectors that yfinance returns which indicate non-equity instruments.
NON_EQUITY_TYPES = {
    "etf", "mutualfund", "index", "fund", "bond", "currency",
    "cryptocurrency", "futures", "option",
}

# Known inverse/leveraged ETF keyword signals in the short name
LEVERAGED_ETF_KEYWORDS = {"ultrashort", "ultra pro", "2x", "3x", "-2x", "-3x",
                           "inverse", "bear", "short", "direxion", "proshares ultra"}


@dataclass
class FirewallIssue:
    level: Literal["block", "warn"]
    code: str
    message: str
    detail: str


@dataclass
class FirewallResult:
    status: Literal["PASS", "WARN", "BLOCK"]
    issues: List[FirewallIssue] = field(default_factory=list)

    @property
    def block_issues(self) -> List[FirewallIssue]:
        return [i for i in self.issues if i.level == "block"]

    @property
    def warn_issues(self) -> List[FirewallIssue]:
        return [i for i in self.issues if i.level == "warn"]


def run(symbol: str) -> FirewallResult:
    """
    Run all firewall checks for the given ticker symbol.
    Returns a FirewallResult with status and a list of issues.
    """
    info = metrics.get_info(symbol)
    issues: List[FirewallIssue] = []

    # --- Check 1: Ticker must exist and return real data ---
    if not info:
        issues.append(FirewallIssue(
            level="block",
            code="INVALID_TICKER",
            message="Ticker no encontrado",
            detail=(
                f"'{symbol}' no devolvio datos validos de Yahoo Finance. "
                "Verifica que el ticker sea correcto (ej: AAPL, KO, MSFT)."
            ),
        ))
        return FirewallResult(status="BLOCK", issues=issues)

    quote_type = str(info.get("quoteType", "")).lower()
    short_name = str(info.get("shortName") or info.get("longName") or "").lower()

    # --- Check 2: Must be an equity (stock), not a fund/ETF/crypto ---
    if quote_type in NON_EQUITY_TYPES:
        issues.append(FirewallIssue(
            level="block",
            code="NOT_AN_EQUITY",
            message=f"Instrumento no analizable: {quote_type.upper()}",
            detail=(
                "El analisis de Buffett requiere una empresa con estados financieros reales. "
                f"'{symbol}' es un {quote_type.upper()}, no una accion individual. "
                "Busca empresas como KO, AAPL, JNJ."
            ),
        ))

    # --- Check 3: Detect leveraged/inverse ETFs by name ---
    if any(kw in short_name for kw in LEVERAGED_ETF_KEYWORDS):
        issues.append(FirewallIssue(
            level="block",
            code="LEVERAGED_ETF",
            message="ETF apalancado o inverso detectado",
            detail=(
                "Los ETFs apalancados/inversos no tienen fundamentales empresariales. "
                "Son instrumentos especulativos incompatibles con el analisis de valor."
            ),
        ))

    # --- Check 4: Market cap must be >= $300M ---
    market_cap = info.get("marketCap")
    if market_cap is not None and market_cap < 300_000_000:
        cap_m = market_cap / 1_000_000
        issues.append(FirewallIssue(
            level="block",
            code="MICRO_CAP",
            message=f"Capitalizacion muy baja: ${cap_m:.0f}M",
            detail=(
                f"Con una cap. de mercado de ${cap_m:.0f}M, esta empresa es micro/nano-cap. "
                "Los datos financieros suelen ser incompletos o poco fiables a esta escala. "
                "Buffett invierte en empresas con ventajas competitivas duraderas, "
                "lo que generalmente requiere escala significativa."
            ),
        ))

    # --- Check 5: Must have at least 3 years of income data ---
    income = metrics.get_income_statement(symbol)
    years_of_data = income.shape[1] if not income.empty else 0
    if years_of_data < 3:
        issues.append(FirewallIssue(
            level="block",
            code="INSUFFICIENT_HISTORY",
            message=f"Historial financiero insuficiente: {years_of_data} año(s)",
            detail=(
                "Se requieren al menos 3 anos de estados financieros anuales "
                "para evaluar consistencia y tendencias. "
                f"Solo se encontraron {years_of_data} periodo(s) para '{symbol}'."
            ),
        ))

    # --- Check 6: Negative book value (equity) ---
    book_value = info.get("bookValue")
    if book_value is not None and book_value < 0:
        issues.append(FirewallIssue(
            level="block",
            code="NEGATIVE_EQUITY",
            message="Patrimonio neto negativo",
            detail=(
                f"El valor en libros por accion es ${book_value:.2f} (negativo). "
                "Esto invalida el calculo de P/B y ROE. Puede indicar deuda excesiva "
                "o perdidas acumuladas. Buffett evita empresas con patrimonio negativo."
            ),
        ))

    # --- Check 7: Zero or missing revenue ---
    revenue_hist = metrics.get_revenue_history(symbol)
    if not revenue_hist["values"] or all(v == 0 for v in revenue_hist["values"]):
        issues.append(FirewallIssue(
            level="block",
            code="NO_REVENUE",
            message="Sin ingresos reportados",
            detail=(
                "No se encontraron ingresos en los estados financieros. "
                "Puede ser una empresa preoperacional, shell company, o un "
                "problema de datos en Yahoo Finance."
            ),
        ))

    # --- Check 8: High beta (warn only, not block) ---
    beta = info.get("beta")
    if beta is not None and beta > 4:
        issues.append(FirewallIssue(
            level="warn",
            code="HIGH_VOLATILITY",
            message=f"Volatilidad extrema: Beta = {beta:.2f}",
            detail=(
                f"Beta de {beta:.2f} indica una volatilidad muy superior al mercado. "
                "Buffett busca negocios predecibles ('dentro de su circulo de competencia'). "
                "Una beta tan alta sugiere especulacion o riesgo sectorial elevado. "
                "El analisis se muestra, pero con esta advertencia."
            ),
        ))

    # --- Check 9: Ethics / sector transparency flag ---
    industry = str(info.get("industry") or "").lower()
    sector = str(info.get("sector") or "").lower()
    combined = industry + " " + sector

    # Use word-boundary matching to avoid "alcohol" matching "non-alcoholic"
    import re
    flagged_terms = [
        term for term in ETHICS_FLAGGED_INDUSTRIES
        if re.search(r'\b' + re.escape(term) + r'\b', combined)
    ]
    if flagged_terms:
        issues.append(FirewallIssue(
            level="warn",
            code="ETHICS_FLAG",
            message=f"Sector con consideraciones eticas: {info.get('industry', 'N/A')}",
            detail=(
                f"Esta empresa opera en '{info.get('industry', sector)}', "
                "un sector que algunos inversores excluyen por razones eticas o de valores. "
                "El analisis financiero se aplica normalmente, pero considera si este "
                "tipo de negocio es compatible con tus principios de inversion."
            ),
        ))

    # --- Check 10: No price data ---
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    if price is None:
        issues.append(FirewallIssue(
            level="warn",
            code="NO_PRICE",
            message="Precio actual no disponible",
            detail=(
                "No se pudo obtener el precio actual de mercado. "
                "Los calculos de valoracion (P/E, P/B) pueden ser inexactos. "
                "Verifica que el mercado este abierto o que el ticker este activo."
            ),
        ))

    # --- Determine final status ---
    if any(i.level == "block" for i in issues):
        status = "BLOCK"
    elif any(i.level == "warn" for i in issues):
        status = "WARN"
    else:
        status = "PASS"

    return FirewallResult(status=status, issues=issues)
