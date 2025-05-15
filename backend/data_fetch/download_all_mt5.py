#!/usr/bin/env python3
# TODO: incolla qui il tuo download_all_mt5.py
import os
import yaml
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import MetaTrader5 as mt5

# Carica configurazione da config/default.yaml
CONFIG_PATH = Path(__file__).parents[1] / "config" / "default.yaml"
with open(CONFIG_PATH, 'r') as f:
    config = yaml.safe_load(f)

MT5_GROUPS    = config["mt5"]["groups"]
TIMEFRAMES    = config["mt5"]["timeframes"]
HISTORY_PATH  = Path(config["mt5"].get("history_path", "mt5_history"))

# Mappatura stringa → costante MT5
TF_MAP = {
    "M1":  mt5.TIMEFRAME_M1,
    "H1":  mt5.TIMEFRAME_H1,
    "H4":  mt5.TIMEFRAME_H4,
    "D1":  mt5.TIMEFRAME_D1,
    "W1":  mt5.TIMEFRAME_W1,
    "MN1": mt5.TIMEFRAME_MN1,
}

def initialize_mt5():
    if not mt5.initialize():
        print(f"Errore inizializzazione MT5: {mt5.last_error()}")
        return False
    print("MT5 inizializzato correttamente")
    return True

def shutdown_mt5():
    mt5.shutdown()
    print("MT5 chiuso")

def fetch_and_save():
    if not initialize_mt5():
        return

    to_date   = datetime.now()
    from_date = to_date - timedelta(days=365 * 20)

    for group, symbols in MT5_GROUPS.items():
        for symbol in symbols:
            out_dir = HISTORY_PATH / group / symbol
            out_dir.mkdir(parents=True, exist_ok=True)

            for tf in TIMEFRAMES:
                mt5_tf = TF_MAP.get(tf)
                if mt5_tf is None:
                    print(f"[WARN] Timeframe non supportato: {tf}")
                    continue

                csv_file = out_dir / f"{symbol}_{tf}.csv"
                if csv_file.exists():
                    print(f"[SKIP] {csv_file} già esistente")
                    continue

                rates = mt5.copy_rates_range(symbol, mt5_tf, from_date, to_date)
                if rates is None or len(rates) == 0:
                    print(f"[WARN] Nessun dato per {symbol} {tf}")
                    continue

                df = pd.DataFrame(rates)
                df.rename(columns={"time": "timestamp"}, inplace=True)
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
                df.to_csv(csv_file, index=False)
                print(f"[SAVED] {csv_file}")

    shutdown_mt5()

if __name__ == "__main__":
    fetch_and_save()
