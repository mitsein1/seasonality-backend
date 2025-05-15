import os
from flask import Flask, request, jsonify
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.models import Asset, Pattern, Statistic


def create_app():
    app = Flask(__name__)
    # Database URL from ENV or default
    db_url = os.getenv('DATABASE_URL', 'sqlite:///./data.db')
    engine = create_engine(db_url, echo=False, future=True)
    Session = sessionmaker(bind=engine)

    @app.route('/api/screener', methods=['GET'])
    def screener():
        session = Session()
        # Query parameters
        pattern_type = request.args.get('patternType')
        years_back = request.args.getlist('yearsBack', type=int)
        asset_groups = request.args.getlist('assetGroups')
        symbols = request.args.getlist('symbols')
        sort_by = request.args.get('sortBy')
        sort_order = request.args.get('sortOrder', 'desc')

        # Extract time-specific params (e.g. tf, start_hour, month)
        exclude_keys = {'patternType', 'yearsBack', 'assetGroups', 'symbols', 'sortBy', 'sortOrder'}
        time_params = {k: request.args.get(k) for k in request.args if k not in exclude_keys}

        # Base query joining Asset, Pattern, Statistic
        query = session.query(Pattern, Asset, Statistic) \
            .join(Asset, Pattern.asset_id == Asset.id) \
            .join(Statistic, Statistic.pattern_id == Pattern.id)

        # Apply filters
        if pattern_type:
            query = query.filter(Pattern.type == pattern_type)
        if years_back:
            query = query.filter(Pattern.years_back.in_(years_back))
        if asset_groups:
            query = query.filter(Asset.group.in_(asset_groups))
        if symbols:
            query = query.filter(Asset.symbol.in_(symbols))
        # JSON field filters
        for key, val in time_params.items():
            # Compare JSON param as text
            query = query.filter(Pattern.params[key].astext == val)

        # Sorting
        if sort_by and hasattr(Statistic, sort_by):
            col = getattr(Statistic, sort_by)
            query = query.order_by(col.asc() if sort_order == 'asc' else col.desc())

        # Execute and format
        results = query.all()
        data = []
        for pattern, asset, stat in results:
            data.append({
                'id': pattern.id,
                'assetSymbol': asset.symbol,
                'patternType': pattern.type,
                'params': pattern.params,
                'yearsBack': pattern.years_back,
                'stats': {
                    'grossProfitPct': stat.gross_profit_pct,
                    'grossLossPct': stat.gross_loss_pct,
                    'netReturnPct': stat.net_return_pct,
                    'winRate': stat.win_rate,
                    'profitFactor': stat.profit_factor,
                    'expectancy': stat.expectancy,
                    'maxDrawdownPct': stat.max_drawdown_pct,
                    'sharpeRatio': stat.sharpe_ratio,
                    'sortinoRatio': stat.sortino_ratio
                }
            })
        session.close()
        return jsonify(data)

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))

