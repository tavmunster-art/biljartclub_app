from app import create_app
from app.sockets.events import socketio
import os
import webbrowser
import threading

app = create_app()

def open_browser():
    webbrowser.open("http://127.0.0.1:5000/coordinator")

threading.Timer(1, open_browser).start()

if __name__ == "__main__":
    socketio.run(
    app,
    host=os.environ.get("APP_HOST", "0.0.0.0"),
    port=5000,
    debug=False,
    allow_unsafe_werkzeug=True
)