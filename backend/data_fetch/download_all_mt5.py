#!/usr/bin/env python3
import os
from pathlib import Path
from datetime import datetime
from dateutil.relativedelta import relativedelta
import pandas as pd
import yaml
import MetaTrader5 as mt5

# --- 1) TROVA E CARICA LA CONFIG in <PROJECT_ROOT>/config/default.yaml ---
HERE      = Path(__file__).resolve().parent            # …/backend/data_fetch
PROJECT   = HERE.parents[1]                            # risale fino a seasonality-backend
CONFIG_FP = PROJECT / "config" / "default.yaml"

if not CONFIG_FP.exists():
    raise FileNotFoundError(f"Non trovo default.yaml in {CONFIG_FP!s}")

with open(CONFIG_FP, 'r') as f:
    cfg = yaml.safe_load(f)

# --- 2) CONFIGURAZIONE TIMEFRAME E DATE ---------------------------
TIMEFRAME_MAP = {
    'H1':  mt5.TIMEFRAME_H1,
    'H4':  mt5.TIMEFRAME_H4,
    'D1':  mt5.TIMEFRAME_D1,
    'W1':  mt5.TIMEFRAME_W1,
    'MN1': mt5.TIMEFRAME_MN1,
}
TIMEFRAMES   = cfg['mt5']['timeframes']

DATE_TO      = datetime.now()
DATE_FROM    = DATE_TO - relativedelta(years=20)

# --- 3) GRUPPI MT5 DA PROCESSARE (primo segmento di sym.path) ------
MT5_GROUPS   = cfg['mt5']['groups']   # es. ['Cryptocurrencies']

# --- 4) CARTELLA DI OUTPUT ----------------------------------------
OUTPUT_ROOT  = PROJECT / cfg['mt5'].get('history_path', 'mt5_history')
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

# --- 5) INIT / SHUTDOWN MT5 ---------------------------------------
def init_mt5():
    if not mt5.initialize():
        raise RuntimeError(f"Errore init MT5: {mt5.last_error()}")
    print("✅ MT5 initialized")

def shutdown_mt5():
    mt5.shutdown()
    print("✅ MT5 shutdown")

# --- 6) DISCOVERY SIMBOLI PER GRUPPO -----------------------------
def discover_symbols_by_group():
    """
    Restituisce un dict { gruppo: [symbol1, symbol2, ...], ... }
    filtrando mt5.symbols_get() per root = sym.path.split('\\')[0].
    """
    all_syms = mt5.symbols_get()
    assets   = {g: [] for g in MT5_GROUPS}

    for sym in all_syms:
        root = sym.path.split('\\')[0]
        if root in MT5_GROUPS:
            assets[root].append(sym.name)

    for group, syms in assets.items():
        if not syms:
            print(f"⚠️ Nessun simbolo trovato per gruppo '{group}'")
            continue
        for symbol in syms:
            (OUTPUT_ROOT / group / symbol).mkdir(parents=True, exist_ok=True)
        print(f"→ Gruppo '{group}': trovati {len(syms)} simboli")
    return assets

# --- 7) FUNZIONE DI DOWNLOAD & SALVATAGGIO ------------------------
def fetch_and_save(symbol: str, tf_str: str, tf_const: int, out_dir: Path):
    try:
        # paths sia CSV (retrocompatibilità) che Parquet
        csv_path = out_dir / f"{symbol}_{tf_str}.csv"
        pq_path  = csv_path.with_suffix('.parquet')

        # Seleziona il simbolo
        if not mt5.symbol_select(symbol, True):
            print(f"   ⚠️ symbol_select fallita per {symbol}, skip")
            return

        # Download range completo
        print(f"   → Download {symbol} {tf_str} ({DATE_FROM.date()} → {DATE_TO.date()})")
        rates = mt5.copy_rates_range(symbol, tf_const, DATE_FROM, DATE_TO)

        # controlla se dati presenti
        if rates is None or len(rates) == 0:
            print(f"      ⚠️ Nessun dato per {symbol} {tf_str}")
            return

        df = pd.DataFrame(rates)
        df.rename(columns={"time": "timestamp"}, inplace=True)
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")

        # salva Parquet
        df.to_parquet(pq_path, index=False)
        print(f"      ✅ Salvato {pq_path}")

        # (opzionale) salva ancora CSV per retrocompatibilità
        # df.to_csv(csv_path, index=False)

    except Exception as e:
        print(f"   ⚠️ Errore in fetch_and_save per {symbol} {tf_str}: {e}")

def update_csv(symbol: str, tf_str: str, tf_const: int, out_dir: Path):
    """
    Aggiorna il Parquet di `symbol`+`tf_str` in out_dir,
    scaricando solo le barre successive a quelle già presenti.
    """
    pq_path = out_dir / f"{symbol}_{tf_str}.parquet"
    # 1) se non esiste, full download in parquet
    if not pq_path.exists():
        print(f"   → {symbol} {tf_str} non trovato, full download → Parquet")
        rates = mt5.copy_rates_range(symbol, tf_const, DATE_FROM, DATE_TO)
        if rates is None or len(rates) == 0:
            print(f"      ⚠️ Nessun dato per {symbol} {tf_str}")
            return
        df = pd.DataFrame(rates)
        df.rename(columns={"time":"timestamp"}, inplace=True)
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
        df.to_parquet(pq_path, index=False)
        print(f"      ✅ Salvato {pq_path}")
        return

    # 2) altrimenti, append delle nuove barre
    df_exist = pd.read_parquet(pq_path)
    last_ts  = df_exist['timestamp'].max()
    start_dt = last_ts + pd.Timedelta(seconds=1)
    if start_dt >= DATE_TO:
        print(f"   → {symbol} {tf_str} già aggiornato fino a {last_ts}")
        return

    print(f"   → Update {symbol} {tf_str} ({start_dt.date()} → {DATE_TO.date()})")
    rates = mt5.copy_rates_range(symbol, tf_const, start_dt, DATE_TO)
    # qui il controllo corretto
    if rates is None or len(rates) == 0:
        print(f"      ⚠️ Nessuna barra nuova per {symbol} {tf_str}")
        return

    df_new = pd.DataFrame(rates)
    df_new.rename(columns={"time":"timestamp"}, inplace=True)
    df_new["timestamp"] = pd.to_datetime(df_new["timestamp"], unit="s")
    df_combined = pd.concat([df_exist, df_new], ignore_index=True)
    df_combined.to_parquet(pq_path, index=False)
    print(f"      ✅ Aggiornato {pq_path} (+{len(df_new)} barre)")


# --- 8) MAIN -----------------------------------------------------
def main():
    init_mt5()
    try:
        assets = discover_symbols_by_group()
        if not any(assets.values()):
            print("❌ Nessun asset da scaricare – controlla la config dei gruppi MT5")
            return

        for group, symbols in assets.items():
            print(f"\n📁 Aggiorno gruppo '{group}' ({len(symbols)} simboli)")
            for symbol in symbols:
                out_dir = OUTPUT_ROOT / group / symbol
                for tf_str in TIMEFRAMES:
                    tf_const = TIMEFRAME_MAP.get(tf_str)
                    if not tf_const:
                        print(f"   ⚠️ Timeframe non supportato: {tf_str}")
                        continue
                    update_csv(symbol, tf_str, tf_const, out_dir)
    finally:
        shutdown_mt5()
        print("\n🏁 Update terminato.")

if __name__ == "__main__":
    main()
