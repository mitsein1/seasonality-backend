#!/usr/bin/env python3
import os
import pandas as pd
import numpy as np
import traceback

from datetime import timedelta
from joblib import Parallel, delayed

from backend.db.session import SessionLocal
from backend.db.models import Asset, Pattern, Statistic, EquitySeries
from backend.services.statistics import get_pattern_statistics
from backend.services.backtest_engine import _drawdown_duration

# ── Config paths ───────────────────────────────────────────────────────────────
ROOT_DIR     = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
HISTORY_ROOT = os.path.join(ROOT_DIR, 'mt5_history')

# ── Definitions ────────────────────────────────────────────────────────────────
intraday_defs = [
    {'tf':'H1','start_hour':h,'end_hour':h+d}
    for d in range(1,7) for h in range(0,24-d+1)
]
monthly_defs = [
    {'start_day':d,'window_days':w}
    for d in range(1,29) for w in (3,7,15) if d+w-1<=31
]
annual_defs = []
for m in range(1,13):
    days = pd.Period(f"2000-{m:02d}", freq='M').days_in_month
    for d in range(1, days+1):
        start = pd.Timestamp(2000,m,d)
        for k in range(1,27):
            end = start + timedelta(days=7*k)
            if end.year==2000:
                annual_defs.append({
                    'start_month':m,'start_day':d,
                    'end_month':end.month,'end_day':end.day
                })
years_options = [5,10,15,20]

# ── Helpers ────────────────────────────────────────────────────────────────────
def load_symbol_history(group: str, symbol: str, tf_str: str = 'D1') -> pd.DataFrame:
    """
    Parquet-first / CSV-fallback; restituisce DataFrame con colonne
    ['timestamp','open','high','low','close'].
    """
    symbol_dir = os.path.join(HISTORY_ROOT, group, symbol)
    fname_base = f"{symbol}_{tf_str}"
    pq_path = os.path.join(symbol_dir, f"{fname_base}.parquet")

    if os.path.isfile(pq_path):
        df = pd.read_parquet(pq_path)
        if 'timestamp' not in df.columns and df.index.dtype.kind == 'M':
            df = df.reset_index().rename(columns={'index':'timestamp'})
    else:
        csv_path = os.path.join(symbol_dir, f"{fname_base}.csv")
        if not os.path.isfile(csv_path):
            raise FileNotFoundError(f"History file non trovato: {csv_path}")
        sample = pd.read_csv(csv_path, nrows=0)
        date_col = 'timestamp' if 'timestamp' in sample.columns else 'time'
        df = pd.read_csv(csv_path, parse_dates=[date_col])
        if date_col == 'time':
            df = df.rename(columns={'time':'timestamp'})

    # ora ho certamente la colonna 'timestamp'
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp')

    # restituisco solo le colonne che servono
    return df[['timestamp','open','high','low','close']]


def safe_value(val):
    if isinstance(val, (np.generic,)):
        return val.item()
    if isinstance(val, pd.Timestamp):
        return val.to_pydatetime()
    if pd.isna(val):
        return None
    return val

def convert_types_for_sqlalchemy(d: dict) -> dict:
    return {k: safe_value(v) for k,v in d.items()}

# ── Core “make, but don’t commit” ───────────────────────────────────────────────
def save_pattern(session, asset, pattern_type, params, years_back, stats, equity_series):
    pat = Pattern(
        asset_id   = asset.id,
        type       = pattern_type,
        params     = params,
        years_back = years_back,
        source     = "precomputed"
    )
    session.add(pat)
    session.flush()

    # drawdowns
    full_idx = pd.DatetimeIndex(sorted(pt["timestamp"] for pt in equity_series))
    eq = pd.Series(
        [pt["value"] for pt in sorted(equity_series, key=lambda x: x["timestamp"])],
        index=full_idx
    )
    dd_realized = _drawdown_duration(eq)
    dd_floating = dd_realized
    from datetime import datetime
    def _iso_dates(d: dict) -> dict:
        return {k:(v.isoformat() if isinstance(v,(pd.Timestamp,datetime)) else v)
                for k,v in d.items()}
    stats["extra_json"] = {
        "dd_realized":_iso_dates(dd_realized),
        "dd_floating":_iso_dates(dd_floating),
    }
    stats.setdefault("recovery_days",0)

    stat_kwargs = convert_types_for_sqlalchemy(stats)
    from sqlalchemy.inspection import inspect
    cols = {c.key for c in inspect(Statistic).mapper.column_attrs}
    stat_kwargs = {k:v for k,v in stat_kwargs.items() if k in cols}
    session.add(Statistic(pattern_id=pat.id, **stat_kwargs))

    # EquitySeries objects (ritornati per bulk save)
    eq_objs = []
    for pt in equity_series:
        if pt["value"] is None:
            continue
        eq_objs.append(EquitySeries(
            pattern_id   = pat.id,
            timestamp    = safe_value(pt['timestamp']),
            equity_value = safe_value(pt['value'])
        ))
    return pat, eq_objs

