from flask import Flask
from app.database import init_db
from app.sockets.events import socketio, register_socket_events

def create_app():

    app = Flask(__name__)

    # 🔥 database
    init_db()

    # 🔥 IMPORTS BINNEN FUNCTIE (BELANGRIJK)
    from app.routes.main import main_bp
    from app.routes.matches import matches_bp
    from app.routes.backup import backup_bp

    # 🔥 REGISTER
    app.register_blueprint(main_bp)
    app.register_blueprint(matches_bp)
    app.register_blueprint(backup_bp)

    # 🔥 sockets
    socketio.init_app(app)
    register_socket_events(socketio)

    return app