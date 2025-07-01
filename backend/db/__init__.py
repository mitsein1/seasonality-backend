# backend/db/models/__init__.py

from backend.db.session import Base

# Importa TUTTI i modelli, con esattamente gli stessi nomi definiti in models.py
from backend.db.models import (
    Asset,
    Pattern,
    Statistic,
    EquitySeries,
    BacktestParams,
    BacktestResult,
    Trade,
    EquityPoint,
    EquityFloatingPoint,
    SavedBacktest,
    Portfolio,        # <-- deve comparire QUI
    PortfolioItem,
    User,
    SimulatedTrade     # <-- e QUI il tuo nuovo modello
)
