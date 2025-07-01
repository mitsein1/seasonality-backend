from flask import Blueprint, jsonify
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

seasonality_bp = Blueprint('seasonality', __name__, url_prefix='/api/seasonality')

@seasonality_bp.route('', methods=['GET'])
def seasonality():
    # Import get_engine dentro la funzione per evitare circular import
    from backend.app import get_engine
    
    # Inizializza sessione DB
    Session = sessionmaker(bind=get_engine())
    session = Session()

    # Query distinct values per filtro, usando text() per raw SQL
    pattern_types = [row[0] for row in session.execute(
        text("SELECT DISTINCT type FROM patterns")
    ).fetchall()]
    years_back = [row[0] for row in session.execute(
        text("SELECT DISTINCT years_back FROM patterns")
    ).fetchall()]
    asset_groups = [row[0] for row in session.execute(
        text("SELECT DISTINCT \"group\" FROM assets")
    ).fetchall()]
    symbols = [row[0] for row in session.execute(
        text("SELECT DISTINCT symbol FROM assets")
    ).fetchall()]

    session.close()

    return jsonify({
        'patternTypes': pattern_types,
        'yearsBack':    years_back,
        'assetGroups':  asset_groups,
        'symbols':      symbols
    })
