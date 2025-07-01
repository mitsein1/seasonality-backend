# backend/services/statistics.py
from __future__ import annotations

"""
Estrazione pattern e calcolo metriche unificate (trade-stats, ratio annualizzati,
draw-down realized / floating) tramite `full_metrics`.
"""

import numpy as np
import pandas as pd
from datetime import timedelta          # usato da chi importa questo modulo

from .metrics_core import full_metrics  # unico entry-point “all-in-one”

# --------------------------------------------------------------------------- #
# Mapping timeframe MT5 → freq pandas                                         #
# --------------------------------------------------------------------------- #
TF_FREQ = {
    "M1": "1T", "H1": "1h", "H4": "4h",
    "D1": "1D", "W1": "1W", "MN1": "1M",
}

# --------------------------------------------------------------------------- #
# Helper per date valide (non-trading)                                        #
# --------------------------------------------------------------------------- #
def _next_valid_date(dt: pd.Timestamp, idx: pd.DatetimeIndex) -> pd.Timestamp | None:
    pos = idx.get_indexer([dt], method="bfill")[0]
    return None if pos == -1 else idx[pos]

def _prev_valid_date(dt: pd.Timestamp, idx: pd.DatetimeIndex) -> pd.Timestamp | None:
    pos = idx.get_indexer([dt], method="ffill")[0]
    return None if pos == -1 else idx[pos]

# --------------------------------------------------------------------------- #
# Funzione core                                                               #
# --------------------------------------------------------------------------- #
def get_pattern_statistics(
    df: pd.DataFrame,
    pattern_type: str,
    params: dict,
    years_back: int,
):
    """
    Calcola equity-curve e statistiche per pattern **intraday / monthly / annual**.

    Ritorna:
        stats  – dict JSON-ready (percentuali già in %)
        equity – list[{"timestamp": ts, "value": equity}] (equity a fine-trade)
    """
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

    # ----- limita lo storico ---------------------------------------------- #
    end   = df["timestamp"].max()
    start = end - pd.DateOffset(years=years_back)
    data  = df[(df["timestamp"] >= start) & (df["timestamp"] <= end)].copy()
    data.set_index("timestamp", inplace=True)

    valid_idx: pd.DatetimeIndex        = data.index
    returns: list[float]               = []
    timestamps: list[pd.Timestamp]     = []

    # ---------------- estrazione trade per pattern ------------------------ #
    if pattern_type == "intraday":
        tf   = params.get("tf")
        freq = TF_FREQ.get(tf)
        if freq is None:
            raise ValueError(f"Timeframe non riconosciuto: {tf!r}")

        sh = params.get("start_hour")
        eh = params.get("end_hour")
        # consentiamo eh == 24 → 23:59:59
        if (
            sh is None or eh is None
            or not (0 <= sh <= 23)
            or not (1 <= eh <= 24)
            or eh < sh
        ):
            return {}, []

        start_str = f"{sh:02d}:00"
        end_str   = "23:59:59" if eh == 24 else f"{eh:02d}:00"

        series = data["close"].resample(freq).last().ffill()
        for _, grp in series.groupby(series.index.date):
            seg = grp.between_time(start_str, end_str)
            if len(seg) >= 2:
                returns.append((seg.iloc[-1] - seg.iloc[0]) / seg.iloc[0])
                timestamps.append(seg.index[-1])

    elif pattern_type == "monthly":
        sd = params["start_day"]
        wd = params["window_days"]
        if not (1 <= sd <= 31 and wd >= 1):
            return {}, []

        daily = data["close"].resample("1D").last().ffill()
        for yr in sorted(daily.index.year.unique()):
            for mo in range(1, 13):
                last_day = pd.Period(f"{yr}-{mo:02d}", "M").days_in_month
                win_end  = sd + wd - 1
                if sd > last_day or win_end > last_day:
                    continue
                rs, re = pd.Timestamp(yr, mo, sd), pd.Timestamp(yr, mo, win_end)
                sdt = _next_valid_date(rs, valid_idx)
                edt = _prev_valid_date(re, valid_idx)
                if sdt and edt and sdt < edt:
                    r = (data["close"].loc[edt] - data["close"].loc[sdt]) / data["close"].loc[sdt]
                    returns.append(r)
                    timestamps.append(edt)

    elif pattern_type == "annual":
        sm, sd, em, ed = (
            params["start_month"], params["start_day"],
            params["end_month"],   params["end_day"],
        )
        daily = data["close"].resample("1D").last().ffill()
        for yr in sorted(daily.index.year.unique()):
            try:
                rs, re = pd.Timestamp(yr, sm, sd), pd.Timestamp(yr, em, ed)
            except ValueError:
                continue
            sdt = _next_valid_date(rs, valid_idx)
            edt = _prev_valid_date(re, valid_idx)
            if sdt and edt and sdt < edt:
                r = (data["close"].loc[edt] - data["close"].loc[sdt]) / data["close"].loc[sdt]
                returns.append(r)
                timestamps.append(edt)
    else:
        raise ValueError(f"Unknown pattern_type {pattern_type!r}")

    # ---------------- equity curve ---------------------------------------- #
    equity = [1.0]
    for r in returns:
        equity.append(equity[-1] * (1 + r))

    equity_series = [
        {"timestamp": ts, "value": eq}
        for ts, eq in zip(timestamps, equity[1:])
    ]

    # ---------------- metriche unificate ---------------------------------- #
    if not returns:
        return {}, equity_series

    stats = full_metrics(
        trade_returns = np.asarray(returns, dtype=float),
        equity_series = equity_series,
        years_back    = max(1, years_back),
    )

    return stats, equity_series
