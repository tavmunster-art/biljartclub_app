from flask import Flask
from flask_socketio import SocketIO

socketio = SocketIO(cors_allowed_origins="*")


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'secret!'

    socketio.init_app(app)

    # 🔧 database init
    from .models import init_db
    init_db()

    # ========================
    # BLUEPRINTS
    # ========================
    from .routes.main import main_bp
    from .routes.matches import matches_bp
    from .routes.players import players_bp
    from .routes.settings import settings_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(matches_bp)
    app.register_blueprint(players_bp)
    app.register_blueprint(settings_bp)

    # ========================
    # SOCKETS
    # ========================
    from .sockets.events import register_socket_events
    register_socket_events(socketio)

    return app