import os
import shutil
import socket
import threading
import sys
from datetime import datetime

from flask import (
    Blueprint,
    render_template,
    request,
    redirect
)

# =========================================
# APP IMPORTS
# =========================================

from app.database import (
    get_db,
    DB_PATH
)

from app.routes.matches import (
    ACTIVE_MATCHES,
    PENDING_RESULTS
)

# =========================================
# REPORTLAB
# =========================================

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle
)

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

# =========================================
# BLUEPRINT
# =========================================

main_bp = Blueprint("main", __name__)

# =========================================
# PATHS
# =========================================

# NOTE:
# opgeschoond:
# oude lokale DB_PATH verwijderd
# nu centrale DB_PATH uit database.py

if getattr(sys, "frozen", False):

    # EXE MODE
    BASE_DIR = os.path.dirname(sys.executable)

else:

    # SOURCE MODE
    BASE_DIR = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..")
    )

BACKUP_DIR = os.path.join(BASE_DIR, "backups")

REPORT_DIR = os.path.join(BASE_DIR, "reports")

os.makedirs(BACKUP_DIR, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)

# =========================================
# HELPERS
# =========================================
def get_setting(conn, key, default):
    row = conn.execute(
        "SELECT value FROM settings WHERE key=?",
        (key,)
    ).fetchone()
    return int(row["value"]) if row else default


def set_setting(conn, key, value):
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (key, str(value))
    )
    conn.commit()

@main_bp.route("/match/approve", methods=["POST"])
def approve_match():

    data = request.json
    match_id = data["match_id"]

    r = PENDING_RESULTS.get(match_id)

    if not r:
        return {"error": "niet gevonden"}

    conn = get_db()

    manual_date = data.get("manual_date")

    if manual_date:

        now = manual_date + " 20:00:00"

    else:

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn.execute("""
    INSERT INTO results
    (match_id, player, opponent, total, game_type,
     ts_recorded, points, result, avg, turns, start_avg)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        match_id,
        r["player1"],
        r["player2"],
        r["total1"],
        r["game_type"],
        now,
        r["points1"],
        r["winner"],
        r["avg1"],
        r["turns"],
        r["start1"]
    ))

    conn.execute("""
    INSERT INTO results
    (match_id, player, opponent, total, game_type,
     ts_recorded, points, result, avg, turns, start_avg)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        match_id,
        r["player2"],
        r["player1"],
        r["total2"],
        r["game_type"],
        now,
        r["points2"],
        r["winner"],
        r["avg2"],
        r["turns"],
        r["start2"]
    ))

    conn.commit()

    ACTIVE_MATCHES[match_id]["status"] = "finished"

    del PENDING_RESULTS[match_id]

    return {"ok": True}


# =========================================
# HELPER FUNCTIONS
# =========================================

def get_server_ip():
    """Get the server's IP address (non-loopback)"""
    try:
        # Connect to a public IP to determine local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# =========================================
# COORDINATOR
# =========================================
@main_bp.route("/")
def home():

    ua = request.user_agent.string.lower()

    mobile_words = [
        "android",
        "iphone",
        "ipad",
        "mobile"
    ]

    # mobiel standaard naar teller
    if any(w in ua for w in mobile_words):
        return redirect("/teller")

    # desktop standaard coordinator
    return redirect("/coordinator")

@main_bp.route("/coordinator")
def coordinator():

    conn = get_db()

    rows = conn.execute("""
        SELECT name, avg_libre, avg_band
        FROM players
        ORDER BY name
    """).fetchall()

    turns = get_setting(conn, "max_turns", 20)

    players = []

    for r in rows:

        avg_libre = r["avg_libre"] or 0.5
        avg_band  = r["avg_band"] or 0.5

        target_libre = int(avg_libre * turns)
        target_band  = int(avg_band * turns)

        players.append({
            "name": r["name"],
            "target_libre": target_libre,
            "target_band": target_band
        })

    matches = list(ACTIVE_MATCHES.values())
    pending = list(PENDING_RESULTS.values())

    return render_template(
        "coordinator.html",
        players=players,
        matches=matches,
        pending=pending,
        server_ip=get_server_ip()
    )


