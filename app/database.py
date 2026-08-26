import os
import sqlite3
import json
from flask import g, has_app_context

from app.paths import (
    BACKUP_DIR,
    DB_PATH,
    REPORT_DIR,
    INSTANCE_DIR
)


def get_db():

    conn = sqlite3.connect(DB_PATH)

    conn.row_factory = sqlite3.Row

    if has_app_context():
        g.setdefault("_db_connections", []).append(conn)

    return conn


def close_db_connections(exception=None):
    for conn in g.pop("_db_connections", []):
        try:
            conn.close()
        except sqlite3.ProgrammingError:
            pass


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

    # tournooien
    conn.execute("""
    CREATE TABLE IF NOT EXISTS tournaments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        game_type TEXT NOT NULL,
        max_turns INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'groups',
        created_at TEXT
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS tournament_players (
        tournament_id INTEGER NOT NULL,
        player TEXT NOT NULL,
        seed_avg REAL NOT NULL,
        group_no INTEGER NOT NULL,
        PRIMARY KEY (tournament_id, player)
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS tournament_matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tournament_id INTEGER NOT NULL,
        group_no INTEGER NOT NULL,
        player1 TEXT NOT NULL,
        player2 TEXT NOT NULL,
        target1 INTEGER,
        target2 INTEGER,
        turns_played INTEGER,
        caramboles1 INTEGER,
        caramboles2 INTEGER,
        turn_reached1 INTEGER,
        turn_reached2 INTEGER,
        points1 REAL,
        points2 REAL,
        winner TEXT,
        status TEXT NOT NULL DEFAULT 'pending'
    )
    """)

    conn.commit()

    conn.close()