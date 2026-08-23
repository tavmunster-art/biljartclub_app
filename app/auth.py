import hmac
import os
import secrets
import tempfile
from functools import wraps

from flask import jsonify, redirect, request, session, url_for
from app.database import BASE_DIR


PASSWORD_FILE = os.path.join(BASE_DIR, "coordinator.password")
SECRET_FILE = os.path.join(BASE_DIR, "session.secret")
RUNTIME_SESSION_ID = secrets.token_urlsafe(32)


def get_session_secret():
    configured = os.environ.get("BILJART_SECRET_KEY")
    if configured:
        return configured

    try:
        with open(SECRET_FILE, encoding="utf-8") as secret_file:
            return secret_file.read().strip()
    except OSError:
        return secrets.token_hex(32)


def get_coordinator_password():
    configured = os.environ.get("COORDINATOR_PASSWORD")
    if configured:
        return configured

    try:
        with open(PASSWORD_FILE, encoding="utf-8") as password_file:
            return password_file.read().strip()
    except OSError:
        return ""


def verify_coordinator_password(password):
    configured = get_coordinator_password()
    return bool(configured) and hmac.compare_digest(password, configured)


def get_runtime_session_id():
    return RUNTIME_SESSION_ID


def change_coordinator_password(password):
    password = password.strip()
    if len(password) < 8:
        raise ValueError("Het wachtwoord moet minimaal 8 tekens bevatten")

    directory = os.path.dirname(PASSWORD_FILE)
    os.makedirs(directory, exist_ok=True)

    fd, temporary_path = tempfile.mkstemp(dir=directory)
    try:
        os.chmod(temporary_path, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as password_file:
            password_file.write(password + "\n")
        os.replace(temporary_path, PASSWORD_FILE)
    except Exception:
        try:
            os.unlink(temporary_path)
        except OSError:
            pass
        raise


def coordinator_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if (
            session.get("coordinator_authenticated")
            and session.get("runtime_session_id") == RUNTIME_SESSION_ID
        ):
            return view(*args, **kwargs)

        if request.method == "GET":
            return redirect(url_for("main.login", next=request.path))

        return jsonify({"error": "coordinator login vereist"}), 401

    return wrapped_view
