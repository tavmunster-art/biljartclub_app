from flask import Flask
from app.auth import get_session_secret
from app.database import init_db
from app.sockets.events import socketio, register_socket_events

def create_app():

    app = Flask(__name__)
    app.config["SECRET_KEY"] = get_session_secret()

    # 🔥 database
    init_db()

    # 🔥 IMPORTS BINNEN FUNCTIE (BELANGRIJK)
    from app.routes.main import main_bp
    from app.routes.matches import matches_bp, restore_pending_results
    from app.routes.backup import backup_bp

    restore_pending_results()

    # 🔥 REGISTER
    app.register_blueprint(main_bp)
    app.register_blueprint(matches_bp)
    app.register_blueprint(backup_bp)

    # 🔥 sockets
    # socketio.init_app(app)
    socketio.init_app(
        app,
        async_mode="threading"
    )
    register_socket_events(socketio)

    return app