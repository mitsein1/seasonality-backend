#!/usr/bin/env python3
from backend.data_fetch.download_all_mt5 import (
    init_mt5,
    shutdown_mt5,
    discover_symbols_by_group,
    TIMEFRAMES,
    TIMEFRAME_MAP,
    OUTPUT_ROOT,
    fetch_and_save,
    update_csv,
)

def fetch_and_save_task():
    """
    Job on-demand / Celery: aggiorna incrementale dei file Parquet
    per ciascun gruppo e li salva in OUTPUT_ROOT.
    """
    # 1) inizializza MT5
    init_mt5()
    try:
        # 2) scopri simboli
        symbols_by_group = discover_symbols_by_group()
        if not any(symbols_by_group.values()):
            print("❌ Nessun asset trovato – controlla config/groups")
            return

        # 3) cicla gruppi, simboli e timeframe
        for group, symbols in symbols_by_group.items():
            if not symbols:
                continue
            print(f"\n📁 Gruppo '{group}' – {len(symbols)} simboli")
            for symbol in symbols:
                out_dir = OUTPUT_ROOT / group / symbol
                for tf_str in TIMEFRAMES:
                    tf_const = TIMEFRAME_MAP.get(tf_str)
                    if not tf_const:
                        print(f"   ⚠️ Timeframe non supportato: {tf_str}")
                        continue
                    # 4) usa update_csv (scrive Parquet) invece di fetch_and_save
                    update_csv(symbol, tf_str, tf_const, out_dir)
    finally:
        # 5) chiude MT5
        shutdown_mt5()

# Permette esecuzione diretta:
# python -c "from backend.jobs.fetch_historical import fetch_and_save_task; fetch_and_save_task()"