# ── Process singolo asset in batch ─────────────────────────────────────────────
def process_asset(asset_id: int):
    print(f"→ START Asset {asset_id}")  # 🔥 log inizio batch
    session = SessionLocal()
    try:
        asset = session.get(Asset, asset_id)
        try: df_int = load_symbol_history(asset.group, asset.symbol, 'H1')
        except: df_int = None
        try: df_dly = load_symbol_history(asset.group, asset.symbol, 'D1')
        except: df_dly = None

        for yb in years_options:
            patterns, equities = [], []

            if df_int is not None:
                for p in intraday_defs:
                    stats, eqv = get_pattern_statistics(df_int, 'intraday', p, yb)
                    if not stats:
                        print(f"⚠️ No stats for {asset.symbol}|intraday|yb={yb}|{p}")
                    else:
                        pat, eos = save_pattern(session, asset, 'intraday', p, yb, stats, eqv)
                        patterns.append(pat); equities.extend(eos)

            if df_dly is not None:
                for p in monthly_defs:
                    stats, eqv = get_pattern_statistics(df_dly, 'monthly', p, yb)
                    if not stats:
                        print(f"⚠️ No stats for {asset.symbol}|monthly|yb={yb}|{p}")
                    else:
                        pat, eos = save_pattern(session, asset, 'monthly', p, yb, stats, eqv)
                        patterns.append(pat); equities.extend(eos)
                for p in annual_defs:
                    stats, eqv = get_pattern_statistics(df_dly, 'annual', p, yb)
                    if not stats:
                        print(f"⚠️ No stats for {asset.symbol}|annual|yb={yb}|{p}")
                    else:
                        pat, eos = save_pattern(session, asset, 'annual', p, yb, stats, eqv)
                        patterns.append(pat); equities.extend(eos)

            if patterns:
                session.bulk_save_objects(patterns)
                session.bulk_save_objects(equities)
                session.commit()
                print(f"✔ Commit Asset {asset_id} yb={yb} ({len(patterns)} patterns)")
                patterns.clear(); equities.clear()

    except Exception:
        print(f"❌ [Asset {asset_id}] ERRORE:\n{traceback.format_exc()}")
    finally:
        session.close()

# ── Parallel compute with chunking ─────────────────────────────────────────────
def compute_patterns_parallel(num_workers: int = 14):
    session = SessionLocal()
    try:
        #asset_ids = [a.id for a in session.query(Asset.id).all()] <--- RIPRISTINARE PER IL CALCOLO DI TUTTI GLI ASSETS
        asset_ids = [
            a.id
            for a in session.query(Asset.id)
                             .filter(Asset.group.in_(["Cryptocurrencies", "Forex"]))
                             .all()
        ]
    finally:
        session.close()

    total = len(asset_ids)
    chunk = (total + num_workers - 1)//num_workers
    print(f"🚀 Calcolo {total} asset su {num_workers} core (chunk={chunk})")

    Parallel(
        n_jobs     = num_workers,
        batch_size = chunk,
        verbose    = 10            # 🔥 mostra progresso
    )(
        delayed(process_asset)(aid)
        for aid in asset_ids
    )
    print("✅ Tutti i pattern completati")

if __name__ == '__main__':
    compute_patterns_parallel()
