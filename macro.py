"""
macro.py — Macro environment indicators and their impact on Buffett analysis.

Fetches key macro data from yfinance (no API key needed) and interprets
how the current macro environment should affect the way you read the
Buffett scoring criteria.

Why macro matters for value investing:
  Buffett's criteria were calibrated in a specific interest rate regime.
  When rates are high, a P/E of 20 might be expensive; in a zero-rate
  environment it might be cheap. This module surfaces that context.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict
from datetime import datetime, timedelta

import yfinance as yf
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class MacroIndicator:
    name: str
    symbol: str           # yfinance symbol
    value: Optional[float]
    unit: str             # e.g. "%", "index", "USD"
    label: str            # formatted value for display
    change_1y: Optional[float]   # change vs 1 year ago
    interpretation: str   # plain language what this means right now
    impact_on_buffett: str  # how this affects the scoring criteria


@dataclass
class MacroEnvironment:
    as_of: str
    indicators: List[MacroIndicator]
    overall_summary: str
    key_alerts: List[str]  # important flags for the investor

    @property
    def rate_environment(self) -> str:
        ten_yr = next((i for i in self.indicators if i.symbol == "^TNX"), None)
        if ten_yr and ten_yr.value is not None:
            if ten_yr.value >= 5.0:
                return "tasas_muy_altas"
            elif ten_yr.value >= 3.5:
                return "tasas_altas"
            elif ten_yr.value >= 2.0:
                return "tasas_moderadas"
            else:
                return "tasas_bajas"
        return "desconocido"


def _fetch_latest(symbol: str) -> Optional[float]:
    try:
        t = yf.Ticker(symbol)
        hist = t.history(period="5d")
        if hist.empty:
            return None
        return float(hist["Close"].dropna().iloc[-1])
    except Exception:
        return None


def _fetch_value_1y_ago(symbol: str) -> Optional[float]:
    try:
        t = yf.Ticker(symbol)
        end = datetime.now()
        start = end - timedelta(days=375)
        hist = t.history(start=start.strftime("%Y-%m-%d"), end=(end - timedelta(days=350)).strftime("%Y-%m-%d"))
        if hist.empty:
            return None
        return float(hist["Close"].dropna().iloc[-1])
    except Exception:
        return None


def _fmt_pct(v: Optional[float]) -> str:
    if v is None:
        return "N/D"
    return f"{v:.2f}%"


def _fmt_idx(v: Optional[float]) -> str:
    if v is None:
        return "N/D"
    return f"{v:.0f}"


def _fmt_change(v: Optional[float], unit: str = "pp") -> str:
    if v is None:
        return ""
    sign = "+" if v >= 0 else ""
    return f"({sign}{v:.1f}{unit} vs hace 1 año)"


def fetch() -> MacroEnvironment:
    """Fetch all macro indicators and return a MacroEnvironment."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    indicators = []
    alerts = []

    # --- 10-Year US Treasury Yield ---
    tnx = _fetch_latest("^TNX")
    tnx_1y = _fetch_value_1y_ago("^TNX")
    tnx_change = (tnx - tnx_1y) if (tnx and tnx_1y) else None

    if tnx is not None:
        if tnx >= 5.0:
            tnx_interp = f"Tasas muy altas ({tnx:.2f}%). La renta fija compite directamente con la renta variable. El 'precio justo' de las acciones cae."
            tnx_impact = "El umbral de P/E se vuelve mas estricto. Un P/E de 18x ya es caro cuando puedes obtener 5%+ sin riesgo. Eleva el peso de la salud financiera (deuda mas cara)."
            alerts.append(f"Tasas al {tnx:.2f}%: exige mayor margen de seguridad en valoracion.")
        elif tnx >= 3.5:
            tnx_interp = f"Tasas elevadas ({tnx:.2f}%). El costo del dinero es alto. Empresas con deuda alta son castigadas."
            tnx_impact = "Ajusta mentalmente el P/E aceptable hacia abajo (~15-18x maximo). FCF positivo y baja deuda son aun mas criticos."
        elif tnx >= 2.0:
            tnx_interp = f"Tasas moderadas ({tnx:.2f}%). Entorno neutro para la renta variable."
            tnx_impact = "Los criterios de Buffett se aplican en su forma estandar. P/E hasta 25x puede ser razonable para empresas de alta calidad."
        else:
            tnx_interp = f"Tasas muy bajas ({tnx:.2f}%). El efectivo no rinde nada. La renta variable es la unica opcion real."
            tnx_impact = "P/E puede justificarse hasta 30x para empresas con moat fuerte. El crecimiento vale mas."
    else:
        tnx_interp = "No se pudo obtener el dato."
        tnx_impact = "Consulta manualmente la tasa del bono del Tesoro a 10 anos."

    indicators.append(MacroIndicator(
        name="Bono del Tesoro EE.UU. 10 Anos",
        symbol="^TNX",
        value=tnx,
        unit="%",
        label=_fmt_pct(tnx) + " " + _fmt_change(tnx_change),
        change_1y=tnx_change,
        interpretation=tnx_interp,
        impact_on_buffett=tnx_impact,
    ))

    # --- 2-Year Treasury (yield curve) ---
    irx = _fetch_latest("^IRX")  # 3-month
    tyx = _fetch_latest("^TYX")  # 30-year

    if tnx and irx:
        curve_slope = tnx - irx / 100 * tnx  # approximate; both in %
        # Actually ^IRX is already in % annualized
        curve = tnx - irx
        if curve < 0:
            curve_interp = f"Curva invertida ({curve:.2f}pp). Historicamente predice recesion en 6-18 meses."
            curve_impact = "Mayor riesgo de recesion: prioriza empresas con deuda baja, FCF alto y demanda inelastica (staples, healthcare)."
            alerts.append("Curva de rendimiento invertida: señal clasica de recesion.")
        elif curve < 0.5:
            curve_interp = f"Curva plana ({curve:.2f}pp). El mercado ve poco crecimiento futuro."
            curve_impact = "Cautela moderada. Las empresas con moat fuerte protegen mejor en slowdowns."
        else:
            curve_interp = f"Curva normal ({curve:.2f}pp). El mercado espera crecimiento economico."
            curve_impact = "Entorno favorable para acciones de crecimiento de calidad."

        indicators.append(MacroIndicator(
            name="Curva de Rendimiento (10Y - 3M)",
            symbol="^IRX",
            value=curve,
            unit="pp",
            label=f"{curve:.2f}pp",
            change_1y=None,
            interpretation=curve_interp,
            impact_on_buffett=curve_impact,
        ))

    # --- VIX (Fear index) ---
    vix = _fetch_latest("^VIX")
    vix_1y = _fetch_value_1y_ago("^VIX")
    vix_change = (vix - vix_1y) if (vix and vix_1y) else None

    if vix is not None:
        if vix >= 30:
            vix_interp = f"Miedo extremo en el mercado (VIX {vix:.0f}). Las valoraciones estan siendo castigadas."
            vix_impact = "Oportunidad Buffett: 'sé codicioso cuando otros tienen miedo'. Revisa si empresas de tu watchlist han caido sin razon fundamental."
            alerts.append(f"VIX alto ({vix:.0f}): posible ventana de compra en calidad.")
        elif vix >= 20:
            vix_interp = f"Incertidumbre moderada (VIX {vix:.0f}). Volatilidad por encima del promedio historico (~15)."
            vix_impact = "Buen momento para revisar precios vs. valor intrinseco. Los diferenciales se amplian."
        else:
            vix_interp = f"Mercado tranquilo (VIX {vix:.0f}). Baja volatilidad, alta complacencia."
            vix_impact = "Cuidado: mercados tranquilos tienden a estar 'caros'. Revisa que el margen de seguridad siga presente."

    else:
        vix_interp = "No disponible."
        vix_impact = "Consulta el VIX manualmente."

    indicators.append(MacroIndicator(
        name="VIX — Indice de Volatilidad (Fear Index)",
        symbol="^VIX",
        value=vix,
        unit="index",
        label=_fmt_idx(vix) + " " + _fmt_change(vix_change, unit=" pts"),
        change_1y=vix_change,
        interpretation=vix_interp,
        impact_on_buffett=vix_impact,
    ))

    # --- S&P 500 level (market valuation proxy) ---
    sp500 = _fetch_latest("^GSPC")
    sp500_1y = _fetch_value_1y_ago("^GSPC")
    sp500_change = ((sp500 / sp500_1y) - 1) * 100 if (sp500 and sp500_1y) else None

    if sp500 is not None:
        if sp500_change and sp500_change > 25:
            sp_interp = f"S&P 500 sube {sp500_change:.1f}% en un año. Mercado en expansion acelerada."
            sp_impact = "Los multiplos del mercado son altos. Ser mas selectivo: solo empresas con Buffett Score > 70."
        elif sp500_change and sp500_change < -10:
            sp_interp = f"S&P 500 baja {sp500_change:.1f}% en un año. Mercado en correccion."
            sp_impact = "Oportunidad para revisar calidad a precios reducidos."
        else:
            sp_interp = f"S&P 500 en {sp500:,.0f} puntos. Movimiento anual: {sp500_change:.1f}%."
            sp_impact = "Entorno de mercado normal. Aplica criterios Buffett estandar."
    else:
        sp_interp = sp_impact = "No disponible."

    indicators.append(MacroIndicator(
        name="S&P 500",
        symbol="^GSPC",
        value=sp500,
        unit="index",
        label=f"{sp500:,.0f}" if sp500 else "N/D",
        change_1y=sp500_change,
        interpretation=sp_interp,
        impact_on_buffett=sp_impact,
    ))

    # --- US Dollar Index ---
    dxy = _fetch_latest("DX-Y.NYB")
    dxy_1y = _fetch_value_1y_ago("DX-Y.NYB")
    dxy_change = ((dxy / dxy_1y) - 1) * 100 if (dxy and dxy_1y) else None

    if dxy is not None:
        if dxy_change and dxy_change > 10:
            dxy_interp = f"Dolar muy fuerte ({dxy:.1f}, +{dxy_change:.1f}% en 1 año). Penaliza ganancias de multinacionales en el exterior."
            dxy_impact = "Descuenta en empresas muy exportadoras o con ingresos fuera de EEUU. Empresas domesticas (retailers, utilities) se benefician relativamente."
        elif dxy_change and dxy_change < -10:
            dxy_interp = f"Dolar debil ({dxy:.1f}, {dxy_change:.1f}% en 1 año). Beneficia exportadores y mercados emergentes."
            dxy_impact = "Buen momento para acciones con ingresos globales. Los mercados emergentes en LatAm/Asia tienden a subir con dolar debil."
        else:
            dxy_interp = f"Dolar estable ({dxy:.1f})."
            dxy_impact = "Impacto cambiario neutro en el analisis."
    else:
        dxy_interp = dxy_impact = "No disponible."

    indicators.append(MacroIndicator(
        name="Indice del Dolar (DXY)",
        symbol="DX-Y.NYB",
        value=dxy,
        unit="index",
        label=f"{dxy:.1f}" if dxy else "N/D",
        change_1y=dxy_change,
        interpretation=dxy_interp,
        impact_on_buffett=dxy_impact,
    ))

    # --- Gold ---
    gold = _fetch_latest("GC=F")
    gold_1y = _fetch_value_1y_ago("GC=F")
    gold_change = ((gold / gold_1y) - 1) * 100 if (gold and gold_1y) else None

    if gold and gold_change is not None:
        if gold_change > 20:
            gold_interp = f"Oro en alza fuerte ({gold:,.0f} USD, +{gold_change:.1f}%). Señal de busqueda de refugio o expectativas de inflacion alta."
            gold_impact = "Confirma entorno de incertidumbre. Las empresas con moat real actuan como 'oro industrial'."
        elif gold_change < -10:
            gold_interp = f"Oro cayendo ({gold:,.0f} USD, {gold_change:.1f}%). Menor demanda de cobertura."
            gold_impact = "Menor miedo en el mercado. Entorno favorable para acciones de calidad."
        else:
            gold_interp = f"Oro estable ({gold:,.0f} USD)."
            gold_impact = "Impacto neutro."
    else:
        gold_interp = gold_impact = "No disponible."

    indicators.append(MacroIndicator(
        name="Oro (Futuros)",
        symbol="GC=F",
        value=gold,
        unit="USD/oz",
        label=f"${gold:,.0f}" if gold else "N/D",
        change_1y=gold_change,
        interpretation=gold_interp,
        impact_on_buffett=gold_impact,
    ))

    # --- Overall summary ---
    if tnx and tnx >= 4.0 and vix and vix >= 25:
        summary = (
            "Entorno DIFICIL para acciones: tasas altas + miedo elevado. "
            "Exige maxima calidad: Buffett Score > 70, deuda minima, FCF positivo. "
            "El margen de seguridad debe ser mayor al habitual (>40%)."
        )
    elif tnx and tnx <= 2.5 and vix and vix <= 15:
        summary = (
            "Entorno COMPLACIENTE: tasas bajas + mercado tranquilo. "
            "Las valoraciones son generalmente altas. Sé paciente. "
            "Buffett en este entorno suele acumular caja y esperar."
        )
    elif vix and vix >= 30:
        summary = (
            "VOLATILIDAD EXTREMA: momento de cazar oportunidades en calidad. "
            "Revisa tu watchlist: ¿cayeron las empresas por panico o por fundamentos?"
        )
    else:
        summary = (
            "Entorno MODERADO. Aplica los criterios Buffett estandar. "
            "Busca empresas con Moat fuerte, valoracion razonable y crecimiento consistente."
        )

    return MacroEnvironment(
        as_of=now,
        indicators=indicators,
        overall_summary=summary,
        key_alerts=alerts,
    )
