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


def _normalize_player_name(name):
    return " ".join((name or "").strip().lower().split())


def _compute_player_averages_from_ranking(conn):
    """Compute player averages the same way the ranking view computes moyennes."""
    players = conn.execute(
        "SELECT name, avg_libre, avg_band FROM players"
    ).fetchall()

    rows = conn.execute(
        """
        SELECT player, game_type, SUM(total) AS car, SUM(turns) AS turns
        FROM results
        GROUP BY player, game_type
        """
    ).fetchall()

    ranking_averages = {}
    for row in rows:
        player_key = _normalize_player_name(row["player"])
        turns = row["turns"] or 0
        average = (row["car"] / turns) if turns else None

        ranking_averages.setdefault(player_key, {})[row["game_type"]] = average

    computed = {}
    for player in players:
        name = player["name"]
        key = _normalize_player_name(name)

        # Keep existing defaults for games without ranking rows.
        avg_libre = player["avg_libre"] if player["avg_libre"] is not None else 0.5
        avg_band = player["avg_band"] if player["avg_band"] is not None else 0.5

        if key in ranking_averages:
            libre_avg = ranking_averages[key].get("libre")
            band_avg = ranking_averages[key].get("band")

            if libre_avg is not None:
                avg_libre = libre_avg
            if band_avg is not None:
                avg_band = band_avg

        computed[key] = (avg_libre, avg_band)

    return computed


def _apply_player_averages(conn, normalized_averages):
    restored_rows = conn.execute("SELECT name FROM players").fetchall()
    restored_name_map = {
        _normalize_player_name(row["name"]): row["name"]
        for row in restored_rows
    }

    updated_count = 0
    for normalized_name, (avg_libre, avg_band) in normalized_averages.items():
        target_name = restored_name_map.get(normalized_name)
        if not target_name:
            continue

        updated = conn.execute(
            """
            UPDATE players
            SET avg_libre=?, avg_band=?
            WHERE name=?
            """,
            (avg_libre, avg_band, target_name)
        )
        updated_count += updated.rowcount

    conn.commit()
    return updated_count

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

        request_data = request.json or {}

        if has_active_matches():
            return {"error": "backup herstellen niet toegestaan tijdens actieve wedstrijden"}, 409

        file = request_data.get("file")
        preserve_current_targets = bool(request_data.get("preserve_current_targets", False))

        current_player_averages = {}

        if preserve_current_targets:
            conn = get_db()
            try:
                # Capture averages as ranking computes them in the current DB.
                current_player_averages = _compute_player_averages_from_ranking(conn)
            finally:
                conn.close()

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

        conn = get_db()
        try:
            if preserve_current_targets and current_player_averages:
                restored_targets = _apply_player_averages(conn, current_player_averages)
            else:
                # Keep restored targets aligned with ranking-based moyennes.
                restored_averages = _compute_player_averages_from_ranking(conn)
                restored_targets = _apply_player_averages(conn, restored_averages)
        finally:
            conn.close()

        return {
            "status": "ok",
            "preserve_current_targets": preserve_current_targets,
            "restored_targets": restored_targets
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