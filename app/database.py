import os
import sys
import sqlite3
import pathlib
import json

BASE_DIR = "/var/lib/biljartclub"

INSTANCE_DIR = os.path.join(BASE_DIR, "instance")

os.makedirs(INSTANCE_DIR, exist_ok=True)

DB_PATH = os.path.join(INSTANCE_DIR, "biljart.db")
BACKUP_DIR = os.path.join(BASE_DIR, "backups")
REPORT_DIR = os.path.join(BASE_DIR, "reports")

os.makedirs(BACKUP_DIR, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)


def get_db():

    conn = sqlite3.connect(DB_PATH)

    conn.row_factory = sqlite3.Row

    return conn


def save_pending_result(result):
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO pending_results (match_id, payload) VALUES (?, ?)",
        (result["match_id"], json.dumps(result))
    )
    conn.commit()
    conn.close()


def load_pending_results():
    conn = get_db()
    rows = conn.execute(
        "SELECT payload FROM pending_results"
    ).fetchall()
    conn.close()
    return [json.loads(row["payload"]) for row in rows]


def delete_pending_result(match_id):
    conn = get_db()
    conn.execute(
        "DELETE FROM pending_results WHERE match_id=?",
        (match_id,)
    )
    conn.commit()
    conn.close()


# =========================================
# INIT DATABASE
# =========================================
def init_db():


    conn = get_db()

    # spelers
    conn.execute("""
    CREATE TABLE IF NOT EXISTS players (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        avg_libre REAL DEFAULT 0.5,
        avg_band REAL DEFAULT 0.5
    )
    """)

    # resultaten
    conn.execute("""
    CREATE TABLE IF NOT EXISTS results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        match_id TEXT,
        player TEXT,
        opponent TEXT,
        total INTEGER,
        game_type TEXT,
        ts_recorded TEXT,
        points INTEGER,
        result TEXT,
        avg REAL,
        turns INTEGER,
        start_avg REAL,
        high_run INTEGER DEFAULT 0
    )
    """)

    # settings
    conn.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS pending_results (
        match_id TEXT PRIMARY KEY,
        payload TEXT NOT NULL
    )
    """)

    conn.commit()

    conn.close()