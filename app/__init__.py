from flask import Flask
from app.auth import get_session_secret
from app.database import close_db_connections, init_db
from app.sockets.events import socketio, register_socket_events

def create_app():

    app = Flask(__name__)
    app.config["SECRET_KEY"] = get_session_secret()
    app.teardown_appcontext(close_db_connections)

    # 🔥 database
    init_db()

    # 🔥 IMPORTS BINNEN FUNCTIE (BELANGRIJK)
    from app.routes.main import main_bp
    from app.routes.matches import matches_bp, restore_pending_results
    from app.routes.backup import backup_bp
    from app.routes.tournament import tournament_bp

    restore_pending_results()

    # 🔥 REGISTER
    app.register_blueprint(main_bp)
    app.register_blueprint(matches_bp)
    app.register_blueprint(backup_bp)
    app.register_blueprint(tournament_bp)

    # 🔥 sockets
    # socketio.init_app(app)
    socketio.init_app(
        app,
        async_mode="threading"
    )
    register_socket_events(socketio)

    return app