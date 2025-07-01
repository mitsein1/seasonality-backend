import os
from dotenv import load_dotenv
load_dotenv()

# Dev-only: permetti OAuth2 su HTTP e rilassa lo scope
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE']   = '1'

from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_login import LoginManager, current_user
from flask_socketio import SocketIO, join_room, leave_room
from werkzeug.middleware.proxy_fix import ProxyFix

from backend.db.session import SessionLocal
from backend.db.models import User

from backend.routes.oauth             import oauth_bp
from backend.routes.auth_routes       import auth_bp
from backend.routes.seasonality       import seasonality_bp
from backend.routes.screener          import screener_bp
from backend.routes.pattern_returns   import pattern_returns_bp
from backend.routes.assets            import assets_bp
from backend.routes.backtest          import bp as backtest_bp
from backend.routes.portfolio         import portfolio_bp
from backend.routes.pattern_aggregate import pattern_agg_bp
from backend.routes.strategy          import strategy_bp
from backend.routes.buy_and_hold      import buy_hold_bp
from backend.db.session import engine

def get_engine():
    """Per lo screener: restituisce l'engine SQLAlchemy configurato."""
    return engine


def create_app():
    app = Flask(__name__)

    # Se sei dietro Cloudflare Tunnel: forza il wsgi.url_scheme = https
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    # Secret & cookie security
    app.secret_key = os.getenv("SECRET_KEY", "fallback-secret")
    app.config.update({
        'SESSION_COOKIE_NAME':    'seasonality_session',
        'SESSION_COOKIE_HTTPONLY': True,
        'SESSION_COOKIE_SECURE':   True,
        'SESSION_COOKIE_SAMESITE': 'None',
    })

    # CORS: solo il frontend Lovable deve poter chiamare /api/*
    FRONTEND = os.getenv("FRONTEND_URL")
    CORS(app,
        supports_credentials=True,
        resources={r"/api/*": {"origins": [
            os.getenv("FRONTEND_URL"),
            "http://localhost:3000"
        ]}})


    # Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "auth_bp.login"

    @login_manager.user_loader
    def load_user(user_id):
        db = SessionLocal()
        user = db.get(User, int(user_id))
        db.close()
        return user

    # Protegge tutte le /api/* tranne auth e login, ma lascia passare OPTIONS per il CORS
    @app.before_request
    def require_login_for_api():
        p = request.path
        if p.startswith("/api/") and not (p.startswith("/api/auth/") or p.startswith("/login")):
            # preflight CORS → non richiede autenticazione
            if request.method == "OPTIONS":
                return None
            if not current_user.is_authenticated:
                return jsonify({"error": "Unauthenticated"}), 401

    # Health‐check /info dell’utente loggato
    @app.route("/api/auth/me", methods=["GET"])
    def health_check():
        if current_user.is_authenticated:
            return jsonify({
                "message": "Logged in",
                "user": {
                    "id": current_user.get_id(),
                    "email": current_user.email,
                    "created_at": current_user.created_at.isoformat(),
                    "subscription": current_user.subscription.value,
                    "subscription_expires": (
                        current_user.subscription_expires.isoformat()
                        if current_user.subscription_expires else None
                    )
                }
            })
        else:
            return jsonify({"message": "Not logged in"}), 200


    # Registra tutti i blueprint (OAuth, auth tradizionale, business logic…)
    app.register_blueprint(oauth_bp,    url_prefix="/login")
    app.register_blueprint(auth_bp)
    app.register_blueprint(seasonality_bp)
    app.register_blueprint(screener_bp)
    app.register_blueprint(pattern_returns_bp)
    app.register_blueprint(assets_bp)
    app.register_blueprint(backtest_bp)
    app.register_blueprint(portfolio_bp)
    app.register_blueprint(pattern_agg_bp)
    app.register_blueprint(strategy_bp)
    app.register_blueprint(buy_hold_bp)

    return app

app = create_app()

# SocketIO + Redis
REDIS_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
socketio = SocketIO(
    app,
    cors_allowed_origins=[os.getenv("FRONTEND_URL"), "http://localhost:3000"],
    supports_credentials=True,
    message_queue=REDIS_URL,
    ping_interval=25,
    ping_timeout=60,
    async_mode="threading"
)

@socketio.on("connect")
def on_connect():
    pid = request.args.get("pid")
    if pid:
        join_room(f"portfolio_{pid}")

@socketio.on("join_portfolio")
def on_join_portfolio(data):
    pid = data.get("portfolio_id")
    if pid:
        join_room(f"portfolio_{pid}")

@socketio.on("leave_portfolio")
def on_leave_portfolio(data):
    pid = data.get("portfolio_id")
    if pid:
        leave_room(f"portfolio_{pid}")

def emit_to_portfolio(event: str, payload: dict):
    pid = payload.get("portfolio_id")
    if pid:
        socketio.emit(event, payload, room=f"portfolio_{pid}")

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5000"))
    print(f"🚀 SocketIO Server starting on {host}:{port}")
    socketio.run(app, host=host, port=port)
