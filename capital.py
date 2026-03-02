from __future__ import annotations
from typing import Optional
import yfinance as yf
import numpy as np
import pandas as pd
import data_sources


def _empty_result(error: str) -> dict:
    return {
        "roic_history": [],
        "roic_avg": None,
        "roic_trend": None,
        "capex_intensity_avg": None,
        "capex_intensity_label": None,
        "capex_intensity_color": "#64748b",
        "buyback_signal": None,
        "wacc_est": None,
        "roic_vs_wacc": None,
        "verdict": None,
        "verdict_color": "#64748b",
        "error": error,
    }


def get_capital_quality(symbol: str) -> dict:
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info or {}
        info = data_sources.enrich_info(symbol, info)

        financials = ticker.financials          # income stmt: columns = periods, rows = items
        balance = ticker.balance_sheet
        cashflow = ticker.cashflow

        if financials is None or financials.empty:
            return _empty_result("No hay datos financieros disponibles")
        if balance is None or balance.empty:
            return _empty_result("No hay datos de balance disponibles")
        if cashflow is None or cashflow.empty:
            return _empty_result("No hay datos de flujo de caja disponibles")

        # --- ROIC por año ---
        roic_history: list = []
        capex_intensities: list = []

        cols = financials.columns  # DatetimeIndex, newest first

        def _row(df, *keys):
            for k in keys:
                if k in df.index:
                    row = df.loc[k]
                    # yfinance can return a DataFrame if the index has duplicate labels
                    if isinstance(row, pd.DataFrame):
                        row = row.iloc[0]
                    return row
            return None

        ebit_row     = _row(financials, "EBIT", "Operating Income")
        tax_row      = _row(financials, "Tax Provision", "Income Tax Expense")
        pretax_row   = _row(financials, "Pretax Income", "Income Before Tax")
        revenue_row  = _row(financials, "Total Revenue", "Revenue")

        equity_row   = _row(balance, "Stockholders Equity", "Total Stockholder Equity",
                             "Common Stock Equity")
        debt_row     = _row(balance, "Total Debt", "Long Term Debt")
        cash_row     = _row(balance, "Cash And Cash Equivalents", "Cash",
                             "Cash Cash Equivalents And Short Term Investments")

        capex_row    = _row(cashflow, "Capital Expenditure", "Capital Expenditures",
                             "Purchase Of Property Plant And Equipment")

        shares_row   = _row(balance, "Ordinary Shares Number", "Common Stock Shares Outstanding")
        if shares_row is None:
            shares_series = None
        else:
            shares_series = shares_row

        def _gv(row, col):
            """Safely get a float from a Series. Returns None on KeyError or NaN."""
            if row is None:
                return None
            try:
                v = row.get(col) if hasattr(row, "get") else row[col]
                if v is None:
                    return None
                f = float(v)
                return None if (f != f) else f  # NaN check (NaN != NaN)
            except Exception:
                return None

        for col in cols:
            try:
                ebit    = _gv(ebit_row,    col)
                tax     = _gv(tax_row,     col)
                pretax  = _gv(pretax_row,  col)
                equity  = _gv(equity_row,  col)
                debt    = _gv(debt_row,    col)
                cash    = _gv(cash_row,    col)
                revenue = _gv(revenue_row, col)
                capex_v = _gv(capex_row,   col)

                if None in (ebit, equity) or equity == 0:
                    continue

                # Tax rate
                if tax is not None and pretax is not None and pretax != 0:
                    tax_rate = max(0.0, min(0.5, abs(tax) / abs(pretax)))
                else:
                    tax_rate = 0.21  # US statutory default

                nopat            = ebit * (1 - tax_rate)
                invested_capital = (equity or 0) + (debt or 0) - (cash or 0)

                if invested_capital <= 0:
                    continue

                roic = nopat / invested_capital
                year = col.year if hasattr(col, "year") else str(col)[:4]
                roic_history.append((int(year), round(roic * 100, 2)))

                if capex_v is not None and revenue is not None and revenue > 0:
                    capex_intensities.append(abs(capex_v) / revenue)

            except Exception:
                continue

        if not roic_history:
            return _empty_result("No se pudo calcular ROIC con los datos disponibles")

        # Sort ascending by year
        roic_history = sorted(roic_history, key=lambda x: x[0])

        roic_values = [r[1] for r in roic_history]
        roic_avg    = round(float(np.mean(roic_values)), 2)

        # Trend via linear regression slope
        if len(roic_values) >= 3:
            xs   = np.arange(len(roic_values), dtype=float)
            slope = float(np.polyfit(xs, roic_values, 1)[0])
            if slope > 0.5:
                roic_trend = "mejorando"
            elif slope < -0.5:
                roic_trend = "deteriorando"
            else:
                roic_trend = "estable"
        else:
            roic_trend = "estable"

        # --- Capex intensity ---
        capex_intensity_avg: Optional[float] = None
        capex_intensity_label: Optional[str] = None
        capex_intensity_color: str = "#64748b"

        if capex_intensities:
            capex_intensity_avg = round(float(np.mean(capex_intensities)) * 100, 2)
            if capex_intensity_avg < 3:
                capex_intensity_label = "Muy baja (asset-light)"
                capex_intensity_color = "#10b981"
            elif capex_intensity_avg < 7:
                capex_intensity_label = "Baja"
                capex_intensity_color = "#3b82f6"
            elif capex_intensity_avg < 15:
                capex_intensity_label = "Moderada"
                capex_intensity_color = "#f59e0b"
            else:
                capex_intensity_label = "Alta (capital-intensivo)"
                capex_intensity_color = "#ef4444"

        # --- Buyback signal via shares outstanding trend ---
        buyback_signal = "neutral"
        if shares_series is not None and len(shares_series.dropna()) >= 2:
            svals = shares_series.dropna().values.astype(float)
            # yfinance returns newest first
            oldest, newest = float(svals[-1]), float(svals[0])
            if oldest > 0:
                change_pct = (newest - oldest) / oldest
                if change_pct < -0.02:
                    buyback_signal = "yes"
                elif change_pct > 0.02:
                    buyback_signal = "no"

        # --- WACC estimate ---
        wacc_est: Optional[float] = None
        roic_vs_wacc: Optional[float] = None
        try:
            rf_ticker = yf.Ticker("^TNX")
            rf_hist   = rf_ticker.history(period="5d")
            risk_free = float(rf_hist["Close"].iloc[-1]) / 100 if not rf_hist.empty else 0.045
            beta      = float(info.get("beta", 1.0) or 1.0)
            beta      = max(0.3, min(3.0, beta))
            wacc_est  = round((risk_free + beta * 0.055) * 100, 2)
            roic_vs_wacc = round(roic_avg - wacc_est, 2)
        except Exception:
            pass

        # --- Verdict ---
        if roic_avg >= 20 and roic_trend == "mejorando":
            verdict       = "Capital excelente — negocio compuesto"
            verdict_color = "#10b981"
        elif roic_avg >= 15:
            verdict       = "Capital de alta calidad"
            verdict_color = "#3b82f6"
        elif roic_avg >= 10:
            verdict       = "Capital aceptable"
            verdict_color = "#f59e0b"
        else:
            verdict       = "Destructor de capital"
            verdict_color = "#ef4444"

        return {
            "roic_history":          roic_history,
            "roic_avg":              roic_avg,
            "roic_trend":            roic_trend,
            "capex_intensity_avg":   capex_intensity_avg,
            "capex_intensity_label": capex_intensity_label,
            "capex_intensity_color": capex_intensity_color,
            "buyback_signal":        buyback_signal,
            "wacc_est":              wacc_est,
            "roic_vs_wacc":          roic_vs_wacc,
            "verdict":               verdict,
            "verdict_color":         verdict_color,
            "error":                 None,
        }

    except Exception as exc:
        return _empty_result(str(exc))
