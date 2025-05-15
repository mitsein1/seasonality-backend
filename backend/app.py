import os
from flask import Flask
from sqlalchemy import create_engine

# Importa i blueprint
from backend.routes.screener import screener_bp
from backend.routes.seasonality import seasonality_bp
from backend.routes.pattern_returns import pattern_returns_bp

def get_engine():
    db_url = os.getenv('DATABASE_URL', 'sqlite:///./data.db')
    return create_engine(db_url, echo=False, future=True)

def create_app():
    app = Flask(__name__)

    # Registra tutti i blueprint
    app.register_blueprint(screener_bp)
    app.register_blueprint(seasonality_bp)
    app.register_blueprint(pattern_returns_bp)

    return app

if __name__ == '__main__':
    app = create_app()
    host = '0.0.0.0'
    port = int(os.getenv('PORT', 5000))
    app.run(host=host, port=port)
