from flask import Blueprint, request, jsonify
from sqlalchemy.orm import sessionmaker
from sqlalchemy import cast, String, and_, extract, Integer
from backend.services.cache import get_cache, set_cache
from backend.db.models import Asset, Pattern, Statistic, EquitySeries
from backend.db.session import SessionLocal


import pandas as pd
from ..services.backtest_engine import _drawdown_duration

screener_bp = Blueprint('screener', __name__, url_prefix='/api/screener')

def make_cache_key(args: dict) -> str:
    parts = []
    for k in sorted(args):
        v = args[k]
        if isinstance(v, list):
            v = ",".join(map(str, sorted(v)))
        parts.append(f"{k}={v}")
    return "screener:" + "|".join(parts)

@screener_bp.route('', methods=['GET'])
def screener():
    from backend.app import get_engine
    # 1) Build cache key
    params = {k: request.args.getlist(k) or request.args.get(k) for k in request.args}
    cache_key = make_cache_key(params)
    cached = get_cache(cache_key)
    if cached is not None:
        return jsonify(cached)

    # 2) Open DB session
    session = sessionmaker(bind=get_engine())()

    # 3) Read filter params
    pattern_type = request.args.get('patternType')
    years_back   = request.args.getlist('yearsBack', type=int)
    asset_groups = request.args.getlist('assetGroups') or request.args.getlist('group')
    symbols      = request.args.getlist('symbols')     or request.args.getlist('asset')
    sort_by      = request.args.get('sortBy')
    sort_order   = request.args.get('sortOrder', 'desc')

    # Any extra time-params
    exclude = {'patternType','yearsBack','assetGroups','symbols','group','asset','sortBy','sortOrder','limit','page'}
    time_params = {k: request.args.get(k) for k in request.args if k not in exclude}

    # 4) Base query
    q = session.query(Pattern, Asset, Statistic) \
        .join(Asset,   Pattern.asset_id   == Asset.id) \
        .join(Statistic, Statistic.pattern_id == Pattern.id)

    if pattern_type:
        q = q.filter(Pattern.type == pattern_type)
    if years_back:
        q = q.filter(Pattern.years_back.in_(years_back))
    if asset_groups:
        q = q.filter(Asset.group.in_(asset_groups))
    if symbols:
        q = q.filter(Asset.symbol.in_(symbols))
    for k, v in time_params.items():
        if v is not None:
            q = q.filter(cast(Pattern.params[k], String) == str(v))

    # 5) Sorting only on pure-SQL columns
    sortables = {
        'grossProfitPct': Statistic.gross_profit_pct,
        'grossLossPct':   Statistic.gross_loss_pct,
        'netReturnPct':   Statistic.net_return_pct,
        'winRate':        Statistic.win_rate,
        'profitFactor':   Statistic.profit_factor,
        'expectancy':     Statistic.expectancy,
        'maxDrawdownPct': Statistic.max_drawdown_pct,
        'sharpeRatio':    Statistic.sharpe_ratio,
        'sortinoRatio':   Statistic.sortino_ratio,
        'assetSymbol':    Asset.symbol,
        'yearsBack':      Pattern.years_back,
    }
    if sort_by in sortables:
        col = sortables[sort_by]
        q = q.order_by(col.asc() if sort_order=='asc' else col.desc())
    elif sort_by:
        print(f"[screener.py] ⚠️ cannot sort by JSON field `{sort_by}` via SQL, ignoring.")

    # 6) Pagination
    try:
        page  = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 50))
    except ValueError:
        page, limit = 1, 50
    offset = (page-1)*limit

    total = q.count()
    q = q.limit(limit).offset(offset)

    # 7) Build output array
    out = []
    for pattern, asset, stat in q.all():
        ej = stat.extra_json or {}
        dr = ej.get("dd_realized") or {}
        df = ej.get("dd_floating") or {}

        # Fallback: if no realized‐drawdown in JSON, recompute from stored EquitySeries
        if dr.get("max_drawdown_pct") is None:
            rows = (
                session.query(EquitySeries)
                       .filter_by(pattern_id=pattern.id)
                       .order_by(EquitySeries.timestamp)
                       .all()
            )
            if rows:
                ser = pd.Series(
                    { r.timestamp: r.equity_value for r in rows }
                ).sort_index()
                dr = _drawdown_duration(ser)

        out.append({
            'id':           pattern.id,
            'assetSymbol':  asset.symbol,
            'patternType':  pattern.type,
            'params':       pattern.params,
            'yearsBack':    pattern.years_back,
            'stats': {
                'grossProfitPct':        stat.gross_profit_pct,
                'grossLossPct':          stat.gross_loss_pct,
                'netReturnPct':          stat.net_return_pct,
                'winRate':               stat.win_rate,
                'profitFactor':          stat.profit_factor,
                'expectancy':            stat.expectancy,
                'maxDrawdownPct':        stat.max_drawdown_pct,
                'sharpeRatio':           stat.sharpe_ratio,
                'sortinoRatio':          stat.sortino_ratio,
                # realized drawdown (from JSON or fallback):
                'realizedMaxDrawdownPct': dr.get("max_drawdown_pct"),
                'realizedDdDurationDays': dr.get("dd_duration_days"),
                # floating drawdown (only if JSON present):
                'floatingMaxDrawdownPct':  df.get("max_drawdown_pct"),
                'floatingDdDurationDays':  df.get("dd_duration_days"),
            }
        })

    session.close()

    # 8) Cache and return
    set_cache(cache_key, {'data': out, 'total': total}, ttl=600)
    return jsonify({'data': out, 'total': total})


