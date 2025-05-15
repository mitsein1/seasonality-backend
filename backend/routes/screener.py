from flask import Blueprint, request, jsonify
from sqlalchemy.orm import sessionmaker
from backend.db.models import Asset, Pattern, Statistic
from backend.app import get_engine
from backend.services.cache import get_cached, set_cache

screener_bp = Blueprint('screener', __name__, url_prefix='/api/screener')

def make_cache_key(args: dict) -> str:
    # Ordina le chiavi per coerenza e serializza
    parts = []
    for k in sorted(args):
        v = args[k]
        # se è lista, ordina e unisci
        if isinstance(v, list):
            v = ",".join(map(str, sorted(v)))
        parts.append(f"{k}={v}")
    return "screener:" + "|".join(parts)

@screener_bp.route('', methods=['GET'])
def screener():
    # Estrai tutti i parametri in un dict semplice
    params = {}
    for k in request.args:
        params[k] = request.args.getlist(k) or request.args.get(k)

    cache_key = make_cache_key(params)
    cached = get_cached(cache_key)
    if cached is not None:
        return jsonify(cached)

    # --- se non in cache, esegui la query ---
    session = sessionmaker(bind=get_engine())()

    pattern_type = request.args.get('patternType')
    years_back   = request.args.getlist('yearsBack', type=int)
    asset_groups = request.args.getlist('assetGroups')
    symbols      = request.args.getlist('symbols')
    sort_by      = request.args.get('sortBy')
    sort_order   = request.args.get('sortOrder', 'desc')

    exclude = {'patternType','yearsBack','assetGroups','symbols','sortBy','sortOrder'}
    time_params = {k: request.args.get(k) for k in request.args if k not in exclude}

    q = session.query(Pattern, Asset, Statistic) \
        .join(Asset, Pattern.asset_id==Asset.id) \
        .join(Statistic, Statistic.pattern_id==Pattern.id)

    if pattern_type:
        q = q.filter(Pattern.type==pattern_type)
    if years_back:
        q = q.filter(Pattern.years_back.in_(years_back))
    if asset_groups:
        q = q.filter(Asset.group.in_(asset_groups))
    if symbols:
        q = q.filter(Asset.symbol.in_(symbols))
    for k, v in time_params.items():
        q = q.filter(Pattern.params[k].astext == v)

    if sort_by and hasattr(Statistic, sort_by):
        col = getattr(Statistic, sort_by)
        q = q.order_by(col.asc() if sort_order=='asc' else col.desc())

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

    # Salva in cache e restituisci
    set_cache(cache_key, out, expire_seconds=600)  # 10 minuti di TTL
    return jsonify(out)
