from flask import Blueprint, request
from app.database import get_db
import uuid
import random
from datetime import datetime

matches_bp = Blueprint("matches", __name__)

ACTIVE_MATCHES = {}

PENDING_RESULTS = {}

def get_max_turns(conn):
    row = conn.execute(
        "SELECT value FROM settings WHERE key='max_turns'"
    ).fetchone()
    return int(row["value"]) if row else 20


# =============================
# CREATE MATCHES
# =============================
@matches_bp.route("/matches/create", methods=["POST"])
def create_matches():

    data = request.json
    players = data.get("players", [])

    conn = get_db()
    turns = get_max_turns(conn)

    random.shuffle(players)
    ACTIVE_MATCHES.clear()

    unmatched = None

    best_pairs = []
    best_unmatched = players[:]

    # ==========================================
    # HISTORIE OPHALEN
    # ==========================================
    history = {}

    rows = conn.execute("""
        SELECT player, opponent, COUNT(*) as cnt
        FROM results
        GROUP BY player, opponent
    """).fetchall()

    for r in rows:
        key = tuple(sorted([r["player"], r["opponent"]]))

        history[key] = r["cnt"]//2

    # ==========================================
    # 50 POGINGEN
    # ==========================================
    for _ in range(50):

        pool = players[:]
        random.shuffle(pool)

        pairs = []
        unmatched_local = []

        while len(pool) > 1:

            p1 = pool.pop(0)

            found = False

            for i, p2 in enumerate(pool):

                key = tuple(sorted([p1, p2]))

                played = history.get(key, 0)

                if played < 2:

                    pairs.append((p1, p2))

                    pool.pop(i)

                    found = True
                    break

            if not found:
                unmatched_local.append(p1)

        # laatste speler over
        if pool:
            unmatched_local.append(pool.pop())

        # beste resultaat bewaren
        if len(unmatched_local) < len(best_unmatched):

            best_pairs = pairs
            best_unmatched = unmatched_local

            # perfecte oplossing gevonden
            if len(best_unmatched) <= 1:
                break

    # ==========================================
    # MATCHES MAKEN
    # ==========================================
    unmatched = best_unmatched

    for p1, p2 in best_pairs:

        row1 = conn.execute(
            "SELECT avg_libre, avg_band FROM players WHERE name=?",
            (p1,)
        ).fetchone()

        row2 = conn.execute(
            "SELECT avg_libre, avg_band FROM players WHERE name=?",
            (p2,)
        ).fetchone()

        for game_type in ["libre", "band"]:

            start1 = row1["avg_libre"] if game_type=="libre" else row1["avg_band"]
            start2 = row2["avg_libre"] if game_type=="libre" else row2["avg_band"]

            start1 = start1 or 0.5
            start2 = start2 or 0.5

            target1 = int(start1 * turns)
            target2 = int(start2 * turns)

            match_id = str(uuid.uuid4())

            ACTIVE_MATCHES[match_id] = {
                "id": match_id,
                "player1": p1,
                "player2": p2,
                "game_type": game_type,
                "status": "ready",
                "claimed_by": None,
                "target1": target1,
                "target2": target2,
                "start_avg1": start1,
                "start_avg2": start2,
                "turns": turns
            }

    return {"ok": True, "unmatched": unmatched}

# =============================
# CREATE MANUAL MATCH
# =============================
@matches_bp.route("/matches/manual", methods=["POST"])
def create_manual_match():

    data = request.json

    p1 = data.get("player1")
    p2 = data.get("player2")
    game_type = data.get("game_type")

    if not p1 or not p2:
        return {"error": "spelers ontbreken"}

    if p1 == p2:
        return {"error": "zelfde speler gekozen"}

    conn = get_db()

    turns = get_max_turns(conn)

    row1 = conn.execute(
        "SELECT avg_libre, avg_band FROM players WHERE name=?",
        (p1,)
    ).fetchone()

    row2 = conn.execute(
        "SELECT avg_libre, avg_band FROM players WHERE name=?",
        (p2,)
    ).fetchone()

    start1 = row1["avg_libre"] if game_type == "libre" else row1["avg_band"]
    start2 = row2["avg_libre"] if game_type == "libre" else row2["avg_band"]

    start1 = start1 or 0.5
    start2 = start2 or 0.5

    target1 = int(start1 * turns)
    target2 = int(start2 * turns)

    match_id = str(uuid.uuid4())

    ACTIVE_MATCHES[match_id] = {
        "id": match_id,
        "player1": p1,
        "player2": p2,
        "game_type": game_type,
        "status": "ready",
        "claimed_by": None,
        "target1": target1,
        "target2": target2,
        "start_avg1": start1,
        "start_avg2": start2,
        "turns": turns
    }

    return {"ok": True}


