from datetime import datetime
import enum

from sqlalchemy import (
    Column, Integer, String, Float, DateTime, JSON, ForeignKey,
    Text, Numeric, func
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import Enum as SAEnum
from flask_login import UserMixin

from backend.db.session import Base

# ────────────────────────────────────────────────────────────────────────────────
class SubscriptionType(enum.Enum):
    FREE = "free"
    PRO  = "pro"
# ────────────────────────────────────────────────────────────────────────────────

class Asset(Base):
    __tablename__ = 'assets'
    id      = Column(Integer, primary_key=True)
    symbol  = Column(String, unique=True, nullable=False)
    group   = Column(String, nullable=False)

    patterns = relationship('Pattern', back_populates='asset')

class Pattern(Base):
    __tablename__ = 'patterns'
    id           = Column(Integer, primary_key=True)
    asset_id     = Column(Integer, ForeignKey('assets.id'), nullable=False)
    type         = Column(String, nullable=False)
    params       = Column(JSON, nullable=False)
    years_back   = Column(Integer, nullable=False)
    source       = Column(String, nullable=False, default="precomputed")

    asset         = relationship('Asset', back_populates='patterns')
    statistics    = relationship('Statistic', back_populates='pattern', uselist=False)
    equity_series = relationship('EquitySeries', back_populates='pattern')

class Statistic(Base):
    __tablename__ = 'statistics'
    pattern_id        = Column(Integer, ForeignKey('patterns.id'), primary_key=True)
    gross_profit_pct  = Column(Float, nullable=False)
    gross_loss_pct    = Column(Float, nullable=False)
    net_return_pct    = Column(Float, nullable=False)
    win_rate          = Column(Float, nullable=False)
    profit_factor     = Column(Float)
    expectancy        = Column(Float)
    max_drawdown_pct  = Column(Float)
    drawdown_start    = Column(DateTime, nullable=True)
    drawdown_end      = Column(DateTime, nullable=True)
    recovery_days     = Column(Integer, nullable=False)
    sharpe_ratio      = Column(Float)
    sortino_ratio     = Column(Float)
    annual_volatility_pct = Column(Float)
    num_trades        = Column(Integer)
    avg_trade_pct     = Column(Float)
    max_consec_wins   = Column(Integer)
    max_consec_losses = Column(Integer)
    extra_json        = Column(JSONB, nullable=True)

    pattern = relationship('Pattern', back_populates='statistics')

class EquitySeries(Base):
    __tablename__ = 'equity_series'
    id           = Column(Integer, primary_key=True)
    pattern_id   = Column(Integer, ForeignKey('patterns.id'), nullable=False)
    timestamp    = Column(DateTime, nullable=False)
    equity_value = Column(Float, nullable=False)

    pattern = relationship('Pattern', back_populates='equity_series')

class BacktestParams(Base):
    __tablename__ = "backtest_params"
    id           = Column(Integer, primary_key=True)
    user_id      = Column(Integer, nullable=False)
    asset        = Column(String, nullable=False)
    pattern_type = Column(SAEnum("annual", "monthly", "intraday", name="pattern_types"), nullable=False)
    years_back   = Column(Integer, nullable=False)
    range_config = Column(JSON, nullable=False)
    created_at   = Column(DateTime, default=datetime.utcnow)

    results = relationship("BacktestResult", back_populates="params")

class BacktestResult(Base):
    __tablename__ = "backtest_result"
    id           = Column(Integer, primary_key=True)
    params_id    = Column(Integer, ForeignKey("backtest_params.id"), nullable=False)
    created_at   = Column(DateTime, default=datetime.utcnow)
    source       = Column(String, nullable=False, default="custom")

    params                 = relationship("BacktestParams", back_populates="results")
    trades                 = relationship("Trade", back_populates="backtest_result")
    equity_points          = relationship("EquityPoint", back_populates="backtest_result")
    equity_floating_points = relationship(
        "EquityFloatingPoint",
        back_populates="result",
        cascade="all, delete-orphan"
    )

    def to_summary_dict(self):
        return {
            "id":           self.id,
            "created_at":   self.created_at.isoformat(),
            "asset":        self.params.asset,
            "pattern_type": self.params.pattern_type,
            "years_back":   self.params.years_back,
            "range_config": self.params.range_config,
        }

    def to_full_dict(self):
        return {
            **self.to_summary_dict(),
            "equity": {
                ep.timestamp.isoformat(): ep.value
                for ep in self.equity_points
            },
            "trade_list": [
                {col: getattr(t, col) for col in t.__table__.columns.keys()}
                for t in self.trades
            ],
        }

class Trade(Base):
    __tablename__ = "trade"
    id          = Column(Integer, primary_key=True)
    backtest_id = Column(Integer, ForeignKey("backtest_result.id"), nullable=False)
    year        = Column(Integer, nullable=False)
    start_date  = Column(DateTime, nullable=False)
    end_date    = Column(DateTime, nullable=False)
    start_price = Column(Float, nullable=False)
    end_price   = Column(Float, nullable=False)
    profit      = Column(Float, nullable=False)
    profit_pct  = Column(Float, nullable=False)
    max_rise    = Column(Float, nullable=True)
    max_drop    = Column(Float, nullable=True)

    backtest_result = relationship("BacktestResult", back_populates="trades")

class EquityPoint(Base):
    __tablename__ = "equity_point"
    id          = Column(Integer, primary_key=True, index=True)
    backtest_id = Column(Integer, ForeignKey("backtest_result.id"), nullable=False)
    timestamp   = Column(DateTime, nullable=False)
    value       = Column(Float, nullable=False)
    pattern_id  = Column(Integer, ForeignKey("patterns.id"))

    backtest_result = relationship("BacktestResult", back_populates="equity_points")

class EquityFloatingPoint(Base):
    __tablename__ = "equity_floating_point"
    id           = Column(Integer, primary_key=True)
    backtest_id  = Column(Integer, ForeignKey("backtest_result.id", ondelete="CASCADE"), nullable=False)
    timestamp    = Column(DateTime(timezone=True), nullable=False)
    value        = Column(Float, nullable=False)

    result = relationship("BacktestResult", back_populates="equity_floating_points")

class SavedBacktest(Base):
    __tablename__ = "saved_backtests"
    id             = Column(Integer, primary_key=True, autoincrement=True)
    user_id        = Column(Integer, nullable=False)
    backtest_id    = Column(Integer, ForeignKey("backtest_result.id"), nullable=False)
    saved_at       = Column(DateTime(timezone=True), server_default=func.now())

    backtest        = relationship("BacktestResult")
    portfolio_items = relationship(
        "PortfolioItem",
        back_populates="saved_backtest",
        cascade="all, delete-orphan",
        passive_deletes=True,
        overlaps="backtest,portfolio_items"
    )

class Portfolio(Base):
    __tablename__ = "portfolios"
    id             = Column(Integer, primary_key=True)
    user_id        = Column(Integer, nullable=False)
    name           = Column(Text, nullable=False)
    created_at     = Column(DateTime(timezone=True), server_default=func.now())
    execution_mode = Column(SAEnum("paper", "live", name="execution_mode_enum"), nullable=False, default="paper")

    items            = relationship("PortfolioItem", back_populates="portfolio")
    simulated_trades = relationship("SimulatedTrade", back_populates="portfolio", cascade="all, delete-orphan")

class PortfolioItem(Base):
    __tablename__ = "portfolio_items"
    portfolio_id      = Column(Integer, ForeignKey("portfolios.id", ondelete="CASCADE"), primary_key=True)
    saved_backtest_id = Column(Integer, ForeignKey("saved_backtests.id", ondelete="CASCADE"), primary_key=True)
    weight_pct        = Column(Numeric(5,2), nullable=False, default=100.00)

    portfolio      = relationship("Portfolio", back_populates="items")
    saved_backtest = relationship("SavedBacktest", back_populates="portfolio_items", passive_deletes=True, overlaps="backtest,portfolio_items")
    backtest       = relationship("SavedBacktest", foreign_keys=[saved_backtest_id], passive_deletes=True)

class User(Base, UserMixin):
    __tablename__ = "users"

    id                   = Column(Integer, primary_key=True)
    username             = Column(String(50), unique=True, nullable=False)
    password             = Column(String(128), nullable=False)
    created_at           = Column(DateTime, default=datetime.utcnow, nullable=False)

    google_id            = Column(String(128), unique=True, nullable=True)
    email                = Column(String(128), unique=True, nullable=True)

    # ──────────────────────────────────────────────────────────────────────────
    # campi di subscription
    subscription         = Column(
        SAEnum(SubscriptionType, name="subscription_type"),
        default=SubscriptionType.FREE,
        nullable=False
    )
    subscription_expires = Column(DateTime, nullable=True)
    # ──────────────────────────────────────────────────────────────────────────

class SimulatedTrade(Base):
    __tablename__ = "simulated_trades"
    id           = Column(Integer, primary_key=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False)
    symbol       = Column(String, nullable=False)
    side         = Column(SAEnum("buy", "sell", name="trade_side_enum"), nullable=False)
    volume       = Column(Float, nullable=False)
    open_price   = Column(Float, nullable=False)
    open_time    = Column(DateTime, nullable=False, default=datetime.utcnow)
    close_price  = Column(Float, nullable=True)
    close_time   = Column(DateTime, nullable=True)
    profit       = Column(Float, nullable=True)

    portfolio = relationship("Portfolio", back_populates="simulated_trades")

class LatestPrice(Base):
    __tablename__ = 'latest_price'

    symbol = Column(String, primary_key=True)
    bid    = Column(Numeric, nullable=True)
    ask    = Column(Numeric, nullable=True)
    last   = Column(Numeric, nullable=True)
    time   = Column(DateTime, server_default=func.now(), nullable=False)
