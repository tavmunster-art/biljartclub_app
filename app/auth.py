import hmac
import os
import secrets
import tempfile
from functools import wraps
from pathlib import Path

from flask import jsonify, redirect, request, session, url_for
from app.paths import BASE_DIR, USER_DATA_DIR


AUTH_DIR = USER_DATA_DIR
PASSWORD_FILE = os.path.join(AUTH_DIR, "coordinator.password")
SECRET_FILE = os.path.join(AUTH_DIR, "session.secret")

LEGACY_AUTH_DIRS = [
    BASE_DIR,
    os.path.join(os.environ.get("PROGRAMDATA", str(Path.home())), "BiljartClubApp")
]


def _read_existing_text_file(path):
    try:
        with open(path, encoding="utf-8-sig") as file_handle:
            value = file_handle.read().strip()
            if value:
                return value
    except OSError:
        pass

    return ""


def _read_with_legacy_fallback(primary_path, filename):
    value = _read_existing_text_file(primary_path)
    if value:
        return value

    for legacy_dir in LEGACY_AUTH_DIRS:
        legacy_path = os.path.join(legacy_dir, filename)
        value = _read_existing_text_file(legacy_path)
        if value:
            return value

    return ""


def get_session_secret():
    configured = os.environ.get("BILJART_SECRET_KEY")
    if configured:
        return configured

    existing_secret = _read_with_legacy_fallback(SECRET_FILE, "session.secret")
    if existing_secret:
        return existing_secret

    directory = os.path.dirname(SECRET_FILE)
    os.makedirs(directory, exist_ok=True)

    secret = secrets.token_hex(32)
    fd, temporary_path = tempfile.mkstemp(dir=directory)
    try:
        os.chmod(temporary_path, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as secret_file:
            secret_file.write(secret + "\n")
        os.replace(temporary_path, SECRET_FILE)
    except Exception:
        try:
            os.unlink(temporary_path)
        except OSError:
            pass
        raise

    return secret


def get_coordinator_password():
    configured = os.environ.get("COORDINATOR_PASSWORD")
    if configured:
        return configured

    return _read_with_legacy_fallback(PASSWORD_FILE, "coordinator.password")


def verify_coordinator_password(password):
    configured = get_coordinator_password()
    return bool(configured) and hmac.compare_digest(password, configured)


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
        if session.get("coordinator_authenticated"):
            return view(*args, **kwargs)

        if request.method == "GET":
            return redirect(url_for("main.login", next=request.path))

        return jsonify({"error": "coordinator login vereist"}), 401

    return wrapped_view
