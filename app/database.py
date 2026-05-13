import sqlite3
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# 🔥 database nu correct in instance/
DB_PATH = os.path.join(BASE_DIR, "instance", "biljart.db")


def get_db():

    conn = sqlite3.connect(DB_PATH)

    conn.row_factory = sqlite3.Row

    return conn


# =========================================
# INIT DATABASE
# =========================================
def init_db():

    os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)

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
        start_avg REAL
    )
    """)

    # settings
    conn.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    conn.commit()

    conn.close()