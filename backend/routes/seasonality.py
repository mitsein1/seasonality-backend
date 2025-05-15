from flask import Blueprint, request, jsonify

seasonality_bp = Blueprint('seasonality', __name__, url_prefix='/api/seasonality')

@seasonality_bp.route('', methods=['GET'])
def seasonality():
    # TODO: leggere request.args, filtrare in base a tipo pattern,
    #       gruppi asset, orizzonte temporale e restituire metadata!
    return jsonify({
        'message': 'seasonality endpoint in costruzione'
    })
