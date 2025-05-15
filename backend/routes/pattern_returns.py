from flask import Blueprint, request, jsonify

pattern_returns_bp = Blueprint('pattern_returns', __name__, url_prefix='/api/pattern_returns')

@pattern_returns_bp.route('/<int:pattern_id>', methods=['GET'])
def pattern_returns(pattern_id):
    # TODO: recuperare equity series + buy&hold per pattern_id
    return jsonify({
        'patternId': pattern_id,
        'equity': [],
        'buyHold': []
    })
