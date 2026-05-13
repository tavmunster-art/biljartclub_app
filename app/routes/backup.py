from flask import Blueprint, request
import os
import shutil
import sys
from datetime import datetime

from app.database import get_db

backup_bp = Blueprint("backup", __name__)

# =========================================
# BASE DIRECTORY
# =========================================

# werkt voor source én pyinstaller exe
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..")
    )

# =========================================
# PATHS
# =========================================

DB_FILE = os.path.join(BASE_DIR, "instance", "biljart.db")

BACKUP_DIR = os.path.join(BASE_DIR, "backups")

# =========================================
# CREATE BACKUP
# =========================================
@backup_bp.route("/backup/create", methods=["POST"])
def create_backup():

    try:

        # map maken indien nodig
        os.makedirs(BACKUP_DIR, exist_ok=True)

        # controle database
        if not os.path.exists(DB_FILE):

            return {
                "error": f"database niet gevonden: {DB_FILE}"
            }

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        filename = f"backup_{ts}.db"

        backup_path = os.path.join(
            BACKUP_DIR,
            filename
        )

        shutil.copy2(DB_FILE, backup_path)

        return {
            "status": "ok",
            "file": filename
        }

    except Exception as e:

        return {
            "error": str(e)
        }

# =========================================
# LIST BACKUPS
# =========================================
@backup_bp.route("/backup/list")
def list_backups():

    os.makedirs(BACKUP_DIR, exist_ok=True)

    files = sorted(
        os.listdir(BACKUP_DIR),
        reverse=True
    )

    return {
        "files": files
    }

# =========================================
# RESTORE BACKUP
# =========================================
@backup_bp.route("/backup/restore", methods=["POST"])
def restore_backup():

    try:

        file = request.json.get("file")

        if not file:

            return {
                "error": "geen backup geselecteerd"
            }

        backup_path = os.path.join(
            BACKUP_DIR,
            file
        )

        if not os.path.exists(backup_path):

            return {
                "error": "backup niet gevonden"
            }

        shutil.copy2(backup_path, DB_FILE)

        return {
            "status": "ok"
        }

    except Exception as e:

        return {
            "error": str(e)
        }

# =========================================
# RESET RESULTS
# =========================================
@backup_bp.route("/backup/reset", methods=["POST"])
def reset_db():

    try:

        conn = get_db()

        conn.execute("DELETE FROM results")

        conn.commit()
        conn.close()

        return {
            "status": "reset"
        }

    except Exception as e:

        return {
            "error": str(e)
        }