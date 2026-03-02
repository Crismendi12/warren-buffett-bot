from __future__ import annotations
from datetime import datetime, timedelta, timezone
import yfinance as yf
import pandas as pd


def _empty_result(error: str) -> dict:
    return {
        "net_6m_usd":           None,
        "buy_count":            0,
        "sell_count":           0,
        "signal":               "NEUTRAL",
        "signal_color":         "#64748b",
        "signal_label":         "Sin datos",
        "recent_transactions":  [],
        "error":                error,
    }


def get_insider_signal(symbol: str) -> dict:
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.insider_transactions

        if df is None or df.empty:
            return _empty_result("No hay transacciones de insiders disponibles")

        df = df.copy()

        # Normalize date column
        date_col = None
        for c in df.columns:
            if "date" in c.lower() or "start" in c.lower():
                date_col = c
                break
        if date_col is None:
            return _empty_result("Columna de fecha no encontrada")

        df[date_col] = pd.to_datetime(df[date_col], utc=True, errors="coerce")
        df = df.dropna(subset=[date_col])

        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=182)
        df = df[df[date_col] >= cutoff]

        if df.empty:
            return _empty_result("Sin transacciones en los ultimos 6 meses")

        # Normalize transaction type / value columns
        tx_col  = next((c for c in df.columns if "transaction" in c.lower()), None)
        val_col = next((c for c in df.columns if "value" in c.lower()), None)
        name_col = next((c for c in df.columns if "insider" in c.lower()
                         or "name" in c.lower()), None)

        # Exclude automatic option exercises
        auto_keywords = ["automatic", "auto", "exercise", "option exercise"]
        if tx_col:
            mask = ~df[tx_col].astype(str).str.lower().str.contains(
                "|".join(auto_keywords), na=False
            )
            df = df[mask]

        if df.empty:
            return _empty_result("Solo hay ejercicios automaticos de opciones")

        # Classify buys / sells
        buy_keywords  = ["purchase", "buy", "acquisition", "grant"]
        sell_keywords = ["sale", "sell", "disposition"]

        def _is_buy(tx: str) -> bool:
            tx = tx.lower()
            return any(k in tx for k in buy_keywords)

        def _is_sell(tx: str) -> bool:
            tx = tx.lower()
            return any(k in tx for k in sell_keywords)

        if tx_col:
            buy_mask  = df[tx_col].astype(str).apply(_is_buy)
            sell_mask = df[tx_col].astype(str).apply(_is_sell)
        else:
            buy_mask  = pd.Series([False] * len(df), index=df.index)
            sell_mask = pd.Series([False] * len(df), index=df.index)

        buy_df  = df[buy_mask]
        sell_df = df[sell_mask]

        def _sum_value(sub_df) -> float:
            if val_col and val_col in sub_df.columns:
                return float(sub_df[val_col].abs().sum())
            return 0.0

        buy_usd  = _sum_value(buy_df)
        sell_usd = _sum_value(sell_df)
        net_usd  = buy_usd - sell_usd

        # Signal
        THRESHOLD = 500_000
        if net_usd > THRESHOLD:
            signal       = "BULLISH"
            signal_color = "#10b981"
            signal_label = "Insiders comprando"
        elif net_usd < -THRESHOLD:
            signal       = "BEARISH"
            signal_color = "#ef4444"
            signal_label = "Insiders vendiendo"
        else:
            signal       = "NEUTRAL"
            signal_color = "#f59e0b"
            signal_label = "Actividad neutral"

        # Recent transactions list (up to 5)
        df_sorted = df.sort_values(date_col, ascending=False).head(5)
        recent: list = []
        for _, row in df_sorted.iterrows():
            tx_type = str(row[tx_col]) if tx_col else "—"
            value   = float(row[val_col]) if val_col and pd.notna(row[val_col]) else None
            name    = str(row[name_col]) if name_col and pd.notna(row[name_col]) else "—"
            date_str = row[date_col].strftime("%Y-%m-%d") if pd.notna(row[date_col]) else "—"
            recent.append({
                "date":        date_str,
                "insider":     name,
                "transaction": tx_type,
                "value_usd":   value,
            })

        return {
            "net_6m_usd":          round(net_usd),
            "buy_count":           int(len(buy_df)),
            "sell_count":          int(len(sell_df)),
            "signal":              signal,
            "signal_color":        signal_color,
            "signal_label":        signal_label,
            "recent_transactions": recent,
            "error":               None,
        }

    except Exception as exc:
        return _empty_result(str(exc))