@screener_bp.route('/filter-by-date', methods=['GET'])
def filter_by_date():
    session = SessionLocal()
    try:
        pattern_type = request.args.get('patternType')
        start_month = request.args.get('start_month', type=int)
        start_day = request.args.get('start_day', type=int)
        end_month = request.args.get('end_month', type=int)
        end_day = request.args.get('end_day', type=int)

        start_day_monthly = request.args.get('start_day_monthly', type=int)
        duration_days = request.args.get('duration_days', type=int)

        start_hour = request.args.get('start_hour', type=int)
        end_hour = request.args.get('end_hour', type=int)

        years_back = request.args.getlist('yearsBack', type=int)
        asset_groups = request.args.getlist('assetGroups') or request.args.getlist('group')
        symbols = request.args.getlist('symbols') or request.args.getlist('asset')

        q = (
            session.query(Pattern)
            .join(Asset, Pattern.asset_id == Asset.id)
            .filter(Pattern.type == pattern_type)
        )

        if years_back:
            q = q.filter(Pattern.years_back.in_(years_back))
        if asset_groups:
            q = q.filter(Asset.group.in_(asset_groups))
        if symbols:
            q = q.filter(Asset.symbol.in_(symbols))

        if pattern_type == "annual":
            if start_month is not None:
                q = q.filter(cast(Pattern.params.op('->>')('start_month'), Integer) == start_month)
            if start_day is not None:
                q = q.filter(cast(Pattern.params.op('->>')('start_day'), Integer) == start_day)
            if end_month is not None:
                q = q.filter(cast(Pattern.params.op('->>')('end_month'), Integer) == end_month)
            if end_day is not None:
                q = q.filter(cast(Pattern.params.op('->>')('end_day'), Integer) == end_day)

        elif pattern_type == "monthly":
            if start_day_monthly is not None:
                q = q.filter(cast(Pattern.params.op('->>')('start_day'), Integer) == start_day_monthly)
            if duration_days is not None:
                q = q.filter(cast(Pattern.params.op('->>')('window_days'), Integer) == duration_days)

        elif pattern_type == "intraday":
            if start_hour is not None:
                q = q.filter(cast(Pattern.params.op('->>')('start_hour'), Integer) == start_hour)
            if end_hour is not None:
                q = q.filter(cast(Pattern.params.op('->>')('end_hour'), Integer) == end_hour)

        results = q.limit(1000).all()

        out = []
        for p in results:
            stats = p.statistics
            out.append({
                'id': p.id,
                'assetSymbol': p.asset.symbol,
                'assetGroup': p.asset.group,
                'patternType': p.type,
                'yearsBack': p.years_back,
                'params': p.params,
                'statistics': {
                    'gross_profit_pct': stats.gross_profit_pct,
                    'gross_loss_pct': stats.gross_loss_pct,
                    'net_return_pct': stats.net_return_pct,
                    'win_rate': stats.win_rate,
                    'profit_factor': stats.profit_factor,
                    'expectancy': stats.expectancy,
                    'max_drawdown_pct': stats.max_drawdown_pct,
                    'drawdown_start': stats.drawdown_start.isoformat() if stats.drawdown_start else None,
                    'drawdown_end': stats.drawdown_end.isoformat() if stats.drawdown_end else None,
                    'recovery_days': stats.recovery_days,
                    'sharpe_ratio': stats.sharpe_ratio,
                    'sortino_ratio': stats.sortino_ratio,
                    'annual_volatility_pct': stats.annual_volatility_pct,
                    'num_trades': stats.num_trades,
                    'avg_trade_pct': stats.avg_trade_pct,
                    'max_consec_wins': stats.max_consec_wins,
                    'max_consec_losses': stats.max_consec_losses,
                    'extra_json': stats.extra_json
                } if stats else None
            })

        return jsonify(out)

    finally:
        session.close()