# =========================================
# SETTINGS
# =========================================
@main_bp.route("/settings/get")
def get_settings():
    conn = get_db()
    turns = get_setting(conn, "max_turns", 20)
    return {"turns": turns}


@main_bp.route("/settings/set", methods=["POST"])
def set_settings():
    data = request.json
    turns = data.get("turns", 20)

    conn = get_db()
    set_setting(conn, "max_turns", turns)

    return {"ok": True}

# =========================================
# RANKING
# =========================================
@main_bp.route("/ranking")
def ranking():
    return render_template("ranking.html")


@main_bp.route("/ranking/data")
def ranking_data():

    conn = get_db()

    def get_data(game):

        rows = conn.execute("""
            SELECT
                player,
                SUM(total) as total_points,
                SUM(turns) as total_turns,
                SUM(points) as total_score
            FROM results
            WHERE game_type = ?
            GROUP BY player
        """, (game,)).fetchall()

        result = []

        for r in rows:

            turns = r["total_turns"] or 0
            avg = round(r["total_points"] / turns, 3) if turns else 0

            result.append({
                "player": r["player"],
                "points": r["total_score"],
                "avg": avg,
                "caramboles": r["total_points"],
                "turns": turns
            })

        return result

    return {
        "libre": get_data("libre"),
        "band": get_data("band")
    }


# =========================================
# TELLER
# =========================================

@main_bp.route("/teller")
def teller_list():

    matches = [
        m for m in ACTIVE_MATCHES.values()
        if m["status"] == "ready"
    ]

    return render_template("teller_list.html", matches=matches)


@main_bp.route("/teller/<match_id>")
def teller(match_id):

    m = ACTIVE_MATCHES.get(match_id)

    if not m:
        return "Match niet gevonden"

    
    return render_template("teller.html", match=m)


# =========================================
# DASHBOARD
# =========================================
@main_bp.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@main_bp.route("/dashboard/data")
def dashboard_data():

    from_date = request.args.get("from")
    to_date   = request.args.get("to")

    conn = get_db()

    query = """
        SELECT player, game_type, avg, ts_recorded
        FROM results
        WHERE 1=1
    """

    params = []

    if from_date:
        query += " AND date(ts_recorded) >= date(?)"
        params.append(from_date)

    if to_date:
        query += " AND date(ts_recorded) <= date(?)"
        params.append(to_date)

    query += " ORDER BY ts_recorded"

    rows = conn.execute(query, params).fetchall()

    players = conn.execute("""
        SELECT DISTINCT player FROM results
    """).fetchall()

    return {
        "matches": [dict(r) for r in rows],
        "players": [p["player"] for p in players]
    }

@main_bp.route("/players/add", methods=["POST"])
def add_player():

    name = request.form.get("name")
    avg_libre = request.form.get("avg_libre")
    avg_band  = request.form.get("avg_band")

    if name:

        try:
            avg_libre = float(avg_libre)
        except:
            avg_libre = 0.5

        try:
            avg_band = float(avg_band)
        except:
            avg_band = 0.5

        conn = get_db()

        conn.execute("""
            INSERT OR IGNORE INTO players (name, avg_libre, avg_band)
            VALUES (?, ?, ?)
        """, (name, avg_libre, avg_band))

        conn.commit()

    return redirect("/")

@main_bp.route("/players/delete", methods=["POST"])
def delete_player():

    data = request.json
    name = data.get("name")

    if not name:
        return {"error": "geen speler"}

    conn = get_db()

    # resultaten verwijderen
    conn.execute("DELETE FROM results WHERE player=?", (name,))

    # speler verwijderen
    conn.execute("DELETE FROM players WHERE name=?", (name,))

    conn.commit()

    return {"ok": True}

@main_bp.route("/history")
def history():
    return render_template("history.html")


@main_bp.route("/history/data")
def history_data():

    conn = get_db()

    rows = conn.execute("""
        SELECT *
        FROM results
        ORDER BY ts_recorded DESC
    """).fetchall()

    return {"rows": [dict(r) for r in rows]}

import os
import shutil
from datetime import datetime

# ===========================
# BACKUP
# ==========================

