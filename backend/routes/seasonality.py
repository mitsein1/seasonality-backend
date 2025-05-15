from flask import Blueprint, jsonify
from sqlalchemy.orm import sessionmaker

from backend.db.models import Pattern, Asset
from backend.app import get_engine

seasonality_bp = Blueprint('seasonality', __name__, url_prefix='/api/seasonality')

@seasonality_bp.route('', methods=['GET'])
def seasonality():
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    session = Session()

    # Distinct pattern types
    pattern_types = [pt for (pt,) in session.query(Pattern.type).distinct().all()]
    # Distinct years_back values, sorted
    years_back = sorted({yb for (yb,) in session.query(Pattern.years_back).distinct().all()})
    # Distinct asset groups
    asset_groups = [ag for (ag,) in session.query(Asset.group).distinct().all()]
    # Distinct symbols
    symbols = [s for (s,) in session.query(Asset.symbol).distinct().all()]

    session.close()
    return jsonify({
        'patternTypes':    pattern_types,
        'yearsBack':       years_back,
        'assetGroups':     asset_groups,
        'symbols':         symbols
    })
