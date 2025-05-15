#!/usr/bin/env python3
# TODO: calcolo delle statistiche dei pattern
import os
import json
import yaml
import pandas as pd
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# SQLAlchemy models
from backend.db.models import Base, Asset, Pattern, Statistic, EquityPoint

# Load configuration
def load_config():
    cfg_path = Path(__file__).parents[1] / "config" / "default.yaml"
    with open(cfg_path, 'r') as f:
        return yaml.safe_load(f)

# Load pattern definitions
def load_pattern_defs():
    defs_path = Path(__file__).parents[2] / "configs" / "pattern_defs.json"
    with open(defs_path, 'r') as f:
        return json.load(f)

# Initialize DB session
def init_db(db_url: str):
    engine = create_engine(db_url, echo=False, future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session

# Compute and persist patterns
def compute_patterns():
    # Config
    cfg = load_config()
    mt5_groups = cfg["mt5"]["groups"]
    timeframes = cfg["mt5"]["timeframes"]
    history_root = Path(cfg["mt5"].get("history_path", "mt5_history"))
    db_url = os.getenv("DATABASE_URL", cfg.get("database_url"))

    # Load pattern definitions
    pattern_defs = load_pattern_defs()

    # Prepare DB
    Session = init_db(db_url)
    session = Session()

    for group, symbols in mt5_groups.items():
        for symbol in symbols:
            # Ensure Asset exists
            asset = session.query(Asset).filter_by(symbol=symbol).first()
            if not asset:
                asset = Asset(symbol=symbol, group=group)
                session.add(asset)
                session.commit()

            # For each timeframe, read CSV and compute
            for tf in timeframes:
                csv_file = history_root / group / symbol / f"{symbol}_{tf}.csv"
                if not csv_file.exists():
                    print(f"[WARN] Missing CSV for {symbol} {tf}")
                    continue

                df = pd.read_csv(csv_file, parse_dates=['timestamp'])
                df.sort_values('timestamp', inplace=True)

                # For each pattern type in defs
                for pattern_type, defs in pattern_defs.items():
                    for pat in defs:
                        params = pat.get('params', {})
                        years_back = pat.get('years_back', cfg.get('default_years_back', 5))

                        # Delegate to statistics service
                        from backend.services.statistics import get_pattern_statistics
                        stats, equity_series = get_pattern_statistics(df, pattern_type, params, years_back)

                        # Persist Pattern
                        pattern = Pattern(
                            asset_id=asset.id,
                            type=pattern_type,
                            params=params,
                            years_back=years_back
                        )
                        session.add(pattern)
                        session.flush()

                        # Persist Statistic
                        stat = Statistic(
                            pattern_id=pattern.id,
                            gross_profit_pct=stats['gross_profit_pct'],
                            gross_loss_pct=stats['gross_loss_pct'],
                            net_return_pct=stats['net_return_pct'],
                            win_rate=stats['win_rate'],
                            profit_factor=stats['profit_factor'],
                            expectancy=stats['expectancy'],
                            max_drawdown_pct=stats['max_drawdown_pct'],
                            drawdown_start=stats['drawdown_start'],
                            drawdown_end=stats['drawdown_end'],
                            recovery_days=stats['recovery_days'],
                            sharpe_ratio=stats['sharpe_ratio'],
                            sortino_ratio=stats['sortino_ratio'],
                            annual_volatility_pct=stats['annual_volatility_pct'],
                            num_trades=stats['num_trades'],
                            avg_trade_pct=stats['avg_trade_pct'],
                            max_consec_wins=stats['max_consec_wins'],
                            max_consec_losses=stats['max_consec_losses']
                        )
                        session.add(stat)

                        # Persist Equity Series
                        for point in equity_series:
                            ep = EquityPoint(
                                pattern_id=pattern.id,
                                timestamp=point['timestamp'],
                                equity_value=point['value']
                            )
                            session.add(ep)

                        session.commit()
                        print(f"[DONE] {symbol} {tf} {pattern_type} {params}")

    session.close()

if __name__ == "__main__":
    compute_patterns()