@main_bp.route("/backup/create", methods=["POST"])
def create_backup():

    os.makedirs(BACKUP_DIR, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    backup_name = f"biljart_{timestamp}.db"

    backup_path = os.path.join(BACKUP_DIR, backup_name)

    shutil.copy(DB_PATH, backup_path)

    return {"ok": True}


@main_bp.route("/backup/list")
def list_backups():

    os.makedirs(BACKUP_DIR, exist_ok=True)

    files = [f for f in os.listdir(BACKUP_DIR) if f.endswith(".db")]

    files.sort(reverse=True)

    return {"files": files}


@main_bp.route("/backup/restore", methods=["POST"])
def restore_backup():

    data = request.json
    filename = data.get("file")

    backup_path = os.path.join(BACKUP_DIR, filename)

    if not os.path.exists(backup_path):
        return {"error": "Bestand niet gevonden"}

    shutil.copy(backup_path, DB_PATH)

    return {"ok": True}

# ================================
# SEIZOEN AFSLUITING
# ===============================

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

@main_bp.route("/season/close", methods=["POST"])
def close_season():

    conn = get_db()

    # =========================================
    # PADEN
    # =========================================
    REPORT_DIR = os.path.join(BASE_DIR, "reports")
    BACKUP_DIR = os.path.join(BASE_DIR, "backups")

    os.makedirs(REPORT_DIR, exist_ok=True)
    os.makedirs(BACKUP_DIR, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")

    report_path = os.path.join(REPORT_DIR, f"reports_{timestamp}.pdf")

    # =========================================
    # PDF MAKEN
    # =========================================
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer,
        Table, TableStyle
    )
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet

    # =========================================
    # PDF MAKEN
    # =========================================

    doc = SimpleDocTemplate(report_path)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("Seizoen Rapport", styles["Title"]))
    elements.append(Spacer(1, 10))

    # =========================================
    # HISTORIE TABEL
    # =========================================
    elements.append(Paragraph("Historie", styles["Heading2"]))

    rows = conn.execute("""
        SELECT ts_recorded, player, opponent, total, avg, points, game_type
        FROM results
        ORDER BY ts_recorded
    """).fetchall()

    data = [["Datum", "Speler", "Tegenstander", "Type", "Car", "Avg", "Punten"]]

    for r in rows:
        data.append([
            r["ts_recorded"],
            r["player"],
            r["opponent"],
            r["game_type"],
            r["total"],
            round(r["avg"], 3),
            r["points"]
        ])

    table = Table(data)

    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.grey),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("GRID", (0,0), (-1,-1), 0.5, colors.black),
        ("ALIGN", (4,1), (-1,-1), "RIGHT"),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 20))

    # =========================================
    # RANKING LIBRE
    # =========================================
    elements.append(Paragraph("Ranking Libre", styles["Heading2"]))

    players = conn.execute("SELECT name FROM players").fetchall()

    data = [["Speler", "Caramboles", "Beurten", "Moyenne", "Punten"]]

    for p in players:
        name = p["name"]

        r = conn.execute("""
            SELECT SUM(total) as car, SUM(turns) as turns, SUM(points) as pts
            FROM results
            WHERE player=? AND game_type='libre'
        """, (name,)).fetchone()

        car = r["car"] or 0
        turns = r["turns"] or 0
        pts = r["pts"] or 0

        avg = (car / turns) if turns else 0

        data.append([
            name,
            car,
            turns,
            round(avg, 3),
            pts
        ])

    table = Table(data)

    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.darkblue),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("GRID", (0,0), (-1,-1), 0.5, colors.black),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 20))

    # =========================================
    # RANKING BAND
    # =========================================
    elements.append(Paragraph("Ranking Band", styles["Heading2"]))

    data = [["Speler", "Caramboles", "Beurten", "Moyenne", "Punten"]]

    for p in players:
        name = p["name"]

        r = conn.execute("""
            SELECT SUM(total) as car, SUM(turns) as turns, SUM(points) as pts
            FROM results
            WHERE player=? AND game_type='band'
        """, (name,)).fetchone()

        car = r["car"] or 0
        turns = r["turns"] or 0
        pts = r["pts"] or 0

        avg = (car / turns) if turns else 0

        data.append([
            name,
            car,
            turns,
            round(avg, 3),
            pts
        ])

    table = Table(data)

    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.darkgreen),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("GRID", (0,0), (-1,-1), 0.5, colors.black),
    ]))

    elements.append(table)

    doc.build(elements)

    # =========================================
    # BACKUP
    # =========================================
    backup_path = os.path.join(BACKUP_DIR, f"biljart_{timestamp}.db")
    shutil.copy(DB_PATH, backup_path)

    # =========================================
    # MOYENNES BIJWERKEN
    # =========================================
    for p in players:
        name = p["name"]

        libre = conn.execute("""
            SELECT SUM(total) as car, SUM(turns) as turns
            FROM results WHERE player=? AND game_type='libre'
        """, (name,)).fetchone()

        band = conn.execute("""
            SELECT SUM(total) as car, SUM(turns) as turns
            FROM results WHERE player=? AND game_type='band'
        """, (name,)).fetchone()

        avg_libre = (libre["car"] / libre["turns"]) if libre["turns"] else 0.5
        avg_band  = (band["car"] / band["turns"]) if band["turns"] else 0.5

        conn.execute("""
            UPDATE players
            SET avg_libre=?, avg_band=?
            WHERE name=?
        """, (avg_libre, avg_band, name))

    # =========================================
    # PURGE
    # =========================================
    conn.execute("DELETE FROM results")
    conn.commit()

    return {"ok": True}

