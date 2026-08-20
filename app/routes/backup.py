from flask import Blueprint, request
import os
import shutil
from datetime import datetime

from app.database import (
    BACKUP_DIR,
    DB_PATH,
    get_db
)
from app.auth import coordinator_required
from app.routes.matches import has_active_matches

backup_bp = Blueprint("backup", __name__)

DB_FILE = DB_PATH

# =========================================
# CREATE BACKUP
# =========================================
@backup_bp.route("/backup/create", methods=["POST"])
@coordinator_required
def create_backup():

    try:

        if has_active_matches():
            return {"error": "backup niet toegestaan tijdens actieve wedstrijden"}, 409

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
@coordinator_required
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
@coordinator_required
def restore_backup():

    try:

        if has_active_matches():
            return {"error": "backup herstellen niet toegestaan tijdens actieve wedstrijden"}, 409

        file = request.json.get("file")

        if not file:

            return {
                "error": "geen backup geselecteerd"
            }

        if os.path.basename(file) != file or not file.endswith(".db"):
            return {"error": "ongeldig backupbestand"}

        backup_path = os.path.join(BACKUP_DIR, file)

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
@coordinator_required
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