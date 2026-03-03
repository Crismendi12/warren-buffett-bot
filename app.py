"""
app.py — Warren Buffett Stock Analysis Dashboard

Two modes:
  1. Single ticker — deep analysis with full transparency (existing behavior)
  2. Hub — Ranking, Watchlist management, Screener results

Run with: streamlit run app.py
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from datetime import datetime

import firewall
import analysis
import metrics
import batch
import watchlist as wl
import macro as macro_mod
import peers as peers_mod
import portfolio as portfolio_mod
import markets as mkt
import preferences as prefs_mod
import etf_analyzer as etf_mod
import capital as capital_mod
import insider as insider_mod
import pipeline as pipeline_mod

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="La Boveda | Buffett Analysis",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Global CSS — visual polish
# ---------------------------------------------------------------------------

st.markdown("""
<style>
/* === LA BOVEDA — Vault Dark Theme === */

/* Layout */
.block-container { padding-top: 1rem !important; }

/* Sidebar */
[data-testid="stSidebar"] { background: #0f1623 !important; border-right: 1px solid #1e2d45 !important; }
[data-testid="stSidebar"] .block-container { padding-top: 0.5rem !important; }

/* Metric cards — dark */
[data-testid="metric-container"] {
    background: #141c2e;
    border: 1px solid #1e2d45;
    border-radius: 10px;
    padding: 0.8rem 1rem !important;
}
[data-testid="metric-container"] label {
    color: #64748b !important;
    font-size: 0.75rem !important;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-size: 1.45rem !important;
    font-weight: 700 !important;
    color: #e2e8f0 !important;
}

/* Expanders — dark */
details {
    background: #141c2e !important;
    border: 1px solid #1e2d45 !important;
    border-radius: 10px !important;
    overflow: hidden;
    margin-bottom: 0.4rem;
}
details summary {
    padding: 0.6rem 0.9rem;
    font-weight: 600;
    color: #e2e8f0 !important;
    background: #141c2e !important;
}

/* Tabs — dark */
.stTabs [data-baseweb="tab-list"] {
    background: #0f1623 !important;
    border-bottom: 1px solid #1e2d45 !important;
    gap: 0.2rem;
}
.stTabs [data-baseweb="tab"] {
    color: #64748b !important;
    font-size: 0.88rem !important;
    font-weight: 600;
    border-radius: 6px 6px 0 0 !important;
}
.stTabs [data-baseweb="tab"][aria-selected="true"] {
    color: #c9a84c !important;
    background: #141c2e !important;
    border-bottom: 2px solid #c9a84c !important;
}
.stTabs [data-baseweb="tab-panel"] { padding-top: 0.8rem; }

/* HR dividers */
hr { border-color: #1e2d45 !important; margin: 1.2rem 0 !important; }

/* Dataframes */
[data-testid="stDataFrame"] { border-radius: 8px; overflow: hidden; }

/* Progress bar */
[data-testid="stProgress"] > div { border-radius: 6px; }
[data-testid="stProgress"] > div > div { background: #c9a84c !important; }

/* Plotly charts */
.js-plotly-plot { border-radius: 10px; overflow: hidden; }

/* Scrollbar */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #0f1623; }
::-webkit-scrollbar-thumb { background: #2a3d5a; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #c9a84c; }

/* === Vault Card Components === */
.vault-card {
    background: #141c2e;
    border: 1px solid #1e2d45;
    border-radius: 12px;
    padding: 1.2rem 1.4rem;
    margin-bottom: 1rem;
}
.vault-card-gold {
    background: #141c2e;
    border: 1px solid #1e2d45;
    border-left: 4px solid #c9a84c;
    border-radius: 12px;
    padding: 1.2rem 1.4rem;
    margin-bottom: 1rem;
}
.vault-score {
    font-size: 2.5rem;
    font-weight: 800;
    line-height: 1;
}

/* === Sidebar Navigation === */
.nav-section {
    font-size: 0.68rem;
    font-weight: 700;
    color: #c9a84c;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    padding: 0.9rem 0 0.3rem;
    border-bottom: 1px solid #1e2d45;
    margin-bottom: 0.2rem;
}
/* All sidebar buttons become flat nav items */
[data-testid="stSidebar"] .stButton > button {
    background: transparent !important;
    border: none !important;
    color: #94a3b8 !important;
    font-size: 0.88rem !important;
    font-weight: 500 !important;
    text-align: left !important;
    padding: 0.42rem 0.6rem !important;
    border-radius: 6px !important;
    width: 100% !important;
    margin: 0.04rem 0 !important;
    transition: all 0.15s ease !important;
    box-shadow: none !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: #1a2540 !important;
    color: #e8c97e !important;
}
/* Primary button (Analizar) keeps gold style */
[data-testid="stSidebar"] .stButton > button[kind="primary"] {
    background: #c9a84c !important;
    color: #080c14 !important;
    font-weight: 700 !important;
    border-radius: 8px !important;
}
[data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {
    background: #e8c97e !important;
}
/* Active nav item */
.nav-btn-active {
    background: #1a2540;
    border-left: 3px solid #c9a84c;
    color: #e8c97e !important;
    font-size: 0.88rem;
    font-weight: 600;
    padding: 0.42rem 0.57rem;
    border-radius: 6px;
    margin: 0.04rem 0;
    cursor: default;
    display: block;
}

/* === Recommendation Cards === */
.rec-card {
    background: #141c2e;
    border: 1px solid #1e2d45;
    border-radius: 10px;
    padding: 0.9rem 1.2rem;
    margin-bottom: 0.8rem;
}

/* === Pick cards (sidebar top picks) === */
.pick-card {
    background: #1a2540;
    border-left: 4px solid #3b82f6;
    border-radius: 6px;
    padding: 0.45rem 0.75rem;
    margin-bottom: 0.35rem;
    font-size: 0.82rem;
    line-height: 1.5;
    color: #e2e8f0;
    overflow: hidden;
}
.pick-card-green  { border-left-color: #10b981; }
.pick-card-blue   { border-left-color: #3b82f6; }
.pick-card-orange { border-left-color: #f59e0b; }
.pick-card-red    { border-left-color: #ef4444; }

/* Section header accent */
.section-header {
    border-left: 4px solid #c9a84c;
    padding-left: 0.8rem;
    margin-bottom: 0.8rem;
    color: #e2e8f0;
}

/* === Streamlit widget overrides === */
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input {
    background: #141c2e !important;
    border: 1px solid #2a3d5a !important;
    color: #e2e8f0 !important;
    border-radius: 8px !important;
}
[data-testid="stTextInput"] input:focus,
[data-testid="stNumberInput"] input:focus {
    border-color: #c9a84c !important;
    box-shadow: 0 0 0 2px rgba(201,168,76,0.2) !important;
}
[data-testid="stSelectbox"] > div > div {
    background: #141c2e !important;
    border: 1px solid #2a3d5a !important;
    color: #e2e8f0 !important;
}
[data-testid="stAlert"] {
    border-radius: 8px !important;
    border-left-width: 4px !important;
}
/* Main content area buttons (non-sidebar) */
.main .stButton > button {
    border-radius: 8px !important;
    font-weight: 600 !important;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def score_color(pct: float) -> str:
    if pct >= 0.8: return "#10b981"
    elif pct >= 0.6: return "#3b82f6"
    elif pct >= 0.4: return "#f59e0b"
    else: return "#ef4444"


def _dark_layout(fig, height: int = None, title: str = None):
    """Apply consistent La Boveda dark theme to any Plotly figure."""
    updates = dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#0f1623",
        font=dict(color="#e2e8f0", size=12),
        xaxis=dict(gridcolor="#1e2d45", linecolor="#2a3d5a", zeroline=False),
        yaxis=dict(gridcolor="#1e2d45", linecolor="#2a3d5a", zeroline=False),
    )
    if height:
        updates["height"] = height
    if title:
        updates["title"] = dict(text=title, font=dict(color="#e2e8f0"))
    fig.update_layout(**updates)
    return fig


def fmt_cap(v) -> str:
    if v is None: return "N/A"
    if v >= 1e12: return f"${v/1e12:.2f}T"
    if v >= 1e9:  return f"${v/1e9:.1f}B"
    return f"${v/1e6:.0f}M"


def score_badge(score: int) -> str:
    if score >= 80: return "Strong candidate"
    elif score >= 60: return "On radar"
    elif score >= 40: return "With caution"
    else: return "Does not qualify"


def _score_style(df, col: str = "Score"):
    """Color-code a score column using vault palette. No matplotlib required.
    Uses df.style.map() (pandas >= 2.1 compatible — applymap was removed)."""
    def _cell(v):
        try:
            v = int(v)
        except (ValueError, TypeError):
            return ""
        if v >= 80:   return "background-color:#0d1f18;color:#10b981"
        elif v >= 60: return "background-color:#0d1428;color:#3b82f6"
        elif v >= 40: return "background-color:#1a1408;color:#f59e0b"
        else:         return "background-color:#1a0808;color:#ef4444"
    return df.style.map(_cell, subset=[col])


# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------

def _nav_btn(label: str, target: str) -> None:
    """Render a sidebar nav item. Active mode shows as styled div, others as buttons."""
    cur = st.session_state.get("mode", "Analyze Company")
    if cur == target:
        st.markdown(
            f"<div class='nav-btn-active'>{label}</div>",
            unsafe_allow_html=True,
        )
    else:
        if st.button(label, key=f"nav_{target}", use_container_width=True):
            st.session_state["mode"] = target
            st.rerun()


if "mode" not in st.session_state:
    st.session_state["mode"] = "Analyze Company"

with st.sidebar:
    # --- Brand header ---
    st.markdown(
        "<div style='padding:1rem 0 0.8rem; border-bottom:1px solid #c9a84c; margin-bottom:0.8rem'>"
        "<div style='font-size:1.55rem; font-weight:800; letter-spacing:0.18em; color:#c9a84c; line-height:1'>LA BOVEDA</div>"
        "<div style='font-size:0.66rem; color:#64748b; letter-spacing:0.1em; margin-top:0.25rem'>POWERED BY BUFFETT PRINCIPLES</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    # --- Ticker input (Analyze mode only) ---
    if st.session_state["mode"] == "Analyze Company":
        ticker_input = st.text_input(
            "Ticker",
            value="",
            placeholder="e.g.: AAPL, KO, MSFT",
        ).strip().upper()
        analyze_btn = st.button("Analyze", type="primary", use_container_width=True)
        st.markdown("<div style='margin-bottom:0.4rem'></div>", unsafe_allow_html=True)
    else:
        ticker_input = ""
        analyze_btn = False

    # --- Navigation groups ---
    st.markdown("<div class='nav-section'>ANALYZE</div>", unsafe_allow_html=True)
    _nav_btn("Company", "Analyze Company")
    _nav_btn("Recommendations", "Recommendations")

    st.markdown("<div class='nav-section'>DISCOVER</div>", unsafe_allow_html=True)
    _nav_btn("Global Screener", "Global Screener")
    _nav_btn("Ranking", "Ranking")
    _nav_btn("Dividend ETFs", "Dividend ETFs")

    st.markdown("<div class='nav-section'>MANAGE</div>", unsafe_allow_html=True)
    _nav_btn("My Portfolio", "My Portfolio")
    _nav_btn("My Watchlist", "My Watchlist")

    st.markdown("<div class='nav-section'>CONTEXT</div>", unsafe_allow_html=True)
    _nav_btn("Macro", "Macro Context")

    st.markdown("<div style='margin-top:0.6rem'></div>", unsafe_allow_html=True)

    # --- Top Picks widget ---
    _ranked_sidebar = batch.get_ranked_results(min_score=65)
    if _ranked_sidebar:
        st.markdown(
            "<div style='font-size:0.68rem; font-weight:700; color:#c9a84c; "
            "letter-spacing:0.12em; text-transform:uppercase; padding:0.7rem 0 0.3rem; "
            "border-bottom:1px solid #1e2d45; margin-bottom:0.3rem'>TOP PICKS</div>",
            unsafe_allow_html=True,
        )
        for r in _ranked_sidebar[:5]:
            sc  = r["total_score"]
            col = score_color(sc / 100)
            css_cls = {
                "#10b981": "pick-card pick-card-green",
                "#3b82f6": "pick-card pick-card-blue",
                "#f59e0b": "pick-card pick-card-orange",
                "#ef4444": "pick-card pick-card-red",
            }.get(col, "pick-card")
            st.markdown(
                f"<div class='{css_cls}'>"
                f"<b>{r['symbol']}</b>"
                f"<span style='float:right;color:{col};font-weight:700'>{sc}/100</span>"
                f"<br><span style='color:#64748b;font-size:0.75rem'>{r.get('verdict','')}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

    st.markdown("<div style='margin-top:0.8rem'></div>", unsafe_allow_html=True)
    with st.expander("About this analysis"):
        st.caption(
            "Data via Yahoo Finance (yfinance). "
            "Educational analysis — not financial advice."
        )

    # --- Automation panel ---
    st.markdown(
        "<div style='font-size:0.68rem; font-weight:700; color:#c9a84c; "
        "letter-spacing:0.12em; text-transform:uppercase; padding:0.9rem 0 0.3rem; "
        "border-top:1px solid #1e2d45; margin-top:0.6rem'>AUTOMATION</div>",
        unsafe_allow_html=True,
    )
    _auto_status = pipeline_mod.load_status()
    if _auto_status:
        _last = _auto_status.get("last_run_at", "")[:16].replace("T", " ")
        _next = _auto_status.get("next_run_at", "")[:10]
        _cands = _auto_status.get("candidates_found", "—")
        _added = _auto_status.get("added_to_watchlist", "—")
        _wl_sz = _auto_status.get("watchlist_size", "—")
        st.sidebar.caption(f"Last cycle: {_last}")
        st.sidebar.caption(f"Candidates: {_cands} | New in WL: {_added}")
        st.sidebar.caption(f"Current WL: {_wl_sz} companies")
        st.sidebar.caption(f"Next: {_next}")
    else:
        st.sidebar.caption("No run recorded.")
        st.sidebar.caption("Start with: python3 scheduler.py --run-now")

    if st.sidebar.button("Run now", key="run_pipeline_now", use_container_width=True):
        _prog = st.sidebar.progress(0, text="Starting pipeline...")

        def _pipeline_cb(msg: str, pct: float) -> None:
            _prog.progress(min(pct, 1.0), text=msg[:80])

        try:
            pipeline_mod.run_full_pipeline(progress_callback=_pipeline_cb)
            _prog.empty()
            st.sidebar.success("Pipeline complete. Ranking updated.")
        except Exception as _pe:
            _prog.empty()
            st.sidebar.error(f"Pipeline error: {_pe}")
        st.rerun()

mode = st.session_state["mode"]


# ===========================================================================
# CONVICTION SCORE — composite buy signal (quality + MOS + insider + ROIC)
# ===========================================================================

def _conviction_score(r: dict):
    """
    Compute a Conviction Index (0-100) from cached batch result data.
    No network calls — uses only pre-computed fields in the result dict.

    Components (100 pts total):
      35 — Calidad Buffett (fundamentals score)
      30 — Margen de Seguridad (price vs intrinsic value)
      15 — Timing de entrada (52W range position + 200-DMA distance)
      12 — Senal insider (management conviction)
       8 — ROIC vs WACC (capital efficiency)

    Returns: (score: int, label: str, color: str)
    """
    # Component 1: Buffett quality (0-35 pts)
    quality_pts = round(r.get("total_score", 0) / 100 * 35)

    # Component 2: Margin of Safety (0-30 pts)
    # 50%+ MOS = full 30 pts; negative MOS = 0 pts
    iv    = r.get("intrinsic_value") or 0
    price = r.get("current_price") or 0
    if iv > 0 and price > 0:
        mos_pct = (iv - price) / iv * 100
    else:
        mos_pct = 0
    mos_pts = round(min(max(mos_pct, 0), 50) / 50 * 30)

    # Component 3: Entry timing (0-15 pts)
    # Uses 52-week range position and distance from 200-day moving average
    pm      = r.get("price_metrics") or {}
    pct_low = pm.get("pct_from_52w_low")     # 0% = at 52W low, 100% = at 52W high
    dist200 = pm.get("dist_from_200dma_pct") # negative = below MA200 (potentially oversold)
    if pct_low is not None and pct_low <= 25 and dist200 is not None and dist200 < 0:
        timing_pts = 15   # lower 25% of 52W range AND below MA200 — ideal technical entry
    elif pct_low is not None and pct_low <= 40:
        timing_pts = 10   # lower 40% of range — relatively cheap technically
    elif pct_low is not None and pct_low <= 60:
        timing_pts = 5    # neutral zone
    elif pct_low is not None:
        timing_pts = 0    # upper range — wait for a better entry
    else:
        timing_pts = 5    # no data available — neutral, don't penalize

    # Component 4: Insider signal (0-12 pts)
    insider_signal = (r.get("insider") or {}).get("signal", "NEUTRAL")
    insider_pts = {"BULLISH": 12, "NEUTRAL": 6, "BEARISH": 0}.get(insider_signal, 6)

    # Component 5: ROIC vs WACC — value creation (0-8 pts)
    cap          = r.get("capital") or {}
    roic_vs_wacc = cap.get("roic_vs_wacc")
    roic_avg     = cap.get("roic_avg") or 0
    if roic_vs_wacc and roic_vs_wacc > 0 and roic_avg >= 15:
        roic_pts = 8
    elif roic_vs_wacc and roic_vs_wacc > 0:
        roic_pts = 5
    elif roic_avg and roic_avg > 0:
        roic_pts = 2
    else:
        roic_pts = 0

    total = quality_pts + mos_pts + timing_pts + insider_pts + roic_pts

    if total >= 75:
        label, color = "High conviction", "#10b981"
    elif total >= 55:
        label, color = "Medium conviction", "#3b82f6"
    elif total >= 35:
        label, color = "Low conviction", "#f59e0b"
    else:
        label, color = "Not recommended", "#ef4444"

    return total, label, color


# ===========================================================================
# DRILL-DOWN HELPERS — used by Recomendaciones tab
# ===========================================================================

def _verdict_color_from_score(sc: int) -> str:
    if sc >= 80: return "#10b981"
    elif sc >= 60: return "#3b82f6"
    elif sc >= 40: return "#f59e0b"
    return "#ef4444"


def _compute_signal_from_cache(total_score: int, iv, price):
    """Replicate analysis.AnalysisResult.signal using cached values."""
    if iv and iv > 0 and price and price > 0:
        margin    = (iv - price) / iv
        buy_tgt   = round(float(iv) * 0.70, 2)
        sell_tgt  = round(float(iv) * 1.20, 2)
    else:
        margin = None
        buy_tgt = sell_tgt = None
    if total_score >= 75 and margin is not None and margin >= 0.35:
        return ("STRONG BUY", "#10b981", buy_tgt, sell_tgt)
    elif total_score >= 65 and margin is not None and margin >= 0.20:
        return ("BUY", "#10b981", buy_tgt, sell_tgt)
    elif total_score >= 60 and margin is not None and margin >= 0.10:
        return ("ACCUMULATE", "#3b82f6", buy_tgt, sell_tgt)
    elif total_score < 40 or (margin is not None and margin <= -0.40):
        return ("SELL", "#ef4444", buy_tgt, sell_tgt)
    elif total_score < 55 or (margin is not None and margin < -0.15):
        return ("REDUCE", "#f59e0b", buy_tgt, sell_tgt)
    elif total_score >= 55:
        return ("HOLD", "#f59e0b", buy_tgt, sell_tgt)
    return ("EVALUATE", "#64748b", buy_tgt, sell_tgt)


def _show_drill_down(symbol: str) -> None:
    """Render full company analysis from batch cache + live charts."""
    import warnings as _w

    # Back button
    if st.button("← Back to Recommendations", key="drill_back"):
        del st.session_state["rec_drill"]
        st.rerun()

    # Load from cache (instant, no network call)
    _cache = batch.load_cache()
    _r = _cache.get("results", {}).get(symbol)
    if not _r:
        st.error(f"No data for {symbol} in cache. Run the analysis first.")
        return

    sc       = _r.get("total_score", 0)
    company  = _r.get("company_name", symbol)
    sector   = _r.get("sector", "N/A")
    industry = _r.get("industry", "")
    price    = _r.get("current_price")
    mktcap   = _r.get("market_cap")
    iv       = _r.get("intrinsic_value")
    verdict  = _r.get("verdict", "N/A")
    analyzed = _r.get("analyzed_at", "")[:10]

    st.markdown(
        f"<div style='margin-bottom:0.4rem'>"
        f"<span style='font-size:2rem; font-weight:800; color:#c9a84c'>{symbol}</span>"
        f"<span style='font-size:1.1rem; color:#94a3b8; margin-left:0.9rem'>{company}</span>"
        f"</div>"
        f"<div style='color:#64748b; font-size:0.85rem; margin-bottom:0.8rem'>"
        f"{sector} · {industry} | Price: {'$'+f'{price:.2f}' if price else 'N/A'} | "
        f"Cap: {fmt_cap(mktcap)} | Analyzed: {analyzed}"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    # --- Gauge + verdict + signal ---
    def _make_gauge_d(s, mx):
        _fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=s,
            number={"suffix": f"/{mx}", "font": {"size": 36, "color": "#e2e8f0"}},
            gauge={
                "axis": {"range": [0, mx], "tickcolor": "#64748b"},
                "bar": {"color": "#c9a84c", "thickness": 0.3},
                "bgcolor": "#0f1623",
                "borderwidth": 1, "bordercolor": "#1e2d45",
                "steps": [
                    {"range": [0, mx*0.4], "color": "#1a1020"},
                    {"range": [mx*0.4, mx*0.6], "color": "#1a1a10"},
                    {"range": [mx*0.6, mx*0.8], "color": "#101a20"},
                    {"range": [mx*0.8, mx], "color": "#0d1f18"},
                ],
            },
            title={"text": "Buffett Score", "font": {"size": 16, "color": "#64748b"}},
        ))
        _fig.update_layout(
            height=260, margin=dict(t=40, b=0, l=20, r=20),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e2e8f0"),
        )
        return _fig

    _vc = _verdict_color_from_score(sc)
    try:
        _sig_lbl, _sig_col, _buy_t, _sell_t = _compute_signal_from_cache(sc, iv, price)
    except Exception:
        _sig_lbl, _sig_col, _buy_t, _sell_t = ("EVALUATE", "#64748b", None, None)
    _iv_disp  = f"${iv:.2f}" if iv else "N/C"
    _buy_str  = f"${_buy_t:.2f}"  if _buy_t  else "—"
    _sell_str = f"${_sell_t:.2f}" if _sell_t else "—"

    _gc, _vc2 = st.columns([1, 1])
    with _gc:
        st.plotly_chart(_make_gauge_d(sc, 100), use_container_width=True)
    with _vc2:
        st.markdown(
            f"<div style='padding:1.4rem; background:#141c2e; border:1px solid #1e2d45; "
            f"border-left:4px solid {_vc}; border-radius:12px; margin-top:0.5rem'>"
            f"<div style='font-size:0.72rem; text-transform:uppercase; letter-spacing:0.1em; "
            f"color:#64748b; margin-bottom:0.3rem'>Verdict</div>"
            f"<div style='font-size:1.7rem; font-weight:800; color:{_vc}; line-height:1.1; "
            f"margin-bottom:0.5rem'>{verdict}</div>"
            f"<div style='color:#94a3b8; font-size:0.87rem'>"
            f"Score: <b style='color:#e2e8f0'>{sc}/100</b> ({sc}%)</div>"
            f"<div style='margin-top:0.9rem; padding-top:0.8rem; border-top:1px solid #1e2d45'>"
            f"<div style='font-size:0.72rem; text-transform:uppercase; letter-spacing:0.1em; "
            f"color:#64748b; margin-bottom:0.3rem'>Action signal</div>"
            f"<div style='font-size:1.2rem; font-weight:800; color:{_sig_col}; "
            f"margin-bottom:0.4rem'>{_sig_lbl}</div>"
            f"<div style='font-size:0.82rem; color:#94a3b8; line-height:1.8'>"
            f"Estimated IV: <b style='color:#e2e8f0'>{_iv_disp}</b><br>"
            f"Buy &lt; <b style='color:#10b981'>{_buy_str}</b> &nbsp;·&nbsp; "
            f"Sell &gt; <b style='color:#ef4444'>{_sell_str}</b>"
            f"</div></div></div>",
            unsafe_allow_html=True,
        )

    # --- 4 section score cards ---
    st.markdown("<div style='margin-top:1rem'></div>", unsafe_allow_html=True)
    _secs = [
        ("moat",      "Moat"),
        ("valuation", "Valuation"),
        ("health",    "Health"),
        ("growth",    "Growth"),
    ]
    _sc1, _sc2, _sc3, _sc4 = st.columns(4)
    for _col, (key, name) in zip([_sc1, _sc2, _sc3, _sc4], _secs):
        with _col:
            _sd = _r.get(key, {})
            _ss = _sd.get("score", 0)
            _sm = _sd.get("max_score", 25)
            _cc = score_color(_ss / _sm if _sm else 0)
            st.markdown(
                f"<div style='text-align:center; padding:0.7rem; background:#141c2e; "
                f"border:1px solid #1e2d45; border-radius:10px'>"
                f"<div style='font-size:0.68rem; color:#64748b; text-transform:uppercase; "
                f"letter-spacing:0.08em; margin-bottom:0.2rem'>{name}</div>"
                f"<div style='font-size:1.4rem; font-weight:800; color:{_cc}'>{_ss}/{_sm}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # --- Detail tabs ---
    _dt1, _dt2, _dt3, _dt4 = st.tabs([
        "Detailed criteria", "Historical charts", "ROIC", "Insiders"
    ])

    # Tab 1: criteria from cache (instant)
    with _dt1:
        for _sk, _sn in [("moat", "Moat / Competitive Advantage"),
                         ("valuation", "Valuation / Intrinsic Value"),
                         ("health",    "Financial Health"),
                         ("growth",    "Consistent Growth")]:
            _sd2  = _r.get(_sk, {})
            _ss2  = _sd2.get("score", 0)
            _sm2  = _sd2.get("max_score", 25)
            _pct2 = _ss2 / _sm2 if _sm2 else 0
            _cc2  = score_color(_pct2)
            st.markdown(
                f"<div style='display:flex; justify-content:space-between; align-items:center; "
                f"margin-top:1.2rem; margin-bottom:0.3rem'>"
                f"<span style='font-size:1rem; font-weight:700; color:#e2e8f0'>{_sn}</span>"
                f"<span style='font-size:1.1rem; font-weight:800; color:{_cc2}'>{_ss2}/{_sm2}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
            st.progress(_pct2, text=f"{_pct2*100:.0f}%")
            for _cr in _sd2.get("criteria", []):
                _icon = "+" if _cr.get("passed") else "-"
                _pe   = _cr.get("points_earned", 0)
                _pm   = _cr.get("points_max", 0)
                _raw  = _cr.get("raw_label", "N/A")
                with st.expander(f"{_icon} {_cr.get('name','?')}  —  {_pe}/{_pm} pts  |  {_raw}"):
                    st.markdown(f"**Criterion:** {_cr.get('threshold','—')}")
                    st.markdown(f"**Source:** {_cr.get('source','—')}")
                    st.markdown(f"**Justification:** {_cr.get('explanation','—')}")

    # Tab 2: historical charts (fetched live)
    with _dt2:
        with st.spinner("Loading historical charts..."):
            with _w.catch_warnings():
                _w.simplefilter("ignore")
                _roe_d  = metrics.get_roe_history(symbol)
                _rev_d  = metrics.get_revenue_history(symbol)
                _eps_d  = metrics.get_eps_history(symbol)
                _ph     = metrics.get_price_history(symbol, period="5y")
        _hc1, _hc2, _hc3 = st.columns(3)
        with _hc1:
            if _roe_d["values"]:
                _df_roe = pd.DataFrame({"Ano": _roe_d["years"], "ROE": [v*100 for v in _roe_d["values"]]})
                _fig_roe = px.bar(_df_roe, x="Ano", y="ROE", title="ROE (%)", color="ROE",
                                  color_continuous_scale="RdYlGn")
                _fig_roe.add_hline(y=15, line_dash="dash", line_color="#f59e0b",
                                   annotation_text="15%", annotation_font_color="#f59e0b")
                _dark_layout(_fig_roe, height=300)
                _fig_roe.update_layout(showlegend=False, margin=dict(t=40, b=30))
                st.plotly_chart(_fig_roe, use_container_width=True)
            else:
                st.info("No ROE data")
        with _hc2:
            if _rev_d["values"]:
                _fig_re = go.Figure()
                _fig_re.add_trace(go.Scatter(
                    x=_rev_d["years"], y=[v/1e9 for v in _rev_d["values"]],
                    mode="lines+markers", name="Revenue ($B)", yaxis="y1",
                    line=dict(color="#3498db", width=2),
                ))
                if _eps_d["values"]:
                    _fig_re.add_trace(go.Scatter(
                        x=_eps_d["years"], y=_eps_d["values"],
                        mode="lines+markers", name="EPS ($)", yaxis="y2",
                        line=dict(color="#10b981", width=2, dash="dot"),
                    ))
                _dark_layout(_fig_re, height=300)
                _fig_re.update_layout(
                    title=dict(text="Revenue and EPS", font=dict(color="#e2e8f0")),
                    yaxis=dict(title="Revenue ($B)", gridcolor="#1e2d45"),
                    yaxis2=dict(title="EPS ($)", overlaying="y", side="right", gridcolor="#1e2d45"),
                    legend=dict(orientation="h", y=1.1, font=dict(color="#e2e8f0")),
                    margin=dict(t=50, b=30),
                )
                st.plotly_chart(_fig_re, use_container_width=True)
            else:
                st.info("No revenue data")
        with _hc3:
            if not _ph.empty:
                _fig_ph = px.line(_ph.reset_index(), x="Date", y="Close", title="5-Year Price")
                _fig_ph.update_traces(line_color="#c9a84c")
                _dark_layout(_fig_ph, height=300)
                _fig_ph.update_layout(margin=dict(t=40, b=30))
                st.plotly_chart(_fig_ph, use_container_width=True)
            else:
                st.info("No price data")

    # Tab 3: ROIC (fetched live)
    with _dt3:
        with st.spinner("Calculating ROIC and capital quality..."):
            _cap_d = capital_mod.get_capital_quality(symbol)
        if _cap_d.get("error"):
            st.info(f"ROIC not available: {_cap_d['error']}")
        else:
            _rvc = _cap_d["verdict_color"]
            _rvt = _cap_d["verdict"]
            _ra  = _cap_d["roic_avg"]
            _rt  = _cap_d["roic_trend"]
            _rw  = _cap_d["wacc_est"]
            _rs  = _cap_d["roic_vs_wacc"]
            _rcl = _cap_d["capex_intensity_label"]
            _rcc = _cap_d["capex_intensity_color"]
            _rbb = _cap_d["buyback_signal"]
            st.markdown(
                f"<div style='padding:0.8rem 1.2rem; background:#141c2e; border:1px solid #1e2d45; "
                f"border-left:5px solid {_rvc}; border-radius:10px; margin-bottom:1rem'>"
                f"<span style='font-size:1.05rem; font-weight:700; color:{_rvc}'>{_rvt}</span>"
                f"<span style='color:#64748b; font-size:0.85rem; margin-left:0.8rem'>"
                f"Avg ROIC: {_ra:.1f}% · Trend: {_rt}"
                f"{(' · WACC: ' + str(_rw) + '%') if _rw else ''}"
                f"{(' · Spread: ' + ('+' if _rs >= 0 else '') + str(_rs) + '%') if _rs is not None else ''}"
                f"</span></div>",
                unsafe_allow_html=True,
            )
            _rmc1, _rmc2, _rmc3 = st.columns(3)
            with _rmc1:
                _bbm = {"yes": ("Buying back shares", "#10b981"), "no": ("Diluting shares", "#ef4444"), "neutral": ("No clear trend", "#64748b")}
                _bbl, _bbc = _bbm.get(_rbb, ("—", "#64748b"))
                st.markdown(f"<div style='text-align:center; padding:0.8rem; background:#141c2e; border:1px solid #1e2d45; border-radius:10px'><div style='font-size:0.7rem; color:#64748b; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:0.3rem'>Buybacks</div><div style='font-size:1rem; font-weight:700; color:{_bbc}'>{_bbl}</div></div>", unsafe_allow_html=True)
            with _rmc2:
                st.markdown(f"<div style='text-align:center; padding:0.8rem; background:#141c2e; border:1px solid #1e2d45; border-radius:10px'><div style='font-size:0.7rem; color:#64748b; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:0.3rem'>Capex Intensity</div><div style='font-size:1rem; font-weight:700; color:{_rcc}'>{_rcl or '—'}</div></div>", unsafe_allow_html=True)
            with _rmc3:
                _rsc = "#10b981" if (_rs is not None and _rs > 0) else "#ef4444"
                st.markdown(f"<div style='text-align:center; padding:0.8rem; background:#141c2e; border:1px solid #1e2d45; border-radius:10px'><div style='font-size:0.7rem; color:#64748b; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:0.3rem'>ROIC vs WACC</div><div style='font-size:1rem; font-weight:700; color:{_rsc}'>{('+' if _rs >= 0 else '') + str(_rs) + ' pp' if _rs is not None else '—'}</div></div>", unsafe_allow_html=True)
            if _cap_d["roic_history"]:
                _rh2 = _cap_d["roic_history"]
                _fig_roic2 = go.Figure()
                _fig_roic2.add_trace(go.Scatter(x=[x[0] for x in _rh2], y=[x[1] for x in _rh2], mode="lines+markers", name="ROIC %", line=dict(color="#c9a84c", width=2), marker=dict(size=6, color="#c9a84c")))
                if _rw:
                    _fig_roic2.add_hline(y=_rw, line_dash="dash", line_color="#64748b", annotation_text=f"WACC est. {_rw}%", annotation_font_color="#64748b")
                _dark_layout(_fig_roic2, height=260)
                _fig_roic2.update_layout(title=dict(text="ROIC history (%)", font=dict(color="#e2e8f0")), yaxis=dict(title="ROIC %", gridcolor="#1e2d45"), xaxis=dict(title="Year"), margin=dict(t=50, b=30), showlegend=False)
                st.plotly_chart(_fig_roic2, use_container_width=True)

    # Tab 4: Insiders (fetched live)
    with _dt4:
        with st.spinner("Fetching insider transactions..."):
            _ins2 = insider_mod.get_insider_signal(symbol)
        if _ins2.get("error"):
            st.info(f"Insider data not available: {_ins2['error']}")
        else:
            _ic  = _ins2["signal_color"]
            _il  = _ins2["signal_label"]
            _in  = _ins2["net_6m_usd"]
            _ibu = _ins2["buy_count"]
            _ise = _ins2["sell_count"]
            _itx = _ins2["recent_transactions"]

            def _fmt_m2(v):
                if v is None: return "—"
                if abs(v) >= 1e6: return f"${v/1e6:.1f}M"
                if abs(v) >= 1e3: return f"${v/1e3:.0f}K"
                return f"${v:.0f}"

            _ic1, _ic2, _ic3 = st.columns(3)
            with _ic1:
                st.markdown(f"<div style='text-align:center; padding:0.8rem; background:#141c2e; border:1px solid #1e2d45; border-radius:10px'><div style='font-size:0.7rem; color:#64748b; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:0.3rem'>Signal (6 months)</div><div style='font-size:1.1rem; font-weight:800; color:{_ic}'>{_il}</div></div>", unsafe_allow_html=True)
            with _ic2:
                _inc = "#10b981" if (_in or 0) >= 0 else "#ef4444"
                st.markdown(f"<div style='text-align:center; padding:0.8rem; background:#141c2e; border:1px solid #1e2d45; border-radius:10px'><div style='font-size:0.7rem; color:#64748b; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:0.3rem'>Net (buys - sells)</div><div style='font-size:1.05rem; font-weight:700; color:{_inc}'>{_fmt_m2(_in)}</div></div>", unsafe_allow_html=True)
            with _ic3:
                st.markdown(f"<div style='text-align:center; padding:0.8rem; background:#141c2e; border:1px solid #1e2d45; border-radius:10px'><div style='font-size:0.7rem; color:#64748b; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:0.3rem'>Transactions</div><div style='font-size:0.9rem; font-weight:700; color:#e2e8f0'><span style='color:#10b981'>{_ibu} buys</span> · <span style='color:#ef4444'>{_ise} sells</span></div></div>", unsafe_allow_html=True)

            if _itx:
                st.markdown("<div style='margin-top:0.8rem'></div>", unsafe_allow_html=True)
                for _tx in _itx[:3]:
                    _tx_type  = _tx.get("transaction", "—")
                    _is_buy   = any(k in _tx_type.lower() for k in ["purchase", "buy", "acquisition", "grant"])
                    _tx_color = "#10b981" if _is_buy else "#ef4444"
                    st.markdown(
                        f"<div style='padding:0.5rem 0.9rem; background:#141c2e; border:1px solid #1e2d45; "
                        f"border-left:3px solid {_tx_color}; border-radius:8px; margin-bottom:0.4rem; font-size:0.83rem'>"
                        f"<b style='color:#e2e8f0'>{_tx.get('insider','—')}</b> · {_tx_type} · "
                        f"<span style='color:{_tx_color}'>{_fmt_m2(_tx.get('value'))}</span> · "
                        f"<span style='color:#64748b'>{_tx.get('date','—')}</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )


# ===========================================================================
# MODE 1: Single ticker analysis
# ===========================================================================

if mode == "Analyze Company":
    if not ticker_input or not analyze_btn:
        # --- Vault landing screen ---
        st.markdown(
            "<div style='text-align:center; padding:3rem 1rem 1.5rem'>"
            "<div style='font-size:3.8rem; font-weight:800; letter-spacing:0.22em; "
            "color:#c9a84c; line-height:1; margin-bottom:0.5rem'>LA BOVEDA</div>"
            "<div style='font-size:1rem; color:#64748b; letter-spacing:0.08em; "
            "text-transform:uppercase; margin-bottom:2rem'>"
            "Investment analysis in the style of Warren Buffett</div>"
            "</div>",
            unsafe_allow_html=True,
        )

        # Stats bar
        _all_results = batch.get_ranked_results(min_score=0)
        _wl_count = len(wl.load())
        _last_run = batch.get_last_run_time()
        _last_str = "Never"
        if _last_run:
            try:
                _last_str = datetime.fromisoformat(_last_run).strftime("%Y-%m-%d")
            except Exception:
                _last_str = _last_run

        s1, s2, s3 = st.columns(3)
        s1.metric("Companies analyzed", len(_all_results))
        s2.metric("Last analysis", _last_str)
        s3.metric("In my watchlist", _wl_count)

        st.markdown("<div style='margin:1.5rem 0'></div>", unsafe_allow_html=True)

        st.markdown(
            "<div class='vault-card-gold'>"
            "<div style='font-size:0.75rem; text-transform:uppercase; letter-spacing:0.1em; "
            "color:#c9a84c; font-weight:700; margin-bottom:0.6rem'>How to use La Boveda</div>"
            "<div style='color:#94a3b8; font-size:0.9rem; line-height:1.7'>"
            "Enter a ticker in the left panel and press <b style='color:#e2e8f0'>Analyze</b>. "
            "The system evaluates the company on <b style='color:#e2e8f0'>4 pillars</b> "
            "(Moat, Valuation, Health, Growth) out of 100 points, based on the principles "
            "Warren Buffett has detailed in his annual letters.<br><br>"
            "Use the <b style='color:#e2e8f0'>Global Screener</b> to discover candidates across "
            "multiple markets, <b style='color:#e2e8f0'>Recommendations</b> to see the best "
            "batch results, and <b style='color:#e2e8f0'>My Portfolio</b> to evaluate "
            "your set of positions."
            "</div>"
            "</div>",
            unsafe_allow_html=True,
        )

        st.markdown(
            "<div style='text-align:center; color:#64748b; font-size:0.82rem; "
            "margin-bottom:0.8rem'>Quick analyze:</div>",
            unsafe_allow_html=True,
        )
        q1, q2, q3, q4 = st.columns(4)
        for _col, _tick in zip([q1, q2, q3, q4], ["KO", "AAPL", "JNJ", "MSFT"]):
            with _col:
                if st.button(_tick, use_container_width=True):
                    st.session_state["_quick_ticker"] = _tick
                    st.rerun()

        # Handle quick ticker selection
        if "mode" in st.session_state and st.session_state.get("_quick_ticker"):
            st.info(f"Type **{st.session_state['_quick_ticker']}** in the Ticker field and press Analyze.")

        st.stop()

    with st.spinner(f"Checking {ticker_input}..."):
        fw_result = firewall.run(ticker_input)

    if fw_result.status == "BLOCK":
        st.error(f"Analysis blocked for **{ticker_input}**")
        for issue in fw_result.block_issues:
            st.error(f"**{issue.message}**\n\n{issue.detail}")
        st.info("Try: KO, AAPL, JNJ, PG, MSFT")
        st.stop()

    with st.spinner("Calculating score..."):
        result = analysis.run(ticker_input)
        info = metrics.get_info(ticker_input)

    if fw_result.status == "WARN":
        for issue in fw_result.warn_issues:
            st.warning(f"**Warning — {issue.message}**\n\n{issue.detail}")

    # --- Company header ---
    price_str = f"${result.current_price:.2f}" if result.current_price else "N/A"
    st.markdown(
        f"<div class='vault-card-gold' style='margin-bottom:1.2rem'>"
        f"<div style='font-size:0.72rem; text-transform:uppercase; letter-spacing:0.1em; "
        f"color:#c9a84c; font-weight:700; margin-bottom:0.3rem'>{result.symbol}</div>"
        f"<div style='font-size:1.8rem; font-weight:800; color:#e2e8f0; line-height:1.1; "
        f"margin-bottom:0.4rem'>{result.company_name}</div>"
        f"<div style='color:#64748b; font-size:0.85rem'>{result.sector}  ·  {result.industry}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )
    h1, h2, h3, h4 = st.columns(4)
    h1.metric("Current price", price_str)
    h2.metric("Market cap", fmt_cap(result.market_cap))
    h3.metric("Sector", result.sector)
    h4.metric("Industry", result.industry)
    st.markdown("---")

    # --- Gauge + verdict ---
    def make_gauge(score, max_score):
        pct = score / max_score if max_score else 0
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=score,
            number={"suffix": f"/{max_score}", "font": {"size": 36, "color": "#e2e8f0"}},
            gauge={
                "axis": {"range": [0, max_score], "tickcolor": "#64748b"},
                "bar": {"color": "#c9a84c", "thickness": 0.3},
                "bgcolor": "#0f1623",
                "borderwidth": 1,
                "bordercolor": "#1e2d45",
                "steps": [
                    {"range": [0, max_score*0.4], "color": "#1a1020"},
                    {"range": [max_score*0.4, max_score*0.6], "color": "#1a1a10"},
                    {"range": [max_score*0.6, max_score*0.8], "color": "#101a20"},
                    {"range": [max_score*0.8, max_score], "color": "#0d1f18"},
                ],
            },
            title={"text": "Total Buffett Score", "font": {"size": 16, "color": "#64748b"}},
        ))
        fig.update_layout(
            height=280,
            margin=dict(t=40, b=0, l=20, r=20),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e2e8f0"),
        )
        return fig

    g_col, v_col = st.columns([1, 1])
    with g_col:
        st.plotly_chart(make_gauge(result.total_score, result.total_max), use_container_width=True)
    with v_col:
        color = result.verdict_color
        pct = result.total_pct * 100
        try:
            sig_label, sig_color, buy_tgt, sell_tgt = result.signal
        except Exception:
            sig_label, sig_color, buy_tgt, sell_tgt = ("EVALUAR", "#64748b", None, None)
        iv_display = f"${result.intrinsic_value:.2f}" if result.intrinsic_value else "N/C"
        buy_str  = f"${buy_tgt:.2f}"  if buy_tgt  else "—"
        sell_str = f"${sell_tgt:.2f}" if sell_tgt else "—"
        st.markdown(
            f"<div style='padding:1.5rem; background:#141c2e; border:1px solid #1e2d45; "
            f"border-left:4px solid {color}; border-radius:12px; margin-top:0.5rem'>"
            f"<div style='font-size:0.72rem; text-transform:uppercase; letter-spacing:0.1em; "
            f"color:#64748b; margin-bottom:0.4rem'>Verdict</div>"
            f"<div style='font-size:1.8rem; font-weight:800; color:{color}; line-height:1.1; "
            f"margin-bottom:0.6rem'>{result.verdict}</div>"
            f"<div style='color:#94a3b8; font-size:0.88rem; line-height:1.6'>"
            f"Score: <b style='color:#e2e8f0'>{result.total_score}/{result.total_max}</b> "
            f"({pct:.0f}%)<br>"
            f"<span style='font-size:0.78rem; color:#64748b'>"
            f"80-100 solid · 60-79 radar · 40-59 caution · &lt;40 discard</span>"
            f"</div>"
            f"<div style='margin-top:1rem; padding-top:0.8rem; border-top:1px solid #1e2d45'>"
            f"<div style='font-size:0.72rem; text-transform:uppercase; letter-spacing:0.1em; "
            f"color:#64748b; margin-bottom:0.4rem'>Action signal</div>"
            f"<div style='font-size:1.3rem; font-weight:800; color:{sig_color}; "
            f"margin-bottom:0.5rem'>{sig_label}</div>"
            f"<div style='font-size:0.82rem; color:#94a3b8; line-height:1.8'>"
            f"Estimated IV: <b style='color:#e2e8f0'>{iv_display}</b><br>"
            f"Buy target: <b style='color:#10b981'>{buy_str}</b> &nbsp;·&nbsp; "
            f"Sell target: <b style='color:#ef4444'>{sell_str}</b>"
            f"</div>"
            f"</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # --- Section tabs ---
    def render_section(section):
        pct = section.pct
        color = score_color(pct)
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"### {section.name}")
        with col2:
            st.markdown(
                f"<div style='text-align:right; font-size:1.4rem; font-weight:bold; color:{color}'>"
                f"{section.score}/{section.max_score}</div>", unsafe_allow_html=True,
            )
        st.progress(pct, text=f"{pct*100:.0f}%")
        for c in section.criteria:
            icon = "+" if c.passed else "-"
            with st.expander(f"{icon} {c.name}  —  {c.points_earned}/{c.points_max} pts  |  {c.raw_label}"):
                st.markdown(f"**Criterion:** {c.threshold}")
                st.markdown(f"**Source:** {c.source}")
                st.markdown(f"**Justification:** {c.explanation}")

    tab1, tab2, tab3, tab4 = st.tabs([
        f"Moat  {result.moat.score}/25",
        f"Valuation  {result.valuation.score}/25",
        f"Health  {result.health.score}/25",
        f"Growth  {result.growth.score}/25",
    ])
    with tab1: render_section(result.moat)
    with tab2:
        render_section(result.valuation)
        # DCF sensitivity table
        if result.intrinsic_value and result.current_price:
            with st.expander("Intrinsic Value Range (DCF sensitivity)"):
                st.caption(
                    "Graham formula adjusted for rates: IV = OE/share × (8.5 + 2g) × (4.4 / r). "
                    "The base cell reflects the central scenario used in scoring."
                )
                _info_dcf = metrics.get_info(ticker_input)
                _eps_h = metrics.get_eps_history(ticker_input)
                _eps_s = pd.Series(_eps_h["values"], index=_eps_h["years"]) if _eps_h["values"] else None
                _eps_cagr = metrics.compute_cagr(_eps_s, 5) if _eps_s is not None else 0.05
                _g_base = max(0, min((_eps_cagr or 0.05) * 100, 20))
                _cf_dcf = metrics.get_cashflow(ticker_input)
                _income_dcf = metrics.get_income_statement(ticker_input)
                _shares_dcf = _info_dcf.get("sharesOutstanding") or 1
                _ni_s = metrics.extract_series(_income_dcf, ["Net Income", "NetIncome"])
                _da_s = metrics.extract_series(_cf_dcf, ["Depreciation", "Depreciation And Amortization"])
                _cx_s = metrics.extract_series(_cf_dcf, ["Capital Expenditure", "Capital Expenditures"])
                _oe_per_share = None
                if _ni_s is not None and _shares_dcf:
                    _ly = sorted(_ni_s.index)[-1]
                    _ni = _ni_s.get(_ly, 0) or 0
                    _da = (_da_s.get(_ly, 0) if _da_s is not None else 0) or 0
                    _cx = (_cx_s.get(_ly, 0) if _cx_s is not None else 0) or 0
                    _oe = _ni + _da + _cx
                    if _oe > 0:
                        _oe_per_share = _oe / _shares_dcf
                if _oe_per_share:
                    _rates = [0.08, 0.10, 0.12]
                    _growths = [_g_base * 0.7, _g_base, _g_base * 1.3]
                    _rate_labels = ["Rate 8%", "Rate 10% (base)", "Rate 12%"]
                    _g_labels = [
                        f"g={_growths[0]:.1f}% (low)",
                        f"g={_growths[1]:.1f}% (base)",
                        f"g={_growths[2]:.1f}% (high)",
                    ]
                    _tbl_rows = []
                    for _r_lbl, _r in zip(_rate_labels, _rates):
                        _row_d = {"Discount rate": _r_lbl}
                        for _g_lbl, _g in zip(_g_labels, _growths):
                            _iv_cell = _oe_per_share * (8.5 + 2 * _g) * (4.4 / _r)
                            _mos = (_iv_cell - result.current_price) / _iv_cell * 100
                            _row_d[_g_lbl] = f"${_iv_cell:.2f} (MoS {_mos:+.0f}%)"
                        _tbl_rows.append(_row_d)
                    _df_dcf = pd.DataFrame(_tbl_rows).set_index("Discount rate")
                    st.dataframe(_df_dcf, use_container_width=True)
                    _count_safe = sum(
                        1 for _r in _rates for _g in _growths
                        if _oe_per_share * (8.5 + 2 * _g) * (4.4 / _r) > result.current_price
                    )
                    st.caption(
                        f"Current price ${result.current_price:.2f} offers positive margin "
                        f"in {_count_safe} of 9 scenarios."
                    )
                else:
                    st.info("Insufficient data to build the sensitivity table.")
    with tab3: render_section(result.health)
    with tab4: render_section(result.growth)

    # --- Charts ---
    st.markdown("---")
    st.subheader("Historical Data")
    c1, c2, c3 = st.columns(3)
    with c1:
        roe_data = metrics.get_roe_history(ticker_input)
        if roe_data["values"]:
            df = pd.DataFrame({"Year": roe_data["years"], "ROE": [v*100 for v in roe_data["values"]]})
            fig = px.bar(df, x="Year", y="ROE", title="ROE (%)", color="ROE",
                         color_continuous_scale="RdYlGn")
            fig.add_hline(y=15, line_dash="dash", line_color="#f59e0b", annotation_text="15%",
                          annotation_font_color="#f59e0b")
            _dark_layout(fig, height=300)
            fig.update_layout(showlegend=False, margin=dict(t=40, b=30))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No ROE data")
    with c2:
        rev_data = metrics.get_revenue_history(ticker_input)
        eps_data = metrics.get_eps_history(ticker_input)
        if rev_data["values"]:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=rev_data["years"], y=[v/1e9 for v in rev_data["values"]],
                                     mode="lines+markers", name="Revenue ($B)", yaxis="y1",
                                     line=dict(color="#3498db", width=2)))
            if eps_data["values"]:
                fig.add_trace(go.Scatter(x=eps_data["years"], y=eps_data["values"],
                                         mode="lines+markers", name="EPS ($)", yaxis="y2",
                                         line=dict(color="#10b981", width=2, dash="dot")))
            _dark_layout(fig, height=300)
            fig.update_layout(
                title=dict(text="Revenue and EPS", font=dict(color="#e2e8f0")),
                yaxis=dict(title="Revenue ($B)", gridcolor="#1e2d45", linecolor="#2a3d5a"),
                yaxis2=dict(title="EPS ($)", overlaying="y", side="right",
                            gridcolor="#1e2d45", linecolor="#2a3d5a"),
                legend=dict(orientation="h", y=1.1, font=dict(color="#e2e8f0")),
                margin=dict(t=50, b=30),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No revenue data")
    with c3:
        ph = metrics.get_price_history(ticker_input, period="5y")
        if not ph.empty:
            fig = px.line(ph.reset_index(), x="Date", y="Close", title="5-Year Price")
            fig.update_traces(line_color="#c9a84c")
            _dark_layout(fig, height=300)
            fig.update_layout(margin=dict(t=40, b=30))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No price data")

    # --- Peer comparison ---
    st.markdown("---")
    st.markdown(
        "<div class='section-header'><h3 style='margin:0; color:#e2e8f0'>Sector comparison with peers</h3></div>",
        unsafe_allow_html=True,
    )
    with st.spinner("Loading sector comparison..."):
        peer_comp = peers_mod.compare(ticker_input, info)

    if peer_comp.peer_count == 0:
        st.info("Not enough peers available for sector comparison.")
    else:
        st.caption(
            f"Sector: **{peer_comp.sector}** | Industry: **{peer_comp.industry}** | "
            f"Peers analyzed: {peer_comp.peer_count} "
            f"({', '.join(peer_comp.peer_symbols[:5])}"
            f"{'...' if len(peer_comp.peer_symbols) > 5 else ''})"
        )
        pct_better = sum(1 for m in peer_comp.metrics if m.better_than_peers) / max(len(peer_comp.metrics), 1)
        badge_color = "#2ecc71" if pct_better >= 0.7 else "#e67e22" if pct_better >= 0.4 else "#e74c3c"
        st.markdown(
            f"<div style='font-weight:bold; color:{badge_color}; margin-bottom:0.5rem'>"
            f"{peer_comp.summary}</div>", unsafe_allow_html=True,
        )
        if peer_comp.metrics:
            peer_cols = st.columns(len(peer_comp.metrics))
            for pcol, m in zip(peer_cols, peer_comp.metrics):
                with pcol:
                    color = "#2ecc71" if m.better_than_peers else "#e74c3c"
                    vs_label = "Better than sector" if m.better_than_peers else "Below sector"
                    st.markdown(f"**{m.name}**")
                    st.markdown(
                        f"<div style='font-size:1.4rem; font-weight:bold; color:#e2e8f0'>{m.company_label}</div>"
                        f"<div style='color:{color}; font-size:0.8rem'>{vs_label}<br>"
                        f"<span style='color:#64748b'>({m.sector_label})</span></div>",
                        unsafe_allow_html=True,
                    )
                    st.caption(m.note)

    # --- Capital Allocation Quality (ROIC) ---
    st.markdown("---")
    st.markdown(
        "<div class='section-header'><h3 style='margin:0; color:#e2e8f0'>Capital Allocation Quality</h3></div>",
        unsafe_allow_html=True,
    )
    with st.spinner("Calculating ROIC and capital quality..."):
        cap_data = capital_mod.get_capital_quality(ticker_input)

    if cap_data.get("error"):
        st.info(f"ROIC not available: {cap_data['error']}")
    else:
        _vc = cap_data["verdict_color"]
        _vt = cap_data["verdict"]
        _roic_avg = cap_data["roic_avg"]
        _roic_trend = cap_data["roic_trend"]
        _wacc = cap_data["wacc_est"]
        _spread = cap_data["roic_vs_wacc"]
        _capex_lbl = cap_data["capex_intensity_label"]
        _capex_color = cap_data["capex_intensity_color"]
        _buyback = cap_data["buyback_signal"]

        st.markdown(
            f"<div style='padding:0.8rem 1.2rem; background:#141c2e; border:1px solid #1e2d45; "
            f"border-left:5px solid {_vc}; border-radius:10px; margin-bottom:1rem'>"
            f"<span style='font-size:1.05rem; font-weight:700; color:{_vc}'>{_vt}</span>"
            f"<span style='color:#64748b; font-size:0.85rem; margin-left:0.8rem'>"
            f"Avg ROIC: {_roic_avg:.1f}% · Trend: {_roic_trend}"
            f"{(' · WACC est: ' + str(_wacc) + '%') if _wacc else ''}"
            f"{(' · Spread: ' + ('+' if _spread >= 0 else '') + str(_spread) + '%') if _spread is not None else ''}"
            f"</span></div>",
            unsafe_allow_html=True,
        )

        _rc1, _rc2, _rc3 = st.columns(3)
        with _rc1:
            _buyback_map = {
                "yes": ("Buying back shares", "#10b981"),
                "no": ("Diluting shares", "#ef4444"),
                "neutral": ("No clear trend", "#64748b"),
            }
            _bb_lbl, _bb_col = _buyback_map.get(_buyback, ("—", "#64748b"))
            st.markdown(
                f"<div style='text-align:center; padding:0.8rem; background:#141c2e; "
                f"border:1px solid #1e2d45; border-radius:10px'>"
                f"<div style='font-size:0.7rem; color:#64748b; text-transform:uppercase; "
                f"letter-spacing:0.08em; margin-bottom:0.3rem'>Buybacks</div>"
                f"<div style='font-size:1rem; font-weight:700; color:{_bb_col}'>{_bb_lbl}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
        with _rc2:
            st.markdown(
                f"<div style='text-align:center; padding:0.8rem; background:#141c2e; "
                f"border:1px solid #1e2d45; border-radius:10px'>"
                f"<div style='font-size:0.7rem; color:#64748b; text-transform:uppercase; "
                f"letter-spacing:0.08em; margin-bottom:0.3rem'>Capex Intensity</div>"
                f"<div style='font-size:1rem; font-weight:700; color:{_capex_color}'>"
                f"{_capex_lbl or '—'}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
        with _rc3:
            _spread_color = "#10b981" if (_spread is not None and _spread > 0) else "#ef4444"
            st.markdown(
                f"<div style='text-align:center; padding:0.8rem; background:#141c2e; "
                f"border:1px solid #1e2d45; border-radius:10px'>"
                f"<div style='font-size:0.7rem; color:#64748b; text-transform:uppercase; "
                f"letter-spacing:0.08em; margin-bottom:0.3rem'>ROIC vs WACC</div>"
                f"<div style='font-size:1rem; font-weight:700; color:{_spread_color}'>"
                f"{('+' if _spread >= 0 else '') + str(_spread) + ' pp' if _spread is not None else '—'}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

        # ROIC history chart
        if cap_data["roic_history"]:
            _rh = cap_data["roic_history"]
            _fig_roic = go.Figure()
            _fig_roic.add_trace(go.Scatter(
                x=[r[0] for r in _rh],
                y=[r[1] for r in _rh],
                mode="lines+markers",
                name="ROIC %",
                line=dict(color="#c9a84c", width=2),
                marker=dict(size=6, color="#c9a84c"),
            ))
            if _wacc:
                _fig_roic.add_hline(
                    y=_wacc, line_dash="dash", line_color="#64748b",
                    annotation_text=f"WACC est. {_wacc}%",
                    annotation_font_color="#64748b",
                )
            _dark_layout(_fig_roic, height=260)
            _fig_roic.update_layout(
                title=dict(text="ROIC history (%)", font=dict(color="#e2e8f0")),
                yaxis=dict(title="ROIC %", gridcolor="#1e2d45", linecolor="#2a3d5a"),
                xaxis=dict(title="Year", linecolor="#2a3d5a"),
                margin=dict(t=50, b=30),
                showlegend=False,
            )
            st.plotly_chart(_fig_roic, use_container_width=True)

    # --- Insider activity ---
    st.markdown("---")
    st.markdown(
        "<div class='section-header'><h3 style='margin:0; color:#e2e8f0'>Insider Activity</h3></div>",
        unsafe_allow_html=True,
    )
    with st.spinner("Fetching insider transactions..."):
        ins_data = insider_mod.get_insider_signal(ticker_input)

    if ins_data.get("error"):
        st.info(f"Insider data not available: {ins_data['error']}")
    else:
        _is_color = ins_data["signal_color"]
        _is_label = ins_data["signal_label"]
        _net_usd  = ins_data["net_6m_usd"]
        _buys     = ins_data["buy_count"]
        _sells    = ins_data["sell_count"]
        _txs      = ins_data["recent_transactions"]

        def _fmt_m(v):
            if v is None: return "—"
            if abs(v) >= 1e6: return f"${v/1e6:.1f}M"
            if abs(v) >= 1e3: return f"${v/1e3:.0f}K"
            return f"${v:.0f}"

        _ins_c1, _ins_c2, _ins_c3 = st.columns(3)
        with _ins_c1:
            st.markdown(
                f"<div style='text-align:center; padding:0.8rem; background:#141c2e; "
                f"border:1px solid #1e2d45; border-radius:10px'>"
                f"<div style='font-size:0.7rem; color:#64748b; text-transform:uppercase; "
                f"letter-spacing:0.08em; margin-bottom:0.3rem'>Signal (6 months)</div>"
                f"<div style='font-size:1.1rem; font-weight:800; color:{_is_color}'>{_is_label}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
        with _ins_c2:
            st.markdown(
                f"<div style='text-align:center; padding:0.8rem; background:#141c2e; "
                f"border:1px solid #1e2d45; border-radius:10px'>"
                f"<div style='font-size:0.7rem; color:#64748b; text-transform:uppercase; "
                f"letter-spacing:0.08em; margin-bottom:0.3rem'>Net (buys - sells)</div>"
                f"<div style='font-size:1.05rem; font-weight:700; "
                f"color:{'#10b981' if (_net_usd or 0) >= 0 else '#ef4444'}'>"
                f"{_fmt_m(_net_usd)}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
        with _ins_c3:
            st.markdown(
                f"<div style='text-align:center; padding:0.8rem; background:#141c2e; "
                f"border:1px solid #1e2d45; border-radius:10px'>"
                f"<div style='font-size:0.7rem; color:#64748b; text-transform:uppercase; "
                f"letter-spacing:0.08em; margin-bottom:0.3rem'>Transactions</div>"
                f"<div style='font-size:0.9rem; font-weight:700; color:#e2e8f0'>"
                f"<span style='color:#10b981'>{_buys} buys</span> · "
                f"<span style='color:#ef4444'>{_sells} sells</span></div>"
                f"</div>",
                unsafe_allow_html=True,
            )

        if _txs:
            st.markdown("<div style='margin-top:0.8rem'></div>", unsafe_allow_html=True)
            for tx in _txs[:3]:
                _tx_type = tx.get("transaction", "—")
                _is_buy_tx = any(k in _tx_type.lower() for k in ["purchase", "buy", "acquisition", "grant"])
                _tx_color = "#10b981" if _is_buy_tx else "#ef4444"
                st.markdown(
                    f"<div style='font-size:0.82rem; padding:0.4rem 0.8rem; background:#141c2e; "
                    f"border:1px solid #1e2d45; border-left:3px solid {_tx_color}; "
                    f"border-radius:6px; margin-bottom:0.3rem; color:#e2e8f0'>"
                    f"<b>{tx.get('date','—')}</b>  ·  {tx.get('insider','—')}  ·  "
                    f"<span style='color:{_tx_color}'>{_tx_type}</span>"
                    f"{('  ·  ' + _fmt_m(tx['value_usd'])) if tx.get('value_usd') else ''}"
                    f"</div>",
                    unsafe_allow_html=True,
                )

    # --- Methodology + raw data ---
    with st.expander("How this analysis is calculated"):
        st.markdown("""
**Moat (25 pts):** 5-year historical ROE (>15% each year = 15pts), net margin >15% (5pts),
operating margin stability — standard deviation <5pp (5pts).

**Valuation (25 pts):** Trailing P/E (<=15=10pts, <=25=5pts), P/B (<=1.5=8pts, <=3=4pts),
margin of safety via simplified DCF: IV = Owner Earnings/share * (8.5 + 2*g) (7pts).

**Health (25 pts):** Debt/Equity (<0.5=10pts, <1=5pts), current ratio (>=1.5=8pts, >=1=4pts),
positive FCF (7pts).

**Growth (25 pts):** Revenue CAGR 5y (>=10%=8pts, >=5%=4pts), EPS CAGR 5y (>=10%=9pts, >=5%=5pts),
book value CAGR 5y (>=7%=8pts, >=3%=4pts).

*Source: Warren Buffett letters to shareholders (1977-2024), The Warren Buffett Way (Hagstrom),
The Intelligent Investor (Graham).*
        """)
    with st.expander("Raw yfinance data"):
        raw = {
            "P/E trailing": info.get("trailingPE"),
            "P/E forward": info.get("forwardPE"),
            "P/B": info.get("priceToBook"),
            "EV/EBITDA": info.get("enterpriseToEbitda"),
            "ROE": f"{(info.get('returnOnEquity') or 0)*100:.1f}%",
            "Net margin": f"{(info.get('profitMargins') or 0)*100:.1f}%",
            "D/E": f"{(info.get('debtToEquity') or 0)/100:.2f}x",
            "Current ratio": info.get("currentRatio"),
            "FCF": fmt_cap(info.get("freeCashflow")),
            "Beta": info.get("beta"),
            "52w High": info.get("fiftyTwoWeekHigh"),
            "52w Low": info.get("fiftyTwoWeekLow"),
        }
        df = pd.DataFrame([(k, str(v) if v else "N/A") for k, v in raw.items()], columns=["Metric", "Value"])
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.caption("Data: Yahoo Finance. Educational analysis — not financial advice.")


# ===========================================================================
# MODE 2: Ranking
# ===========================================================================

elif mode == "Ranking":
    st.markdown(
        "<span style='font-size:2rem; font-weight:800; color:#c9a84c'>Ranking</span>"
        "<span style='color:#64748b; font-size:1rem; margin-left:0.8rem'>Companies analyzed</span>",
        unsafe_allow_html=True,
    )

    last_run = batch.get_last_run_time()
    if last_run:
        try:
            dt = datetime.fromisoformat(last_run)
            st.caption(f"Last analysis: {dt.strftime('%Y-%m-%d %H:%M')}")
        except Exception:
            st.caption(f"Last analysis: {last_run}")
    else:
        st.warning(
            "No cached results yet. "
            "Go to **My Watchlist** and run the batch analysis, "
            "or run `python3 batch.py` in the terminal."
        )

    ranked = batch.get_ranked_results()

    if not ranked:
        st.info("No results. Run a batch analysis first.")
        st.stop()

    # Score distribution chart
    scores = [r["total_score"] for r in ranked]
    names = [r.get("company_name", r["symbol"])[:20] for r in ranked]
    symbols = [r["symbol"] for r in ranked]
    colors = [score_color(s / 100) for s in scores]

    fig = go.Figure(go.Bar(
        x=symbols,
        y=scores,
        text=[f"{s}/100" for s in scores],
        textposition="outside",
        marker_color=colors,
        hovertext=[f"{n}<br>{s}/100 — {r.get('verdict','')}" for n, s, r in zip(names, scores, ranked)],
        hoverinfo="text",
    ))
    fig.add_hline(y=80, line_dash="dash", line_color="#10b981", annotation_text="Strong (80)",
                  annotation_font_color="#10b981")
    fig.add_hline(y=60, line_dash="dash", line_color="#3b82f6", annotation_text="On radar (60)",
                  annotation_font_color="#3b82f6")
    fig.add_hline(y=40, line_dash="dot", line_color="#f59e0b", annotation_text="Caution (40)",
                  annotation_font_color="#f59e0b")
    _dark_layout(fig, height=400)
    fig.update_layout(
        title=dict(text="Buffett Score by Company", font=dict(color="#e2e8f0")),
        yaxis=dict(range=[0, 105], title="Score", gridcolor="#1e2d45", linecolor="#2a3d5a"),
        xaxis=dict(title="", linecolor="#2a3d5a"),
        margin=dict(t=50, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Ranking table
    st.markdown("### Detailed Table")

    col_filter1, col_filter2 = st.columns([1, 2])
    with col_filter1:
        min_score = st.slider("Minimum score", 0, 100, 0, step=5)
    with col_filter2:
        sectors = sorted(set(r.get("sector", "N/A") for r in ranked))
        sector_filter = st.multiselect("Filter by sector", sectors, default=[])

    filtered = [
        r for r in ranked
        if r["total_score"] >= min_score
        and (not sector_filter or r.get("sector") in sector_filter)
    ]

    rows = []
    for r in filtered:
        rows.append({
            "Ticker": r["symbol"],
            "Company": r.get("company_name", "")[:30],
            "Sector": r.get("sector", "N/A"),
            "Score": r["total_score"],
            "Moat": r.get("moat", {}).get("score", 0),
            "Valuation": r.get("valuation", {}).get("score", 0),
            "Health": r.get("health", {}).get("score", 0),
            "Growth": r.get("growth", {}).get("score", 0),
            "Verdict": r.get("verdict", ""),
            "Price": f"${r['current_price']:.2f}" if r.get("current_price") else "N/A",
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        st.dataframe(
            _score_style(df),
            use_container_width=True,
            hide_index=True,
        )
        # Download as CSV
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download CSV",
            data=csv,
            file_name=f"buffett_ranking_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )
    else:
        st.info("No results with the selected filters.")


# ===========================================================================
# MODE 3: Recomendaciones
# ===========================================================================

elif mode == "Recommendations":

    # Drill-down: if a symbol is selected, show detail panel instead of the list
    if st.session_state.get("rec_drill"):
        _show_drill_down(st.session_state["rec_drill"])
        st.stop()

    st.markdown(
        "<div style='margin-bottom:0.5rem'>"
        "<span style='font-size:2rem; font-weight:800; color:#c9a84c'>Recommendations</span>"
        "</div>"
        "<div style='color:#64748b; font-size:0.9rem; margin-bottom:1rem'>"
        "The system reviews all batch analysis results and selects "
        "the best candidates according to Buffett criteria. Only companies with "
        "sufficient data and verified scores are shown."
        "</div>",
        unsafe_allow_html=True,
    )

    all_results = batch.get_ranked_results(min_score=0)
    if not all_results:
        st.warning(
            "No results yet. Go to **My Watchlist** and run the batch analysis, "
            "or run `python3 batch.py --screener` in the terminal."
        )
        st.stop()

    last_run = batch.get_last_run_time()
    if last_run:
        try:
            dt = datetime.fromisoformat(last_run)
            st.caption(f"Based on analysis from {dt.strftime('%Y-%m-%d %H:%M')} — {len(all_results)} companies analyzed")
        except Exception:
            pass

    # Pre-compute conviction score for every result (no network — from cache only)
    for r in all_results:
        r["_conviction"], r["_conv_label"], r["_conv_color"] = _conviction_score(r)

    # Tiers — quality defines the tier; conviction defines the order within each tier
    top_tier   = sorted([r for r in all_results if r["total_score"] >= 80],
                        key=lambda x: x["_conviction"], reverse=True)
    radar_tier = sorted([r for r in all_results if 60 <= r["total_score"] < 80],
                        key=lambda x: x["_conviction"], reverse=True)
    watch_tier = sorted([r for r in all_results if 50 <= r["total_score"] < 60],
                        key=lambda x: x["_conviction"], reverse=True)
    below_tier = sorted([r for r in all_results if r["total_score"] < 50],
                        key=lambda x: x["_conviction"], reverse=True)

    def _avg_conviction(tier_list: list) -> int:
        if not tier_list:
            return 0
        return round(sum(r["_conviction"] for r in tier_list) / len(tier_list))

    def render_rec_card(r: dict, border_color: str):
        sc      = r["total_score"]
        moat    = r.get("moat", {}).get("score", 0)
        val     = r.get("valuation", {}).get("score", 0)
        health  = r.get("health", {}).get("score", 0)
        growth  = r.get("growth", {}).get("score", 0)
        strengths = []
        if moat    >= 20: strengths.append(f"Strong moat ({moat}/25)")
        if val     >= 18: strengths.append(f"Good value ({val}/25)")
        if health  >= 20: strengths.append(f"Solid balance sheet ({health}/25)")
        if growth  >= 18: strengths.append(f"Outstanding growth ({growth}/25)")
        sector = r.get("sector", "N/A")
        price  = f"${r['current_price']:.2f}" if r.get("current_price") else "N/A"

        conv       = r["_conviction"]
        conv_label = r["_conv_label"]
        conv_color = r["_conv_color"]

        # Conviction sub-indicators for the badge row
        iv    = r.get("intrinsic_value") or 0
        price_v = r.get("current_price") or 0
        mos_pct = round((iv - price_v) / iv * 100) if iv > 0 and price_v > 0 else None
        mos_str = f"{mos_pct:+d}%" if mos_pct is not None else "N/A"
        insider_sig   = (r.get("insider") or {}).get("signal", "N/A")
        insider_color = {"BULLISH": "#10b981", "BEARISH": "#ef4444", "NEUTRAL": "#94a3b8"}.get(insider_sig, "#94a3b8")
        roic_avg = (r.get("capital") or {}).get("roic_avg")
        roic_str = f"{roic_avg:.1f}%" if roic_avg is not None else "N/A"

        # Timing badge
        pm      = r.get("price_metrics") or {}
        pct_low = pm.get("pct_from_52w_low")
        dist200 = pm.get("dist_from_200dma_pct")
        if pct_low is not None and pct_low <= 25 and dist200 is not None and dist200 < 0:
            timing_str, timing_color = "Low zone + below MA200", "#10b981"
        elif pct_low is not None and pct_low <= 40:
            timing_str, timing_color = f"Low zone ({pct_low:.0f}%)", "#3b82f6"
        elif pct_low is not None and pct_low <= 60:
            timing_str, timing_color = f"Mid zone ({pct_low:.0f}%)", "#f59e0b"
        elif pct_low is not None:
            timing_str, timing_color = f"High zone ({pct_low:.0f}%)", "#ef4444"
        else:
            timing_str, timing_color = "No data", "#64748b"

        st.markdown(
            f"<div style='background:#141c2e; border:1px solid #1e2d45; "
            f"border-left:5px solid {border_color}; border-radius:10px; "
            f"padding:0.9rem 1.2rem; margin-bottom:0.4rem'>"
            f"<div style='display:flex; justify-content:space-between; align-items:center'>"
            f"<span style='font-size:1.15rem; font-weight:700; color:#e2e8f0'>{r['symbol']}"
            f"  <span style='font-size:0.85rem; color:#64748b; font-weight:400'>"
            f"{r.get('company_name','')[:35]}</span></span>"
            f"<div style='text-align:right'>"
            f"<div style='font-size:1.4rem; font-weight:800; color:{border_color}'>{sc}/100</div>"
            f"<div style='font-size:0.78rem; color:{conv_color}; font-weight:600'>"
            f"Conviction: {conv}/100 — {conv_label}</div>"
            f"</div>"
            f"</div>"
            f"<div style='color:#64748b; font-size:0.82rem; margin:0.25rem 0'>"
            f"{sector} | Price: {price}</div>"
            f"<div style='font-size:0.83rem; color:#94a3b8; margin-top:0.4rem'>"
            f"{'  ·  '.join(strengths) if strengths else 'Balanced score across all pillars.'}"
            f"</div>"
            # Mini-badge row: MOS | Insiders | ROIC | Timing
            f"<div style='display:flex; flex-wrap:wrap; gap:0.5rem; margin-top:0.55rem; font-size:0.78rem'>"
            f"<span style='background:#0f172a; border-radius:6px; padding:0.2rem 0.5rem; color:#94a3b8'>"
            f"MOS: <b style='color:#e2e8f0'>{mos_str}</b></span>"
            f"<span style='background:#0f172a; border-radius:6px; padding:0.2rem 0.5rem; color:#94a3b8'>"
            f"Insiders: <b style='color:{insider_color}'>{insider_sig}</b></span>"
            f"<span style='background:#0f172a; border-radius:6px; padding:0.2rem 0.5rem; color:#94a3b8'>"
            f"ROIC: <b style='color:#e2e8f0'>{roic_str}</b></span>"
            f"<span style='background:#0f172a; border-radius:6px; padding:0.2rem 0.5rem; color:#94a3b8'>"
            f"Timing: <b style='color:{timing_color}'>{timing_str}</b></span>"
            f"</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
        if st.button("View analysis", key=f"drill_{r['symbol']}", use_container_width=True):
            st.session_state["rec_drill"] = r["symbol"]
            st.rerun()

    def _tier_table(tier_list: list):
        """Render a compact dataframe for lower tiers with a drill-down button per row."""
        rows = []
        for r in tier_list:
            iv    = r.get("intrinsic_value") or 0
            price_v = r.get("current_price") or 0
            mos_pct = round((iv - price_v) / iv * 100) if iv > 0 and price_v > 0 else None
            rows.append({
                "Ticker":      r["symbol"],
                "Company":     r.get("company_name", "")[:35],
                "Quality":     r["total_score"],
                "Conviction":  r["_conviction"],
                "MOS%":        f"{mos_pct:+d}%" if mos_pct is not None else "N/A",
                "Insiders":    (r.get("insider") or {}).get("signal", "N/A"),
                "ROIC%":       f"{(r.get('capital') or {}).get('roic_avg'):.1f}%"
                               if (r.get("capital") or {}).get("roic_avg") is not None else "N/A",
                "Sector":      r.get("sector", "N/A"),
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.markdown("**View company detail:**")
        cols = st.columns(min(len(tier_list), 6))
        for i, r in enumerate(tier_list):
            with cols[i % 6]:
                if st.button(r["symbol"], key=f"drill_{r['symbol']}", use_container_width=True):
                    st.session_state["rec_drill"] = r["symbol"]
                    st.rerun()

    # --- Candidatos solidos ---
    avg_conv_top = _avg_conviction(top_tier)
    st.markdown(
        f"<div class='section-header'><h3 style='margin:0'>Strong Candidates — Score >= 80"
        f"  <span style='font-size:0.9rem; font-weight:400; color:#64748b'>"
        f"({len(top_tier)} companies"
        f"{f'  |  Avg conviction: {avg_conv_top}/100' if top_tier else ''})</span>"
        f"</h3></div>",
        unsafe_allow_html=True,
    )
    if top_tier:
        cols_t = st.columns(min(len(top_tier), 2))
        for i, r in enumerate(top_tier):
            with cols_t[i % 2]:
                render_rec_card(r, "#2ecc71")
    else:
        st.info("No ticker has reached 80+ points yet. Expand the screener to find candidates.")

    st.markdown("---")

    # --- En el radar ---
    avg_conv_radar = _avg_conviction(radar_tier)
    st.markdown(
        f"<div class='section-header'><h3 style='margin:0'>On the Radar — Score 60-79"
        f"  <span style='font-size:0.9rem; font-weight:400; color:#64748b'>"
        f"({len(radar_tier)} companies"
        f"{f'  |  Avg conviction: {avg_conv_radar}/100' if radar_tier else ''})</span>"
        f"</h3></div>",
        unsafe_allow_html=True,
    )
    if radar_tier:
        cols_r = st.columns(min(len(radar_tier), 2))
        for i, r in enumerate(radar_tier):
            with cols_r[i % 2]:
                render_rec_card(r, "#3498db")
    else:
        st.info("No results in the 60-79 range.")

    st.markdown("---")

    # --- A vigilar (tabla compacta) ---
    with st.expander(f"Watch List (Score 50-59) — {len(watch_tier)} companies"):
        if watch_tier:
            _tier_table(watch_tier)
        else:
            st.info("No results in the 50-59 range.")

    # --- Por debajo (tabla compacta, colapsada) ---
    if below_tier:
        with st.expander(f"Below threshold (Score < 50) — {len(below_tier)} companies"):
            _tier_table(below_tier)

    st.caption("Educational analysis. Not financial advice.")


# ===========================================================================
# MODE 4: Watchlist management
# ===========================================================================

elif mode == "My Watchlist":
    st.markdown(
        "<span style='font-size:2rem; font-weight:800; color:#c9a84c'>My Watchlist</span>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='color:#64748b; font-size:0.9rem; margin-bottom:1rem'>"
        "List of companies the bot analyzes on each scheduled run."
        "</div>",
        unsafe_allow_html=True,
    )

    current = wl.load()

    # Add ticker
    col_add, col_btn = st.columns([3, 1])
    with col_add:
        new_ticker = st.text_input("Add ticker", placeholder="e.g. JNJ").strip().upper()
    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Add", use_container_width=True):
            if new_ticker:
                added = wl.add(new_ticker)
                if added:
                    st.success(f"{new_ticker} added to watchlist.")
                else:
                    st.warning(f"{new_ticker} is already in the watchlist.")
                current = wl.load()

    st.markdown("---")
    st.subheader(f"Companies in watchlist ({len(current)})")

    # Show each with remove button
    for ticker in current:
        col_t, col_score, col_rm = st.columns([2, 3, 1])
        with col_t:
            st.markdown(f"**{ticker}**")
        with col_score:
            # Show cached score if available
            cached = batch.load_cache().get("results", {}).get(ticker)
            if cached and not cached.get("blocked") and not cached.get("error"):
                score = cached.get("total_score", 0)
                color = score_color(score / 100)
                st.markdown(
                    f"<span style='color:{color}'>{score}/100 — {cached.get('verdict','')}</span>",
                    unsafe_allow_html=True,
                )
            else:
                st.caption("No recent analysis")
        with col_rm:
            if st.button("Remove", key=f"rm_{ticker}"):
                wl.remove(ticker)
                st.rerun()

    st.markdown("---")

    # Batch run button
    st.subheader("Run batch analysis")
    col_opt1, col_opt2 = st.columns(2)
    with col_opt1:
        include_screener = st.checkbox("Include S&P 500 screener candidates", value=False)
    with col_opt2:
        force_refresh = st.checkbox("Force re-analysis (ignore cache)", value=False)

    if st.button("Analyze watchlist now", type="primary"):
        tickers_to_run = list(current)
        if include_screener:
            with st.spinner("Fetching screener candidates..."):
                import screener as sc
                candidates = sc.get_candidates(use_cache=True)
                existing = set(tickers_to_run)
                tickers_to_run += [t for t in candidates if t not in existing]
            st.info(f"Screener added {len(tickers_to_run) - len(current)} new candidates")

        progress_bar = st.progress(0)
        status_text = st.empty()
        total = len(tickers_to_run)

        def ui_progress(current_n, total_n, ticker, status):
            pct = current_n / total_n
            progress_bar.progress(pct)
            status_text.text(f"[{current_n}/{total_n}] {ticker}: {status}")

        cache_hours = None if force_refresh else 11
        with st.spinner(f"Analyzing {total} companies..."):
            batch.run(tickers_to_run, use_cache_age_hours=cache_hours, progress_callback=ui_progress)

        progress_bar.progress(1.0)
        status_text.text("Analysis complete.")
        st.success(f"Analysis complete. Go to **Ranking** to see the results.")
        st.rerun()

    # Scheduler instructions
    with st.expander("How to automate analysis (scheduler)"):
        st.markdown("""
**Option 1 — Simple terminal (recommended to start):**
```bash
cd warren_buffett_bot
python3 scheduler.py --interval daily --screener --run-now
```
Runs Monday through Friday at 17:00 ET (after market close).

**Option 2 — Auto-start on macOS:**
```bash
python3 scheduler.py --launchd
```
Prints instructions to create a LaunchAgent that starts with the system.

**The scheduler:**
- Analyzes your watchlist + screener candidates
- Saves results in `data/results_cache.json`
- The Streamlit app reads that file — the scheduler does not need to be running
        """)


# ===========================================================================
# MODE 4: Screener Global
# ===========================================================================

elif mode == "Global Screener":
    import screener as sc
    import os, json

    st.markdown(
        "<span style='font-size:2rem; font-weight:800; color:#c9a84c'>Screener Global</span>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='color:#64748b; font-size:0.9rem; margin-bottom:1rem'>"
        "Select the markets you want to scan. The screener applies a "
        "<b style='color:#e2e8f0'>quick filter</b> "
        "(ROE &gt; 12%, D/E &lt; 1.5, cap &gt; $300M, positive margin) "
        "to narrow the universe to real candidates before the full Buffett analysis."
        "</div>",
        unsafe_allow_html=True,
    )

    # --- Market selection by region (persisted across sessions) ---
    st.subheader("Select markets")
    _saved_markets = prefs_mod.get("selected_markets", ["us_sp500"])
    regions = mkt.markets_by_region()
    selected_markets = []
    region_cols = st.columns(len(regions))
    for col, (region, mkt_keys) in zip(region_cols, regions.items()):
        with col:
            st.markdown(f"**{region}**")
            for key in mkt_keys:
                name = mkt.market_name(key)
                default = key in _saved_markets
                if st.checkbox(name, key=f"mkt_{key}", value=default):
                    selected_markets.append(key)

    if not selected_markets:
        st.info("Select at least one market to continue.")
        st.stop()

    # --- Cache info ---
    cache_key = "_".join(sorted(selected_markets))
    cache_path = os.path.join(
        os.path.dirname(__file__), "data", f"screener_cache_{cache_key}.json"
    )

    col_info, col_btn = st.columns([3, 1])
    with col_info:
        if os.path.exists(cache_path):
            try:
                with open(cache_path) as f:
                    sc_cache = json.load(f)
                ts = datetime.fromisoformat(sc_cache["timestamp"])
                st.info(
                    f"Cache available: **{len(sc_cache['candidates'])} candidates** "
                    f"from {sc_cache.get('total_universe', '?')} companies. "
                    f"Updated: {ts.strftime('%Y-%m-%d %H:%M')}"
                )
            except Exception:
                st.warning("Cache not available or corrupted. Run the screener.")
    with col_btn:
        run_screener_btn = st.button("Run screener", type="primary", use_container_width=True)

    if run_screener_btn:
        import time as _time
        import yfinance as yf

        with st.spinner(f"Fetching tickers from {len(selected_markets)} markets..."):
            universe = mkt.get_tickers_multi(selected_markets)

        progress_bar = st.progress(0)
        status_txt = st.empty()
        status_txt.text(f"Universe: {len(universe)} tickers. Applying pre-filter...")

        total = len(universe)
        candidates = []
        for i, ticker in enumerate(universe):
            try:
                inf = yf.Ticker(ticker).info
                if not inf or inf.get("marketCap") is None:
                    continue
                market_cap = inf.get("marketCap", 0) or 0
                roe = inf.get("returnOnEquity") or 0
                de_raw = inf.get("debtToEquity")
                de = (de_raw / 100) if de_raw is not None else None
                profit_margin = inf.get("profitMargins") or 0
                qt = str(inf.get("quoteType", "")).lower()
                if qt not in ("equity", "stock", "") or market_cap < 300_000_000:
                    continue
                if roe >= 0.12 and profit_margin > 0 and (de is None or de < 1.5):
                    candidates.append(ticker)
            except Exception:
                pass
            _time.sleep(0.3)
            progress_bar.progress((i + 1) / total)
            status_txt.text(f"[{i+1}/{total}] — {len(candidates)} candidates so far")

        progress_bar.progress(1.0)
        status_txt.text(f"Screener complete: {len(candidates)} candidates found.")

        os.makedirs(os.path.join(os.path.dirname(__file__), "data"), exist_ok=True)
        with open(cache_path, "w") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "markets": selected_markets,
                "total_universe": total,
                "candidates": candidates,
            }, f, indent=2)
        # Remember this market selection for next session
        prefs_mod.set_pref("selected_markets", selected_markets)
        st.success(f"{len(candidates)} companies passed Buffett's quick filter.")
        st.rerun()

    # --- Show candidates ---
    if os.path.exists(cache_path):
        try:
            with open(cache_path) as f:
                sc_cache = json.load(f)
            candidates = sc_cache.get("candidates", [])
        except Exception:
            candidates = []

        if candidates:
            st.markdown(f"### {len(candidates)} pre-filtered candidates")

            batch_cache = batch.load_cache().get("results", {})
            current_wl = wl.load()
            rows = []
            for t in candidates:
                r = batch_cache.get(t)
                has_result = r and not r.get("blocked") and not r.get("error")
                score = r.get("total_score") if has_result else None
                rows.append({
                    "Ticker": t,
                    "Score": score if score is not None else "Pending",
                    "Verdict": r.get("verdict", "—") if has_result else "—",
                    "Sector": r.get("sector", "—") if has_result else "—",
                    "In watchlist": "Yes" if t in current_wl else "No",
                })
            df = pd.DataFrame(rows)
            analyzed = df[df["Score"] != "Pending"].copy()
            pending = df[df["Score"] == "Pending"]

            if not analyzed.empty:
                analyzed["Score"] = analyzed["Score"].astype(int)
                analyzed = analyzed.sort_values("Score", ascending=False)
                st.markdown("**Analyzed:**")
                st.dataframe(
                    _score_style(analyzed, "Score"),
                    use_container_width=True, hide_index=True,
                )

            if not pending.empty:
                st.markdown(f"**Pending analysis: {len(pending)}**")
                st.caption(
                    "Go to **My Watchlist** and run the batch analysis with "
                    "'Include S&P 500 screener candidates' to score them."
                )
                st.dataframe(pending, use_container_width=True, hide_index=True)

            st.markdown("---")
            ticker_to_add = st.selectbox(
                "Add candidate to my watchlist",
                options=[""] + candidates,
            )
            if ticker_to_add and st.button(f"Add {ticker_to_add} to watchlist"):
                added = wl.add(ticker_to_add)
                st.success(f"{ticker_to_add} added." if added else f"{ticker_to_add} is already in your watchlist.")

    st.caption("Data: Wikipedia + Yahoo Finance. Educational analysis — not financial advice.")


# ===========================================================================
# MODE 5: Mi Portafolio
# ===========================================================================

elif mode == "My Portfolio":
    st.markdown(
        "<span style='font-size:2rem; font-weight:800; color:#c9a84c'>My Portfolio</span>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='color:#64748b; font-size:0.9rem; margin-bottom:1rem'>"
        "Define your positions and analyze the quality and diversification of your portfolio "
        "according to Warren Buffett's criteria."
        "</div>",
        unsafe_allow_html=True,
    )

    # --- Add / update holding ---
    st.subheader("Manage positions")
    col_sym, col_w, col_ep, col_ed, col_btn = st.columns([2, 1, 1, 1, 1])
    with col_sym:
        new_sym = st.text_input("Ticker", placeholder="e.g. AAPL").strip().upper()
    with col_w:
        new_weight = st.number_input("Weight (%)", min_value=0.1, max_value=100.0, value=10.0, step=0.5)
    with col_ep:
        new_entry_price = st.number_input(
            "Entry price ($)", min_value=0.0, value=0.0, step=0.01,
            format="%.2f", help="Price at which you bought. 0 = do not record."
        )
    with col_ed:
        new_entry_date = st.text_input(
            "Entry date", placeholder="2024-01-15",
            help="Format YYYY-MM-DD. Optional."
        ).strip()
    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Add / Update", use_container_width=True):
            if new_sym:
                ep = new_entry_price if new_entry_price > 0 else None
                ed = new_entry_date if new_entry_date else None
                portfolio_mod.upsert_with_basis(new_sym, new_weight, ep, ed)
                st.success(f"{new_sym} saved with weight {new_weight:.1f}%")
                st.rerun()

    holdings_raw = portfolio_mod.load()
    if not holdings_raw:
        st.info("Your portfolio is empty. Add positions above.")
        st.stop()

    # --- Current holdings ---
    st.markdown("---")
    total_w = sum(h.get("weight", 0) for h in holdings_raw)
    st.subheader(f"Current positions ({len(holdings_raw)}) — Total weight: {total_w:.1f}%")
    for h in holdings_raw:
        sym = h["symbol"]
        norm_w = h["weight"] / total_w if total_w > 0 else 0
        c_sym, c_bar, c_rm = st.columns([2, 4, 1])
        with c_sym:
            st.markdown(f"**{sym}** ({h['weight']:.1f}%)")
        with c_bar:
            st.progress(min(norm_w, 1.0))
        with c_rm:
            if st.button("Remove", key=f"prm_{sym}"):
                portfolio_mod.remove(sym)
                st.rerun()

    # --- Portfolio analysis ---
    st.markdown("---")
    st.subheader("Portfolio analysis")
    with st.spinner("Calculating Buffett portfolio analysis..."):
        pa = portfolio_mod.analyze()

    if pa is None:
        st.warning(
            "No Buffett analysis data found for the portfolio positions. "
            "Go to **My Watchlist**, add your tickers and run the batch analysis first."
        )
    else:
        # Summary metrics
        if pa.weighted_score is not None:
            mc1, mc2, mc3 = st.columns(3)
            mc1.metric("Weighted Buffett score", f"{pa.weighted_score:.0f}/100")
            mc2.metric("Diversification", pa.diversification_score)
            mc3.metric("Positions with analysis", len(pa.holdings))

        st.markdown(
            f"<div style='font-size:1.05rem; font-weight:600; margin:1rem 0; "
            f"padding:0.8rem 1rem; background:#141c2e; border-radius:8px; "
            f"border-left:4px solid #c9a84c; color:#e2e8f0'>{pa.summary}</div>",
            unsafe_allow_html=True,
        )

        # Alpha vs S&P500 banner
        if pa.sp500_return_pct is not None and pa.portfolio_alpha is not None:
            _alpha_color = "#10b981" if pa.portfolio_alpha >= 0 else "#ef4444"
            _alpha_sign  = "+" if pa.portfolio_alpha >= 0 else ""
            st.markdown(
                f"<div style='padding:0.9rem 1.2rem; background:#141c2e; border:1px solid #1e2d45; "
                f"border-left:5px solid {_alpha_color}; border-radius:10px; margin-bottom:1rem'>"
                f"<div style='font-size:0.72rem; text-transform:uppercase; letter-spacing:0.1em; "
                f"color:#64748b; margin-bottom:0.3rem'>Performance vs S&P500 (annualized)</div>"
                f"<div style='font-size:1.15rem; font-weight:800; color:{_alpha_color}'>"
                f"Alpha: {_alpha_sign}{pa.portfolio_alpha:.2f}% annualized</div>"
                f"<div style='font-size:0.83rem; color:#94a3b8; margin-top:0.3rem'>"
                f"S&P500 since your earliest entry: {pa.sp500_return_pct:.2f}% annualized"
                f"</div></div>",
                unsafe_allow_html=True,
            )

        if pa.alerts:
            for alert in pa.alerts:
                st.warning(alert)

        # Charts
        ch1, ch2 = st.columns(2)
        with ch1:
            if pa.sector_weights:
                sec_df = pd.DataFrame([
                    {"Sector": s, "Weight (%)": round(w * 100, 1)}
                    for s, w in pa.sector_weights.items()
                ])
                fig = px.pie(sec_df, values="Weight (%)", names="Sector",
                             title="Sector distribution", hole=0.4)
                _dark_layout(fig, height=350)
                fig.update_layout(margin=dict(t=50, b=20),
                                  legend=dict(font=dict(color="#e2e8f0")))
                st.plotly_chart(fig, use_container_width=True)

        with ch2:
            if pa.score_category_weights:
                cat_colors = {
                    "Strong candidate": "#2ecc71",
                    "On radar": "#3498db",
                    "With caution": "#e67e22",
                    "Does not qualify": "#e74c3c",
                    "Not analyzed": "#95a5a6",
                }
                cat_df = pd.DataFrame([
                    {"Category": c, "Weight (%)": round(w * 100, 1)}
                    for c, w in pa.score_category_weights.items()
                ])
                fig = px.bar(cat_df, x="Category", y="Weight (%)",
                             title="Buffett portfolio quality",
                             color="Category", color_discrete_map=cat_colors)
                _dark_layout(fig, height=350)
                fig.update_layout(showlegend=False, margin=dict(t=50, b=20))
                st.plotly_chart(fig, use_container_width=True)

        # Holdings table with P&L
        st.markdown("### Position detail")
        h_rows = []
        for h in pa.holdings:
            pnl_str  = (f"{'+' if (h.unrealized_pnl_pct or 0) >= 0 else ''}"
                        f"{h.unrealized_pnl_pct:.1f}%"
                        if h.unrealized_pnl_pct is not None else "N/A")
            ann_str  = (f"{'+' if (h.annualized_return_pct or 0) >= 0 else ''}"
                        f"{h.annualized_return_pct:.1f}%"
                        if h.annualized_return_pct is not None else "N/A")
            ep_str   = f"${h.entry_price:.2f}" if h.entry_price else "—"
            cur_str  = f"${h.current_price:.2f}" if h.current_price else "N/A"
            h_rows.append({
                "Ticker":        h.symbol,
                "Company":       h.company_name[:22] if h.company_name else "—",
                "Sector":        h.sector or "—",
                "Weight (%)":    f"{h.weight * 100:.1f}%",
                "Score":         h.buffett_score if h.buffett_score is not None else "—",
                "Entry price":   ep_str,
                "Current price": cur_str,
                "Total P&L":     pnl_str,
                "Annualized":    ann_str,
                "Verdict":       h.verdict or "—",
            })
        st.dataframe(pd.DataFrame(h_rows), use_container_width=True, hide_index=True)

        if pa.top_holding and pa.weakest_holding:
            tc, wc = st.columns(2)
            with tc:
                st.success(
                    f"Best position: **{pa.top_holding.symbol}** — {pa.top_holding.buffett_score}/100"
                )
            with wc:
                st.warning(
                    f"Weakest position: **{pa.weakest_holding.symbol}** — {pa.weakest_holding.buffett_score}/100"
                )

    # ---------------------------------------------------------------------------
    # PLANIFICADOR DE CAPITAL — cuanto poner en cada empresa con tu presupuesto
    # ---------------------------------------------------------------------------
    st.markdown("---")
    st.markdown(
        "<div class='section-header'><h3 style='margin:0'>Entry planner</h3></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='color:#64748b; font-size:0.9rem; margin-bottom:1rem'>"
        "Based on the companies with the highest conviction in the batch analysis, the planner "
        "calculates how much capital to allocate to each one according to its conviction index, "
        "with concentration limits to manage risk."
        "</div>",
        unsafe_allow_html=True,
    )

    _plan_results = batch.get_ranked_results(min_score=0)
    if not _plan_results:
        st.info("Run the batch analysis first to use the planner.")
    else:
        # Pre-compute conviction for all results
        for _r in _plan_results:
            if "_conviction" not in _r:
                _r["_conviction"], _r["_conv_label"], _r["_conv_color"] = _conviction_score(_r)

        _pc1, _pc2, _pc3 = st.columns(3)
        with _pc1:
            _capital = st.number_input(
                "Available capital (USD)",
                min_value=100, max_value=10_000_000,
                value=20_000, step=1_000,
                help="How much money you have to invest in this round."
            )
        with _pc2:
            _n_pos = st.slider(
                "Number of positions", min_value=3, max_value=10, value=6,
                help="How many different companies you want to hold. More positions = less concentrated risk."
            )
        with _pc3:
            _min_conv = st.slider(
                "Minimum conviction", min_value=35, max_value=75, value=50, step=5,
                help="Only include companies with conviction >= this value."
            )

        # Filter and select top N candidates by conviction
        _candidates = [
            _r for _r in _plan_results
            if _r.get("_conviction", 0) >= _min_conv
        ][:_n_pos]

        if not _candidates:
            st.warning(f"No companies with conviction >= {_min_conv}. Lower the minimum threshold.")
        else:
            _total_conv = sum(_r["_conviction"] for _r in _candidates) or 1

            # Compute raw weights, cap at 20%, renormalize
            _raw_weights = [_r["_conviction"] / _total_conv for _r in _candidates]
            _capped = [min(w, 0.20) for w in _raw_weights]
            _cap_sum = sum(_capped) or 1
            _final_weights = [w / _cap_sum for w in _capped]

            # Build allocation table
            _alloc_rows = []
            _sector_alloc: dict = {}
            for _r, _w in zip(_candidates, _final_weights):
                _dollars    = round(_capital * _w, 0)
                _price_now  = _r.get("current_price") or 0
                _shares_est = int(_dollars / _price_now) if _price_now > 0 else None
                _sector     = _r.get("sector", "Otro")
                _sector_alloc[_sector] = _sector_alloc.get(_sector, 0) + _w
                _alloc_rows.append({
                    "Ticker":         _r["symbol"],
                    "Company":        _r.get("company_name", "")[:30],
                    "Quality":        f"{_r['total_score']}/100",
                    "Conviction":     f"{_r['_conviction']}/100  {_r['_conv_label']}",
                    "Weight":         f"{_w:.1%}",
                    "Capital USD":    f"${_dollars:,.0f}",
                    "Shares*":        str(_shares_est) if _shares_est else "N/A",
                    "Current price":  f"${_price_now:.2f}" if _price_now else "N/A",
                    "Sector":         _sector,
                })

            st.dataframe(pd.DataFrame(_alloc_rows), use_container_width=True, hide_index=True)
            st.caption("* Estimated shares = Capital / Current price. Verify actual price before trading.")

            # Sector concentration warnings
            _sector_alerts = [
                f"{sec}: {pct:.0%}" for sec, pct in _sector_alloc.items() if pct > 0.35
            ]
            if _sector_alerts:
                st.warning(
                    f"High sector concentration (> 35%): {', '.join(_sector_alerts)}. "
                    "Consider reducing positions in that sector."
                )

            # Summary metrics
            _sm1, _sm2, _sm3, _sm4 = st.columns(4)
            _sm1.metric("Capital to invest", f"${_capital:,.0f}")
            _sm2.metric("Positions", len(_candidates))
            _sm3.metric("Avg conviction", f"{sum(_r['_conviction'] for _r in _candidates)//len(_candidates)}/100")
            _sm4.metric("Distinct sectors", len(_sector_alloc))

    st.caption("Educational analysis based on Yahoo Finance data — not financial advice.")


# ===========================================================================
# MODE 6: Contexto Macro
# ===========================================================================

elif mode == "Macro Context":
    st.markdown(
        "<span style='font-size:2rem; font-weight:800; color:#c9a84c'>Macro Context</span>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='color:#64748b; font-size:0.9rem; margin-bottom:1rem'>"
        "The macro environment directly affects the interpretation of Buffett's criteria. "
        "A P/E of 20x with rates at 5% is expensive; the same P/E with rates at 1% can be reasonable."
        "</div>",
        unsafe_allow_html=True,
    )

    with st.spinner("Fetching macroeconomic indicators..."):
        try:
            macro_env = macro_mod.fetch()
            fetch_ok = True
        except Exception as e:
            fetch_ok = False
            st.error(f"Error fetching macro data: {e}")

    if not fetch_ok:
        st.stop()

    st.caption(f"Datos actualizados: {macro_env.as_of}")

    # Overall summary banner
    st.info(macro_env.overall_summary)

    # Key alerts
    if macro_env.key_alerts:
        for alert in macro_env.key_alerts:
            st.warning(f"Alert: {alert}")

    st.markdown("---")

    # Rate environment badge
    rate_env = macro_env.rate_environment
    rate_colors = {
        "tasas_muy_altas": "#e74c3c",
        "tasas_altas": "#e67e22",
        "tasas_moderadas": "#3498db",
        "tasas_bajas": "#2ecc71",
    }
    rate_labels = {
        "tasas_muy_altas": "VERY HIGH rates — more demanding valuation",
        "tasas_altas": "HIGH rates — higher discount rates in DCF",
        "tasas_moderadas": "MODERATE rates — neutral environment",
        "tasas_bajas": "LOW rates — more generous valuations",
    }
    env_color = rate_colors.get(rate_env, "#95a5a6")
    env_label = rate_labels.get(rate_env, rate_env)
    st.markdown(
        f"<div style='padding:0.8rem 1.2rem; border-radius:10px; background:#141c2e; "
        f"border:1px solid #1e2d45; border-left:5px solid {env_color}'>"
        f"<div style='font-size:0.72rem; text-transform:uppercase; letter-spacing:0.08em; "
        f"color:#64748b; margin-bottom:0.3rem'>Rate environment</div>"
        f"<div style='font-weight:700; color:{env_color}; font-size:1.05rem'>{env_label}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)

    # Indicators grid
    for indicator in macro_env.indicators:
        with st.expander(f"**{indicator.name}** — {indicator.label}"):
            col_val, col_interp = st.columns([1, 2])
            with col_val:
                delta_str = None
                if indicator.change_1y is not None:
                    sign = "+" if indicator.change_1y >= 0 else ""
                    unit = " pp" if indicator.unit == "%" else ""
                    delta_str = f"{sign}{indicator.change_1y:.2f}{unit} vs 1 year ago"
                st.metric(
                    label=indicator.name,
                    value=indicator.label,
                    delta=delta_str,
                )
            with col_interp:
                st.markdown(f"**Current situation:** {indicator.interpretation}")
                st.markdown(f"**Impact on Buffett analysis:** {indicator.impact_on_buffett}")

    st.caption(
        "Sources: Yahoo Finance (^TNX, ^IRX, ^VIX, ^GSPC, DX-Y.NYB, GC=F). "
        "Educational analysis — not financial advice."
    )


# ===========================================================================
# MODE 7: ETFs con Dividendos
# ===========================================================================

elif mode == "Dividend ETFs":
    st.markdown(
        "<span style='font-size:2rem; font-weight:800; color:#c9a84c'>Dividend ETFs</span>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='color:#64748b; font-size:0.9rem; margin-bottom:1rem'>"
        "Evaluate dividend ETFs across <b style='color:#e2e8f0'>5 pillars</b> (100 points): "
        "Yield, Cost (expense ratio), Scale (AUM), Dividend consistency "
        "and Total growth."
        "</div>",
        unsafe_allow_html=True,
    )

    # --- ETF watchlist (persisted) ---
    saved_etf_list = prefs_mod.get("etf_watchlist", etf_mod.POPULAR_ETFS)

    col_etf_input, col_etf_btn = st.columns([3, 1])
    with col_etf_input:
        custom_etf = st.text_input(
            "Add ETF to your list",
            placeholder="e.g. SCHD, VYM, JEPI",
        ).strip().upper()
    with col_etf_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Add", use_container_width=True) and custom_etf:
            if custom_etf not in saved_etf_list:
                saved_etf_list = saved_etf_list + [custom_etf]
                prefs_mod.set_pref("etf_watchlist", saved_etf_list)
                st.success(f"{custom_etf} added.")
                st.rerun()
            else:
                st.info(f"{custom_etf} is already in the list.")

    # Manage list (remove)
    with st.expander(f"Manage list ({len(saved_etf_list)} ETFs)"):
        rm_cols = st.columns(4)
        for i, sym in enumerate(saved_etf_list):
            with rm_cols[i % 4]:
                if st.button(f"Remove {sym}", key=f"etf_rm_{sym}"):
                    new_list = [s for s in saved_etf_list if s != sym]
                    prefs_mod.set_pref("etf_watchlist", new_list)
                    st.rerun()

    st.markdown("---")

    # --- Single ETF deep analysis ---
    st.subheader("Analyze an ETF in detail")
    col_sel, col_analyze = st.columns([3, 1])
    with col_sel:
        etf_to_analyze = st.selectbox(
            "ETF",
            options=[""] + saved_etf_list,
            format_func=lambda x: x if x else "Select or type above...",
        )
    with col_analyze:
        st.markdown("<br>", unsafe_allow_html=True)
        etf_analyze_btn = st.button("Analyze ETF", type="primary", use_container_width=True)

    if etf_to_analyze and etf_analyze_btn:
        with st.spinner(f"Analyzing {etf_to_analyze}..."):
            etf_result = etf_mod.run(etf_to_analyze)

        if etf_result is None:
            st.error(f"Could not retrieve data for {etf_to_analyze}. Verify it is a valid ETF.")
        else:
            er = etf_result

            # Header
            st.markdown(f"### {er.name}")
            st.caption(
                f"{er.symbol}  |  {er.category}  |  Issuer: {er.fund_family}  |  "
                f"Frequency: {er.distribution_frequency}"
            )

            h1, h2, h3, h4 = st.columns(4)
            h1.metric(
                "Score Total",
                f"{er.total_score}/100",
            )
            h2.metric(
                "Dividend Yield",
                f"{er.dividend_yield*100:.2f}%" if er.dividend_yield else "N/A",
            )
            h3.metric(
                "Expense Ratio",
                f"{er.expense_ratio*100:.3f}%" if er.expense_ratio else "N/A",
            )
            h4.metric(
                "AUM",
                (f"${er.total_assets/1e9:.1f}B" if er.total_assets and er.total_assets >= 1e9
                 else (f"${er.total_assets/1e6:.0f}M" if er.total_assets else "N/A")),
            )

            # Verdict banner
            st.markdown(
                f"<div style='background:#141c2e; border:1px solid #1e2d45; "
                f"border-left:5px solid {er.verdict_color}; "
                f"border-radius:10px; padding:0.8rem 1.2rem; margin:0.8rem 0'>"
                f"<span style='font-size:1.1rem; font-weight:700; color:{er.verdict_color}'>"
                f"{er.verdict}</span>"
                f"<span style='color:#64748b; font-size:0.9rem; margin-left:0.8rem'>"
                f"{er.total_score}/100 points</span></div>",
                unsafe_allow_html=True,
            )

            st.markdown("---")

            # Sections as tabs
            def render_etf_section(sec):
                pct = sec.pct
                color = score_color(pct)
                col_name, col_score = st.columns([3, 1])
                with col_name:
                    st.markdown(f"#### {sec.name}")
                with col_score:
                    st.markdown(
                        f"<div style='text-align:right; font-size:1.3rem; "
                        f"font-weight:700; color:{color}'>{sec.score}/{sec.max_score}</div>",
                        unsafe_allow_html=True,
                    )
                st.progress(pct, text=f"{pct*100:.0f}%")
                for c in sec.criteria:
                    icon = "+" if c.passed else "-"
                    with st.expander(f"{icon} {c.name}  —  {c.points_earned}/{c.points_max} pts  |  {c.raw_label}"):
                        st.markdown(f"**Criterion:** {c.threshold}")
                        st.markdown(f"**Justification:** {c.explanation}")

            t1, t2, t3, t4, t5 = st.tabs([
                f"Yield  {er.yield_section.score}/30",
                f"Cost  {er.cost_section.score}/25",
                f"Scale  {er.scale_section.score}/20",
                f"Consistency  {er.consistency_section.score}/15",
                f"Growth  {er.growth_section.score}/10",
            ])
            with t1: render_etf_section(er.yield_section)
            with t2: render_etf_section(er.cost_section)
            with t3: render_etf_section(er.scale_section)
            with t4: render_etf_section(er.consistency_section)
            with t5: render_etf_section(er.growth_section)

    st.markdown("---")

    # --- Batch ranking of ETF list ---
    st.subheader("Ranking of your ETF list")

    etf_cache_path = __import__("os").path.join(
        __import__("os").path.dirname(__file__), "data", "etf_cache.json"
    )
    import os as _os, json as _json

    # Show existing cache if available
    etf_cache: dict = {}
    if _os.path.exists(etf_cache_path):
        try:
            with open(etf_cache_path) as f:
                etf_cache = _json.load(f)
        except Exception:
            etf_cache = {}

    col_ec1, col_ec2 = st.columns([3, 1])
    with col_ec1:
        if etf_cache.get("timestamp"):
            try:
                ts = datetime.fromisoformat(etf_cache["timestamp"])
                st.info(
                    f"Cache: {len(etf_cache.get('results', {}))} ETFs analyzed. "
                    f"Updated: {ts.strftime('%d/%m/%Y %H:%M')}"
                )
            except Exception:
                pass
    with col_ec2:
        run_etf_batch = st.button("Analyze full list", use_container_width=True)

    if run_etf_batch:
        etf_pb = st.progress(0)
        etf_status = st.empty()

        def _etf_progress(cur, tot, sym):
            etf_pb.progress(cur / tot)
            etf_status.text(f"[{cur}/{tot}] Analyzing {sym}...")

        with st.spinner(f"Analyzing {len(saved_etf_list)} ETFs..."):
            batch_results = etf_mod.run_batch(saved_etf_list, progress_callback=_etf_progress)

        etf_pb.progress(1.0)
        etf_status.text("Analysis complete.")

        # Save cache
        serialized = {}
        for sym, res in batch_results.items():
            if res is None:
                serialized[sym] = None
            else:
                serialized[sym] = {
                    "symbol": res.symbol,
                    "name": res.name,
                    "category": res.category,
                    "fund_family": res.fund_family,
                    "total_score": res.total_score,
                    "verdict": res.verdict,
                    "dividend_yield": res.dividend_yield,
                    "expense_ratio": res.expense_ratio,
                    "total_assets": res.total_assets,
                    "dividend_growth_3y": res.dividend_growth_3y,
                    "distribution_frequency": res.distribution_frequency,
                    "years_paying": res.years_paying,
                }
        _os.makedirs(_os.path.dirname(etf_cache_path), exist_ok=True)
        with open(etf_cache_path, "w") as f:
            _json.dump({"timestamp": datetime.now().isoformat(), "results": serialized}, f, indent=2)
        etf_cache = {"timestamp": datetime.now().isoformat(), "results": serialized}
        st.success("ETF analysis complete.")
        st.rerun()

    # Show ranking from cache
    if etf_cache.get("results"):
        cached_etfs = etf_cache["results"]
        rows = []
        for sym, r in cached_etfs.items():
            if r is None:
                rows.append({
                    "Ticker": sym, "Name": "Error / no data", "Score": 0,
                    "Yield": "N/A", "Expense Ratio": "N/A", "AUM": "N/A",
                    "Frequency": "—", "Verdict": "Error",
                })
            else:
                aum = r.get("total_assets")
                rows.append({
                    "Ticker": sym,
                    "Name": r.get("name", "")[:30],
                    "Score": r.get("total_score", 0),
                    "Yield": (f"{r['dividend_yield']*100:.2f}%"
                              if r.get("dividend_yield") else "N/A"),
                    "Expense Ratio": (f"{r['expense_ratio']*100:.3f}%"
                                      if r.get("expense_ratio") else "N/A"),
                    "AUM": (f"${aum/1e9:.1f}B" if aum and aum >= 1e9
                            else (f"${aum/1e6:.0f}M" if aum else "N/A")),
                    "Frequency": r.get("distribution_frequency", "—"),
                    "Verdict": r.get("verdict", "—"),
                })

        df_etf = pd.DataFrame(rows).sort_values("Score", ascending=False)

        # Bar chart
        fig_etf = go.Figure(go.Bar(
            x=df_etf["Ticker"],
            y=df_etf["Score"],
            text=[f"{s}/100" for s in df_etf["Score"]],
            textposition="outside",
            marker_color=[score_color(s / 100) for s in df_etf["Score"]],
        ))
        fig_etf.add_hline(y=80, line_dash="dash", line_color="#10b981",
                          annotation_text="Best in class (80)", annotation_font_color="#10b981")
        fig_etf.add_hline(y=65, line_dash="dash", line_color="#c9a84c",
                          annotation_text="Good option (65)", annotation_font_color="#c9a84c")
        _dark_layout(fig_etf, height=380)
        fig_etf.update_layout(
            title=dict(text="Dividend ETF Score", font=dict(color="#e2e8f0")),
            yaxis=dict(range=[0, 108], title="Score", gridcolor="#1e2d45", linecolor="#2a3d5a"),
            margin=dict(t=50, b=40),
        )
        st.plotly_chart(fig_etf, use_container_width=True)

        # Table
        st.dataframe(
            _score_style(df_etf),
            use_container_width=True, hide_index=True,
        )

        csv_etf = df_etf.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download CSV",
            data=csv_etf,
            file_name=f"etf_ranking_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )
    else:
        st.info("Click 'Analyze full list' to see the ranking of all your ETFs.")

    st.caption(
        "Data: Yahoo Finance. Score based on yield, expense ratio, AUM, consistency and return. "
        "Educational analysis — not financial advice."
    )
