# Seasonality Backend

Piattaforma per analisi stagionale e screening quantitativo di asset finanziari.  
Scarica dati storici da MetaTrader5, calcola pattern (intraday, monthly, annual), salva statistiche avanzate in database, automatizza il processo con Celery e task schedulati.

---

## 🚀 Caratteristiche principali

- **Download automatico dati storici** (MT5 → CSV) per tutti gli asset e timeframe configurati
- **Calcolo massivo di pattern stagionali** (anche milioni di combinazioni) in parallelo
- **Salvataggio di pattern, statistiche, equity curve** in database SQLite (`data.db`)
- **Automazione completa** tramite Celery (scaricamento notturno, calcolo settimanale)
- **Configurazione semplice** via file YAML (`config/default.yaml`)
- **Debug e test facilitati** (puoi filtrare per singolo asset, es. solo BTCUSD)
- **Compatibilità nativa** con API backend e frontend React

---

## 🗂 Struttura delle cartelle principali

seasonality-backend/
├── backend/
│ ├── data_fetch/
│ │ └── download_all_mt5.py # Download storico da MT5
│ ├── patterns/
│ │ └── calc_patterns.py # Calcolo pattern e statistiche
│ ├── jobs/
│ │ ├── fetch_historical.py # Task Celery per fetch
│ │ └── compute_patterns.py # Task Celery per calcolo
│ ├── db/
│ │ └── models.py # Modelli SQLAlchemy
│ └── celery_worker.py # Configurazione Celery e scheduler
├── mt5_history/ # CSV scaricati per ogni asset/timeframe
├── data.db # Database SQLite
├── config/
│ └── default.yaml # Configurazione gruppi/timeframe MT5
├── manual_compute.py # Lancia calcolo pattern in parallelo
└── README.md

yaml
Copia
Modifica

---

## ⚙️ Setup rapido

### 1. Installa i requisiti Python

```bash
pip install -r requirements.txt
2. Configura MetaTrader5
Installa MetaTrader5 (broker demo va bene)

Tieni il terminale MT5 aperto e connesso

Configura il file config/default.yaml per i gruppi (es. Cryptocurrencies) e timeframe desiderati

3. Scarica i dati storici
bash
Copia
Modifica
python backend/data_fetch/download_all_mt5.py
(Puoi filtrare solo BTCUSD per i test: vedi commenti nel file)

4. Calcola tutti i pattern in parallelo (locale)
bash
Copia
Modifica
python manual_compute.py
5. (Opzionale) Avvia Celery per automazione
bash
Copia
Modifica
celery -A backend.celery_worker worker --loglevel=info --beat