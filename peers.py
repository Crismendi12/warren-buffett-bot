"""
peers.py — Sector peer comparison for contextualizing a company's metrics.

When analyzing a company, its absolute P/E or ROE means more when you know
how it compares to its industry peers. A P/E of 22 is expensive for a utility,
but cheap for a software company.

Strategy:
  1. From the batch results cache, find companies in the same sector/industry.
  2. If cache doesn't have enough peers, fetch a small set of representative
     sector ETFs or well-known peers using yfinance.
  3. Compute sector medians and percentiles.

Usage:
    comparison = peers.compare("AAPL", info, analysis_result)
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict
import statistics

import yfinance as yf

import batch as batch_module

logger = logging.getLogger(__name__)


# Sector representative tickers — used when cache doesn't have enough peers.
# These are well-known, liquid companies that represent each sector.
SECTOR_PEERS: Dict[str, List[str]] = {
    "Technology": ["AAPL", "MSFT", "GOOGL", "NVDA", "AVGO", "TXN", "INTC", "QCOM", "ADI", "KLAC"],
    "Healthcare": ["JNJ", "UNH", "LLY", "ABBV", "MRK", "TMO", "ABT", "DHR", "BMY", "AMGN"],
    "Consumer Defensive": ["PG", "KO", "PEP", "WMT", "COST", "CL", "GIS", "K", "SJM", "HRL"],
    "Consumer Cyclical": ["AMZN", "HD", "NKE", "MCD", "SBUX", "TGT", "LOW", "TJX", "ROST", "CMG"],
    "Financial Services": ["JPM", "BAC", "WFC", "GS", "MS", "BLK", "AXP", "MCO", "SPGI", "ICE"],
    "Industrials": ["HON", "GE", "CAT", "MMM", "EMR", "ITW", "PH", "ROK", "AME", "ROP"],
    "Communication Services": ["GOOGL", "META", "NFLX", "DIS", "CMCSA", "VZ", "T", "TMUS", "CHTR", "WBD"],
    "Energy": ["XOM", "CVX", "COP", "EOG", "SLB", "OXY", "DVN", "MPC", "VLO", "PSX"],
    "Utilities": ["NEE", "DUK", "SO", "D", "AEP", "EXC", "XEL", "WEC", "ES", "ETR"],
    "Real Estate": ["AMT", "PLD", "EQIX", "CCI", "DLR", "SPG", "O", "AVB", "EQR", "VTR"],
    "Basic Materials": ["LIN", "APD", "ECL", "SHW", "FCX", "NEM", "NUE", "CF", "MOS", "ALB"],
}


@dataclass
class PeerMetric:
    name: str
    company_value: Optional[float]
    company_label: str
    sector_median: Optional[float]
    sector_label: str
    percentile: Optional[int]  # company's percentile in sector (0-100, higher = better if higher is good)
    better_than_peers: Optional[bool]
    note: str  # plain language comparison


@dataclass
class PeerComparison:
    sector: str
    industry: str
    peer_count: int
    peer_symbols: List[str]
    metrics: List[PeerMetric]
    summary: str


def _get_metric(info: dict, key: str, divisor: float = 1.0) -> Optional[float]:
    v = info.get(key)
    if v is None:
        return None
    try:
        return float(v) / divisor
    except (TypeError, ValueError):
        return None


def _percentile(value: float, values: List[float]) -> int:
    """Return what percentage of values are below `value`."""
    if not values:
        return 50
    below = sum(1 for v in values if v < value)
    return round(below / len(values) * 100)


def _fmt(v: Optional[float], fmt: str = ".1f", suffix: str = "") -> str:
    if v is None:
        return "N/D"
    return f"{v:{fmt}}{suffix}"


def compare(symbol: str, info: dict, cached_result: Optional[dict] = None) -> PeerComparison:
    """
    Build a peer comparison for the given company.
    Uses batch cache where possible, fetches from yfinance if needed.
    """
    sector = info.get("sector") or "Unknown"
    industry = info.get("industry") or "Unknown"

    # --- Get peer tickers ---
    peers_from_cache = _peers_from_cache(sector, symbol)
    sector_fallback = SECTOR_PEERS.get(sector, [])
    # Combine: prefer cache peers, fill with sector fallback
    all_peers = list(dict.fromkeys(peers_from_cache + sector_fallback))
    all_peers = [p for p in all_peers if p != symbol.upper()][:15]

    # Fetch peer info
    peer_infos = {}
    for peer in all_peers[:12]:  # limit to avoid rate limiting
        try:
            pi = yf.Ticker(peer).info
            if pi and pi.get("sector") == sector:
                peer_infos[peer] = pi
        except Exception:
            pass

    if not peer_infos:
        return PeerComparison(
            sector=sector, industry=industry, peer_count=0, peer_symbols=[],
            metrics=[], summary="No hay suficientes peers en cache o fallback para comparar.",
        )

    # --- Compute comparative metrics ---
    metrics_list = []

    # P/E ratio (lower is better for value investors)
    company_pe = _get_metric(info, "trailingPE")
    peer_pes = [_get_metric(pi, "trailingPE") for pi in peer_infos.values()]
    peer_pes = [v for v in peer_pes if v is not None and 0 < v < 200]
    if peer_pes and company_pe:
        median_pe = statistics.median(peer_pes)
        pctile = _percentile(company_pe, peer_pes)
        better = company_pe < median_pe  # lower P/E = relatively cheaper
        metrics_list.append(PeerMetric(
            name="P/E Ratio",
            company_value=company_pe,
            company_label=_fmt(company_pe, ".1f", "x"),
            sector_median=median_pe,
            sector_label=_fmt(median_pe, ".1f", "x"),
            percentile=pctile,
            better_than_peers=better,
            note=(
                f"{'Mas barato' if better else 'Mas caro'} que la mediana del sector "
                f"({_fmt(median_pe, '.1f', 'x')}). "
                f"Percentil {pctile} (mas bajo = mas barato en valoracion)."
            ),
        ))

    # ROE (higher is better)
    company_roe = _get_metric(info, "returnOnEquity", divisor=0.01)  # convert to %
    peer_roes = [_get_metric(pi, "returnOnEquity", 0.01) for pi in peer_infos.values()]
    peer_roes = [v for v in peer_roes if v is not None]
    if peer_roes and company_roe is not None:
        median_roe = statistics.median(peer_roes)
        pctile = _percentile(company_roe, peer_roes)
        better = company_roe > median_roe
        metrics_list.append(PeerMetric(
            name="ROE",
            company_value=company_roe,
            company_label=_fmt(company_roe, ".1f", "%"),
            sector_median=median_roe,
            sector_label=_fmt(median_roe, ".1f", "%"),
            percentile=pctile,
            better_than_peers=better,
            note=(
                f"ROE {'superior' if better else 'inferior'} a la mediana del sector "
                f"({_fmt(median_roe, '.1f', '%')}). Percentil {pctile}."
            ),
        ))

    # Net margin (higher is better)
    company_margin = _get_metric(info, "profitMargins", 0.01)
    peer_margins = [_get_metric(pi, "profitMargins", 0.01) for pi in peer_infos.values()]
    peer_margins = [v for v in peer_margins if v is not None]
    if peer_margins and company_margin is not None:
        median_m = statistics.median(peer_margins)
        pctile = _percentile(company_margin, peer_margins)
        better = company_margin > median_m
        metrics_list.append(PeerMetric(
            name="Margen neto",
            company_value=company_margin,
            company_label=_fmt(company_margin, ".1f", "%"),
            sector_median=median_m,
            sector_label=_fmt(median_m, ".1f", "%"),
            percentile=pctile,
            better_than_peers=better,
            note=(
                f"Margen {'superior' if better else 'inferior'} a la mediana del sector "
                f"({_fmt(median_m, '.1f', '%')}). Percentil {pctile}."
            ),
        ))

    # Debt/Equity (lower is better)
    company_de = _get_metric(info, "debtToEquity", divisor=100)
    peer_des = [_get_metric(pi, "debtToEquity", 100) for pi in peer_infos.values()]
    peer_des = [v for v in peer_des if v is not None and v >= 0]
    if peer_des and company_de is not None:
        median_de = statistics.median(peer_des)
        pctile = _percentile(company_de, peer_des)
        better = company_de < median_de
        metrics_list.append(PeerMetric(
            name="Deuda/Patrimonio",
            company_value=company_de,
            company_label=_fmt(company_de, ".2f", "x"),
            sector_median=median_de,
            sector_label=_fmt(median_de, ".2f", "x"),
            percentile=pctile,
            better_than_peers=better,
            note=(
                f"Deuda {'menor' if better else 'mayor'} que la mediana del sector "
                f"({_fmt(median_de, '.2f', 'x')}). "
                f"Percentil {100-pctile} de menor deuda."
            ),
        ))

    # P/B (lower is better)
    company_pb = _get_metric(info, "priceToBook")
    peer_pbs = [_get_metric(pi, "priceToBook") for pi in peer_infos.values()]
    peer_pbs = [v for v in peer_pbs if v is not None and v > 0]
    if peer_pbs and company_pb is not None:
        median_pb = statistics.median(peer_pbs)
        pctile = _percentile(company_pb, peer_pbs)
        better = company_pb < median_pb
        metrics_list.append(PeerMetric(
            name="P/B",
            company_value=company_pb,
            company_label=_fmt(company_pb, ".2f", "x"),
            sector_median=median_pb,
            sector_label=_fmt(median_pb, ".2f", "x"),
            percentile=pctile,
            better_than_peers=better,
            note=(
                f"Valoracion P/B {'mas baja' if better else 'mas alta'} que la mediana "
                f"({_fmt(median_pb, '.2f', 'x')})."
            ),
        ))

    # --- Summary ---
    better_count = sum(1 for m in metrics_list if m.better_than_peers)
    total = len(metrics_list)
    if total > 0:
        if better_count >= total * 0.7:
            summary = f"Empresa SUPERIOR a sus peers en {better_count}/{total} metricas clave del sector '{sector}'."
        elif better_count >= total * 0.4:
            summary = f"Empresa EN LINEA con sus peers — {better_count}/{total} metricas favorables."
        else:
            summary = f"Empresa INFERIOR a sus peers en la mayoria de metricas ({better_count}/{total} favorables)."
    else:
        summary = "Datos insuficientes para comparacion sectorial."

    return PeerComparison(
        sector=sector,
        industry=industry,
        peer_count=len(peer_infos),
        peer_symbols=list(peer_infos.keys()),
        metrics=metrics_list,
        summary=summary,
    )


def _peers_from_cache(sector: str, exclude_symbol: str) -> List[str]:
    """Find tickers in the batch cache that are in the same sector."""
    cache = batch_module.load_cache()
    results = cache.get("results", {})
    peers = []
    for ticker, r in results.items():
        if ticker == exclude_symbol.upper():
            continue
        if r.get("sector") == sector and not r.get("blocked") and not r.get("error"):
            peers.append(ticker)
    return peers[:10]
