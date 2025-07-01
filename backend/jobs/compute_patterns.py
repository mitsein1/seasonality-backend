#!/usr/bin/env python3
import os
import pandas as pd
import numpy as np
from datetime import timedelta
from joblib import Parallel, delayed
import traceback

from backend.db.session import SessionLocal
from backend.db.models import Asset, Pattern, Statistic, EquitySeries
from backend.services.statistics import get_pattern_statistics
from backend.services.backtest_engine import _drawdown_duration

# ── Config paths ───────────────────────────────────────────────────────────────
ROOT_DIR     = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
HISTORY_ROOT = os.path.join(ROOT_DIR, 'mt5_history')

# ── Parallel params ─────────────────────────────────────────────────────────────
NUM_WORKERS = 14
# ciascun worker prende questo numero di job alla volta
CHUNK_SIZE  = 100

# ── Helpers ────────────────────────────────────────────────────────────────────
def load_symbol_history(group: str, symbol: str, tf_str: str = 'D1') -> pd.DataFrame:
    """
    Parquet-first; restituisce DataFrame con colonne
    ['timestamp','open','high','low','close'].
    """
    parquet_fp = os.path.join(HISTORY_ROOT, group, symbol, f"{symbol}_{tf_str}.parquet")
    if not os.path.isfile(parquet_fp):
        raise FileNotFoundError(f"History file Parquet non trovato: {parquet_fp}")
    df = pd.read_parquet(parquet_fp)

    # se 'time' esiste, rinominala in 'timestamp'
    if 'time' in df.columns and 'timestamp' not in df.columns:
        df = df.rename(columns={'time':'timestamp'})

    # se il timestamp è nell'indice anziché in colonna, lo resettiamo
    if not ('timestamp' in df.columns):
        df = df.reset_index().rename(columns={'index':'timestamp'})

    # assicuriamoci che timestamp sia datetime e ordinato
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp')

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

# ── Core save (per singolo pattern) ────────────────────────────────────────────
def save_pattern(session, asset, pattern_type, params, years_back, stats, equity_series):
    pat = Pattern(
        asset_id   = asset.id,
        type       = pattern_type,
        params     = params,
        years_back = years_back,
        source     = "precomputed"
    )
    session.add(pat)
    session.flush()  # pat.id disponibile

    # ricostruisci equity series e calcola drawdown
    full_idx = pd.DatetimeIndex(sorted(pt["timestamp"] for pt in equity_series))
    eq = pd.Series(
        [pt["value"] for pt in sorted(equity_series, key=lambda x: x["timestamp"])],
        index=full_idx
    )
    dd_realized = _drawdown_duration(eq)
    dd_floating = dd_realized

    # serializza datetime
    from datetime import datetime
    def _iso_dates(d: dict) -> dict:
        return {k: (v.isoformat() if isinstance(v,(pd.Timestamp,datetime)) else v)
                for k,v in d.items()}

    stats["extra_json"] = {
        "dd_realized": _iso_dates(dd_realized),
        "dd_floating": _iso_dates(dd_floating),
    }
    stats.setdefault("recovery_days", 0)

    # filtra per colonne presenti in Statistic
    stat_kwargs = convert_types_for_sqlalchemy(stats)
    from sqlalchemy.inspection import inspect
    cols = {c.key for c in inspect(Statistic).mapper.column_attrs}
    stat_kwargs = {k:v for k,v in stat_kwargs.items() if k in cols}

    session.add(Statistic(pattern_id=pat.id, **stat_kwargs))

    # EquitySeries objects
    for pt in equity_series:
        if pt["value"] is None:
            continue
        session.add(EquitySeries(
            pattern_id   = pat.id,
            timestamp    = safe_value(pt['timestamp']),
            equity_value = safe_value(pt['value'])
        ))

# ── Singolo worker per job (asset×pattern) ─────────────────────────────────────
def process_single_pattern(asset_id, pattern_type, params, years_back):
    session = SessionLocal()
    try:
        asset = session.get(Asset, asset_id)
        if not asset:
            return
        tf = 'H1' if pattern_type=='intraday' else 'D1'
        try:
            df = load_symbol_history(asset.group, asset.symbol, tf)
        except Exception as e:
            print(f"❌ [Load] {asset.symbol} ({pattern_type}) ERRORE: {e}")
            return

        stats, equity = get_pattern_statistics(df, pattern_type, params, years_back)
        if stats and equity:
            save_pattern(session, asset, pattern_type, params, years_back, stats, equity)
            session.commit()
            print(f"✔ {asset.symbol} | {pattern_type} | yb={years_back} | params={params}")
    except Exception:
        print(f"❌ [Calc] {asset_id} - {pattern_type} - ERRORE:\n{traceback.format_exc()}")
    finally:
        session.close()

# ── Entry point parallelo ───────────────────────────────────────────────────────
def compute_patterns_parallel(
    num_workers: int = NUM_WORKERS,
    chunk_size:  int = CHUNK_SIZE
):
    session = SessionLocal()
    try:
        assets = session.query(Asset).all()
    finally:
        session.close()

    # rigenera pattern definitions
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
        for d in range(1,days+1):
            start = pd.Timestamp(2000,m,d)
            for k in range(1,27):
                end = start + timedelta(days=7*k)
                if end.year==2000:
                    annual_defs.append({
                        'start_month':m,'start_day':d,
                        'end_month':end.month,'end_day':end.day
                    })
    years_options = [5,10,15,20]

    # costruisci job list
    jobs = []
    for asset in assets:
        has_int = True
        has_dly = True
        # skip se parquet mancante
        try: load_symbol_history(asset.group, asset.symbol, 'H1')
        except: has_int = False
        try: load_symbol_history(asset.group, asset.symbol, 'D1')
        except: has_dly = False

        for yb in years_options:
            if has_int:
                for p in intraday_defs:
                    jobs.append((asset.id,'intraday',p,yb))
            if has_dly:
                for p in monthly_defs:
                    jobs.append((asset.id,'monthly',p,yb))
                for p in annual_defs:
                    jobs.append((asset.id,'annual',p,yb))

    print(f"\n🚀 Lancio {len(jobs)} job su {num_workers} core (batch_size={chunk_size})\n")

    Parallel(
        n_jobs     = num_workers,
        backend    = "loky",
        verbose    = 5,
        batch_size = chunk_size
    )(
        delayed(process_single_pattern)(*job)
        for job in jobs
    )

    print("\n✅ Tutti i pattern completati con successo.")

if __name__ == '__main__':
    compute_patterns_parallel()