@matches_bp.route("/manual/result", methods=["POST"])
def manual_result():

    data = request.json

    match_id = data["match_id"]

    m = ACTIVE_MATCHES.get(match_id)

    if not m:
        return {"error": "match niet gevonden"}

    total1 = data.get("total1", 0)
    total2 = data.get("total2", 0)
    turns = data.get("turns", 1)

    p1 = m["player1"]
    p2 = m["player2"]
    game = m["game_type"]

    start1 = m["start_avg1"]
    start2 = m["start_avg2"]

    target1 = int(start1 * turns)
    target2 = int(start2 * turns)

    avg1 = total1 / turns if turns else 0
    avg2 = total2 / turns if turns else 0

    base1 = min(round((avg1 / start1) * 10), 10) if start1 else 0
    base2 = min(round((avg2 / start2) * 10), 10) if start2 else 0

    if total1 >= target1 and total2 < target2:
        winner = p1
    elif total2 >= target2 and total1 < target1:
        winner = p2
    else:
        winner = p1 if base1 > base2 else p2 if base2 > base1 else "draw"

    bonus1 = 2 if winner == p1 else (1 if winner == "draw" else 0)
    bonus2 = 2 if winner == p2 else (1 if winner == "draw" else 0)

    points1 = base1 + bonus1
    points2 = base2 + bonus2

    PENDING_RESULTS[match_id] = {
        "match_id": match_id,
        "player1": p1,
        "player2": p2,
        "game_type": game,
        "total1": total1,
        "total2": total2,
        "turns": turns,
        "avg1": avg1,
        "avg2": avg2,
        "points1": points1,
        "points2": points2,
        "winner": winner,
        "start1": start1,
        "start2": start2
    }

    m["status"] = "pending"

    return {"ok": True}

# =============================
# CLAIM MATCH
# =============================
@matches_bp.route("/match/claim", methods=["POST"])
def claim_match():

    match_id = request.json["match_id"]
    m = ACTIVE_MATCHES.get(match_id)

    if not m:
        return {"error": "niet gevonden"}

    if m["status"] != "ready":
        return {"error": "al bezet"}

    m["status"] = "busy"
    claim_token = str(uuid.uuid4())

    m["claimed_by"] = claim_token

    return {
        "ok": True,
        "token": claim_token
    }

    return {"ok": True}


# =============================
# FINISH MATCH
# =============================
@matches_bp.route("/match/finish", methods=["POST"])
def finish_match():

    data = request.json
    match_id = data["match_id"]

    m = ACTIVE_MATCHES.get(match_id)

    if not m:
        return {"error": "niet gevonden"}

    # 🔥 ALLEEN CLAIMER MAG AFSLUITEN
    if m.get("claimed_by") != data.get("claim_token"):
        return {"error": "niet jouw match"}

    if m["status"] == "finished":
        return {"error": "al klaar"}

    total1 = data.get("total1", 0)
    total2 = data.get("total2", 0)
    turns = data.get("turns") or 1

    p1 = m["player1"]
    p2 = m["player2"]
    game = m["game_type"]

    start1 = m["start_avg1"]
    start2 = m["start_avg2"]

    target1 = int(start1 * turns)
    target2 = int(start2 * turns)

    avg1 = total1 / turns if turns else 0
    avg2 = total2 / turns if turns else 0

    base1 = min(round((avg1 / start1) * 10), 10) if start1 else 0
    base2 = min(round((avg2 / start2) * 10), 10) if start2 else 0

    if total1 >= target1 and total2 < target2:
        winner = p1
    elif total2 >= target2 and total1 < target1:
        winner = p2
    else:
        winner = p1 if base1 > base2 else p2 if base2 > base1 else "draw"

    bonus1 = 2 if winner == p1 else (1 if winner == "draw" else 0)
    bonus2 = 2 if winner == p2 else (1 if winner == "draw" else 0)

    points1 = base1 + bonus1
    points2 = base2 + bonus2

    m["status"] = "finished"
    m["winner"] = winner

    PENDING_RESULTS[match_id] = {
        "match_id": match_id,
        "player1": p1,
        "player2": p2,
        "game_type": game,
        "total1": total1,
        "total2": total2,
        "turns": turns,
        "avg1": avg1,
        "avg2": avg2,
        "points1": points1,
        "points2": points2,
        "winner": winner,
        "start1": start1,
        "start2": start2
    }

    m["status"] = "pending"

    return {"ok": True}