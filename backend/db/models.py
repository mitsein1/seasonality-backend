#!/usr/bin/env python3
# TODO: definisci i modelli SQLAlchemy
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, JSON
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class Asset(Base):
    __tablename__ = "assets"
    id = Column(Integer, primary_key=True)
    symbol = Column(String, unique=True, nullable=False, index=True)
    group = Column(String, nullable=False)  # es. "Crypto", "Forex", etc.

    patterns = relationship("Pattern", back_populates="asset")

class Pattern(Base):
    __tablename__ = "patterns"
    id = Column(Integer, primary_key=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    type = Column(String, nullable=False)        # "annual", "monthly", "intraday"
    params = Column(JSON, nullable=False)        # es. {"month":5,"day":1} o {"tf":"H1","start":9,"end":17}
    years_back = Column(Integer, nullable=False) # lookback in anni (o periodi intraday)

    asset = relationship("Asset", back_populates="patterns")
    stats = relationship("Statistic", back_populates="pattern", uselist=False)
    equity_series = relationship("EquityPoint", back_populates="pattern", cascade="all, delete-orphan")

class Statistic(Base):
    __tablename__ = "statistics"
    pattern_id = Column(Integer, ForeignKey("patterns.id"), primary_key=True)

    gross_profit_pct       = Column(Float, nullable=False)
    gross_loss_pct         = Column(Float, nullable=False)
    net_return_pct         = Column(Float, nullable=False)
    win_rate               = Column(Float, nullable=False)
    profit_factor          = Column(Float, nullable=False)
    expectancy             = Column(Float, nullable=False)

    max_drawdown_pct       = Column(Float, nullable=False)
    drawdown_start         = Column(DateTime, nullable=False)
    drawdown_end           = Column(DateTime, nullable=False)
    recovery_days          = Column(Integer, nullable=False)

    sharpe_ratio           = Column(Float, nullable=False)
    sortino_ratio          = Column(Float, nullable=False)
    annual_volatility_pct  = Column(Float, nullable=False)

    num_trades             = Column(Integer, nullable=False)
    avg_trade_pct          = Column(Float, nullable=False)
    max_consec_wins        = Column(Integer, nullable=False)
    max_consec_losses      = Column(Integer, nullable=False)

    pattern = relationship("Pattern", back_populates="stats")

class EquityPoint(Base):
    __tablename__ = "equity_series"
    id            = Column(Integer, primary_key=True)
    pattern_id    = Column(Integer, ForeignKey("patterns.id"), nullable=False)
    timestamp     = Column(DateTime, nullable=False, index=True)
    equity_value  = Column(Float, nullable=False)

    pattern = relationship("Pattern", back_populates="equity_series")