@main_bp.route("/report/generate", methods=["POST"])
def generate_report():

    conn = get_db()

    # NOTE:
# gebruikt nu centrale reports map

    global REPORT_DIR
    os.makedirs(REPORT_DIR, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    report_path = os.path.join(REPORT_DIR, f"rapport_{timestamp}.pdf")

    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer,
        Table, TableStyle
    )
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet

    doc = SimpleDocTemplate(report_path)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("Tussenrapport", styles["Title"]))
    elements.append(Spacer(1, 10))

    # =========================================
    # HISTORIE
    # =========================================
    elements.append(Paragraph("Historie", styles["Heading2"]))

    rows = conn.execute("""
        SELECT ts_recorded, player, opponent, total, avg, points, game_type
        FROM results
        ORDER BY ts_recorded
    """).fetchall()

    data = [["Datum", "Speler", "Tegenstander", "Type", "Car", "Avg", "Punten"]]

    for r in rows:
        data.append([
            r["ts_recorded"],
            r["player"],
            r["opponent"],
            r["game_type"],
            r["total"],
            round(r["avg"], 3),
            r["points"]
        ])

    table = Table(data)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.grey),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("GRID", (0,0), (-1,-1), 0.5, colors.black),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 20))

    # =========================================
    # RANKING
    # =========================================
    players = conn.execute("SELECT name FROM players").fetchall()

    for game in ["libre", "band"]:

        elements.append(Paragraph(f"Ranking {game.capitalize()}", styles["Heading2"]))

        data = [["Speler", "Caramboles", "Beurten", "Moyenne", "Punten"]]

        for p in players:
            name = p["name"]

            r = conn.execute("""
                SELECT SUM(total) as car, SUM(turns) as turns, SUM(points) as pts
                FROM results
                WHERE player=? AND game_type=?
            """, (name, game)).fetchone()

            car = r["car"] or 0
            turns = r["turns"] or 0
            pts = r["pts"] or 0
            avg = (car / turns) if turns else 0

            data.append([name, car, turns, round(avg,3), pts])

        table = Table(data)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.darkblue),
            ("TEXTCOLOR", (0,0), (-1,0), colors.white),
            ("GRID", (0,0), (-1,-1), 0.5, colors.black),
        ]))

        elements.append(table)
        elements.append(Spacer(1, 20))

    doc.build(elements)

    return {"ok": True}

# =============
# HELP PAGINA
# ============

@main_bp.route("/help")
def help_page():
    return render_template("help.html")

# =========================================
# SHUTDOWN SERVER
# =========================================

@main_bp.route("/shutdown", methods=["POST"])
def shutdown_server():

    def stop():
        os._exit(0)

    threading.Timer(1, stop).start()

    return {"ok": True}