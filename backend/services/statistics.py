import pandas as pd
import numpy as np
from datetime import timedelta


def get_pattern_statistics(df: pd.DataFrame, pattern_type: str, params: dict, years_back: int):
    """
    Compute statistics and equity series for a given pattern.

    Args:
        df: DataFrame with 'timestamp' and price columns (open, high, low, close).
        pattern_type: one of 'intraday', 'monthly', 'annual'.
        params: dict with pattern-specific parameters.
        years_back: int, lookback period in years.

    Returns:
        stats: dict of metrics
        equity_series: list of {'timestamp': ts, 'value': equity}
    """
    # Limit df to lookback window
    end = df['timestamp'].max()
    start = end - pd.DateOffset(years=years_back)
    data = df[(df['timestamp'] >= start) & (df['timestamp'] <= end)].copy()
    data.set_index('timestamp', inplace=True)

    # Generate returns based on pattern
    if pattern_type == 'intraday':
        tf = params['tf']
        start_h = params['start_hour']
        end_h = params['end_hour']
        # Resample to timeframe
        ohlc = data['close'].resample(tf.lower()).last().ffill()
        signals = []
        # Long at start_h, exit at end_h each day
        for day, group in ohlc.groupby(ohlc.index.date):
            day_series = group.between_time(f'{start_h}:00', f'{end_h}:00')
            if len(day_series) < 2:
                continue
            entry = day_series.iloc[0]
            exit_ = day_series.iloc[-1]
            signals.append((group.index[0].replace(hour=start_h), entry, group.index[-1].replace(hour=end_h), exit_))
        returns = [ (exit_-entry)/entry for (_, entry, _, exit_) in signals ]
        timestamps = [exit_ts for (_, _, exit_ts, _) in signals]
    elif pattern_type == 'monthly':
        ms = params['month']
        monthly = data['close'].resample('D').last().ffill()
        returns, timestamps = [], []
        # For each year in lookback
        years = sorted(list(set(monthly.index.year)))
        for yr in years:
            period = monthly[str(yr)].between_time('00:00','23:59')
            period = period[(period.index.month == ms)]
            if len(period) < 2:
                continue
            entry, exit_ = period.iloc[0], period.iloc[-1]
            returns.append((exit_-entry)/entry)
            timestamps.append(period.index[-1])
    elif pattern_type == 'annual':
        sm, sd = params['start_month'], params['start_day']
        em, ed = params['end_month'], params['end_day']
        alld = data['close'].resample('D').last().ffill()
        returns, timestamps = [], []
        years = sorted(list(set(alld.index.year)))
        for yr in years:
            start_dt = pd.Timestamp(year=yr, month=sm, day=sd)
            end_dt = pd.Timestamp(year=yr, month=em, day=ed)
            if start_dt not in alld.index or end_dt not in alld.index:
                continue
            entry, exit_ = alld.loc[start_dt], alld.loc[end_dt]
            returns.append((exit_-entry)/entry)
            timestamps.append(end_dt)
    else:
        raise ValueError(f"Unknown pattern_type {pattern_type}")

    # Equity series
    equity = [1]
    for r in returns:
        equity.append(equity[-1] * (1 + r))
    equity_series = [
        {'timestamp': timestamps[i], 'value': equity[i+1]}
        for i in range(len(returns))
    ]

    # Metrics
    arr = np.array(returns)
    gross_profit = arr[arr>0].sum()
    gross_loss = -arr[arr<0].sum()
    net = arr.sum()
    win_rate = len(arr[arr>0]) / len(arr) if len(arr)>0 else 0
    profit_factor = gross_profit / gross_loss if gross_loss>0 else np.nan
    expectancy = win_rate * arr[arr>0].mean() - (1-win_rate) * (-arr[arr<0].mean() if len(arr[arr<0])>0 else 0)

    # Drawdown
    eq = np.array(equity)
    peak = np.maximum.accumulate(eq)
    drawdowns = (eq - peak) / peak
    max_dd = drawdowns.min()
    end_idx = np.argmin(drawdowns)
    start_idx = np.argmax(eq[:end_idx]) if end_idx>0 else 0
    drawdown_start = timestamps[start_idx]
    drawdown_end = timestamps[end_idx]
    recovery_days = 0
    for i in range(end_idx, len(eq)):
        if eq[i] >= peak[start_idx]:
            recovery_days = (timestamps[i-1] - timestamps[end_idx]).days
            break

    # Volatility & Ratios
    ret_ann = arr.mean() * np.sqrt(len(arr)) if len(arr)>1 else 0
    sharpe = arr.mean() / arr.std() * np.sqrt(len(arr)) if arr.std()>0 else np.nan
    # Sortino: downside std
    downside = arr[arr<0]
    sortino = arr.mean() / downside.std() * np.sqrt(len(arr)) if len(downside)>1 else np.nan
    ann_vol = arr.std() * np.sqrt(len(arr)) if len(arr)>1 else np.nan

    stats = {
        'gross_profit_pct': gross_profit*100,
        'gross_loss_pct': gross_loss*100,
        'net_return_pct': net*100,
        'win_rate': win_rate*100,
        'profit_factor': profit_factor,
        'expectancy': expectancy,
        'max_drawdown_pct': max_dd*100,
        'drawdown_start': drawdown_start,
        'drawdown_end': drawdown_end,
        'recovery_days': recovery_days,
        'sharpe_ratio': sharpe,
        'sortino_ratio': sortino,
        'annual_volatility_pct': ann_vol*100,
        'num_trades': len(arr),
        'avg_trade_pct': arr.mean()*100 if len(arr)>0 else 0,
        'max_consec_wins': int((arr>0).astype(int).groupby((arr<=0).cumsum()).sum().max()),
        'max_consec_losses': int((arr<0).astype(int).groupby((arr>=0).cumsum()).sum().max())
    }

    return stats, equity_series
