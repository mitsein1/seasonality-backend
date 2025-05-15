from flask import Blueprint, request, jsonify
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.models import Asset, Pattern, Statistic

screener_bp = Blueprint('screener', __name__, url_prefix='/api/screener')

# Database session factory
def get_session():
    from os import getenv
    from backend.app import get_engine  # we’ll expose this in app.py
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()

@screener_bp.route('', methods=['GET'])
def screener():
    session = get_session()

    # Parametri di query
    pattern_type = request.args.get('patternType')
    years_back   = request.args.getlist('yearsBack', type=int)
    asset_groups = request.args.getlist('assetGroups')
    symbols      = request.args.getlist('symbols')
    sort_by      = request.args.get('sortBy')
    sort_order   = request.args.get('sortOrder', 'desc')

    # Estrai params dinamici (tf, month, start_hour…)
    exclude = {'patternType','yearsBack','assetGroups','symbols','sortBy','sortOrder'}
    time_params = {k: request.args.get(k) for k in request.args if k not in exclude}

    # Join Pattern ↔ Asset ↔ Statistic
    q = session.query(Pattern, Asset, Statistic) \
        .join(Asset, Pattern.asset_id==Asset.id) \
        .join(Statistic, Statistic.pattern_id==Pattern.id)

    # Filtri
    if pattern_type:
        q = q.filter(Pattern.type==pattern_type)
    if years_back:
        q = q.filter(Pattern.years_back.in_(years_back))
    if asset_groups:
        q = q.filter(Asset.group.in_(asset_groups))
    if symbols:
        q = q.filter(Asset.symbol.in_(symbols))
    for k,v in time_params.items():
        q = q.filter(Pattern.params[k].astext == v)

    # Ordine
    if sort_by and hasattr(Statistic, sort_by):
        col = getattr(Statistic, sort_by)
        q = q.order_by(col.asc() if sort_order=='asc' else col.desc())

    # Risposta
    out = []
    for pattern, asset, stat in q.all():
        out.append({
            'id': pattern.id,
            'assetSymbol': asset.symbol,
            'patternType': pattern.type,
            'params': pattern.params,
            'yearsBack': pattern.years_back,
            'stats': {
                'grossProfitPct': stat.gross_profit_pct,
                'grossLossPct':   stat.gross_loss_pct,
                'netReturnPct':   stat.net_return_pct,
                'winRate':        stat.win_rate,
                'profitFactor':   stat.profit_factor,
                'expectancy':     stat.expectancy,
                'maxDrawdownPct': stat.max_drawdown_pct,
                'sharpeRatio':    stat.sharpe_ratio,
                'sortinoRatio':   stat.sortino_ratio,
            }
        })
    session.close()
    return jsonify(out)

