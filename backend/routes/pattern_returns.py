from flask import Blueprint, jsonify
from sqlalchemy.orm import sessionmaker
from backend.db.models import EquityPoint

pattern_returns_bp = Blueprint('pattern_returns', __name__, url_prefix='/api/pattern_returns')

@pattern_returns_bp.route('/<int:pattern_id>', methods=['GET'])
def pattern_returns(pattern_id):
    # import get_engine solo al bisogno
    from backend.app import get_engine

    Session = sessionmaker(bind=get_engine())
    session = Session()

    points = (
        session.query(EquityPoint)
               .filter_by(pattern_id=pattern_id)
               .order_by(EquityPoint.timestamp)
               .all()
    )
    equity = [
        {'timestamp': p.timestamp.isoformat(), 'value': p.equity_value}
        for p in points
    ]

    session.close()
    return jsonify({
        'patternId': pattern_id,
        'equity':     equity,
        'buyHold':    []  # TODO: implement buy & hold series
    })
