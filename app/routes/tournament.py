import itertools
import math
import os
from datetime import datetime

from flask import Blueprint, render_template, request

from app.database import get_db
from app.paths import REPORT_DIR
from app.auth import coordinator_required

tournament_bp = Blueprint("tournament", __name__)

GAME_TYPES = ("libre", "band")


def group_count(player_count):
    if player_count <= 5:
        return 1
    if player_count <= 8:
        return 2
    if player_count <= 12:
        return 3
    return 4


def get_seed_avg(conn, player, game_type):
    """Huidig seizoensmoyenne, of het startmoyenne als er nog geen resultaten zijn."""
    row = conn.execute("""
        SELECT SUM(total) AS pts, SUM(turns) AS trn
        FROM results
        WHERE player=? AND game_type=?
    """, (player, game_type)).fetchone()

    if row and row["trn"]:
        return row["pts"] / row["trn"]

    prow = conn.execute(
        "SELECT avg_libre, avg_band FROM players WHERE name=?",
        (player,)
    ).fetchone()

    if not prow:
        return 0.5

    avg = prow["avg_libre"] if game_type == "libre" else prow["avg_band"]
    return avg or 0.5


def compute_result(seed_avg1, seed_avg2, caramboles1, caramboles2,
                    turn_reached1, turn_reached2, turns_played):

    if turn_reached1 is not None and turn_reached2 is None:
        winner = "player1"
    elif turn_reached2 is not None and turn_reached1 is None:
        winner = "player2"
    elif turn_reached1 is not None and turn_reached2 is not None:
        if turn_reached1 < turn_reached2:
            winner = "player1"
        elif turn_reached2 < turn_reached1:
            winner = "player2"
        else:
            winner = "draw"
    else:
        match_avg1 = caramboles1 / turns_played if turns_played else 0
        match_avg2 = caramboles2 / turns_played if turns_played else 0

        quotient1 = (match_avg1 / seed_avg1) if seed_avg1 else 0
        quotient2 = (match_avg2 / seed_avg2) if seed_avg2 else 0

        if quotient1 > quotient2:
            winner = "player1"
        elif quotient2 > quotient1:
            winner = "player2"
        else:
            winner = "draw"

    if winner == "draw":
        return winner, 0.5, 0.5
    if winner == "player1":
        return winner, 1, 0
    return winner, 0, 1


def group_standings(conn, tournament_id, group_no):
    rows = conn.execute("""
        SELECT player1, player2, points1, points2, status
        FROM tournament_matches
        WHERE tournament_id=? AND group_no=?
    """, (tournament_id, group_no)).fetchall()

    players = sorted({r["player1"] for r in rows} | {r["player2"] for r in rows})

    seed_avgs = {}
    for row in conn.execute(
        "SELECT player, seed_avg FROM tournament_players WHERE tournament_id=?",
        (tournament_id,)
    ).fetchall():
        seed_avgs[row["player"]] = row["seed_avg"]

    points = {p: 0 for p in players}
    weerstand = {p: 0 for p in players}

    for row in rows:
        if row["status"] == "done":
            points[row["player1"]] += row["points1"]
            points[row["player2"]] += row["points2"]

    for player in players:
        for opponent in players:
            if opponent != player:
                weerstand[player] += seed_avgs.get(opponent, 0)

    standings = [
        {
            "player": p,
            "points": points[p],
            "weerstand": round(weerstand[p], 3),
            "seed_avg": round(seed_avgs.get(p, 0), 3)
        }
        for p in players
    ]

    standings.sort(key=lambda s: (s["points"], s["weerstand"]), reverse=True)

    return standings


def matches_for_group(conn, tournament_id, group_no):
    rows = conn.execute("""
        SELECT * FROM tournament_matches
        WHERE tournament_id=? AND group_no=?
        ORDER BY id
    """, (tournament_id, group_no)).fetchall()
    return [dict(r) for r in rows]


def tournament_group_count(conn, tournament_id):
    player_count = conn.execute(
        "SELECT COUNT(*) AS cnt FROM tournament_players WHERE tournament_id=?",
        (tournament_id,)
    ).fetchone()["cnt"]
    return group_count(player_count)


def tournament_averages(conn, tournament_id):
    totals = {}
    matches = conn.execute("""
        SELECT player1, player2, caramboles1, caramboles2, turns_played
        FROM tournament_matches
        WHERE tournament_id=? AND status='done'
    """, (tournament_id,)).fetchall()

    for match in matches:
        turns = match["turns_played"] or 0
        for player, caramboles in (
            (match["player1"], match["caramboles1"]),
            (match["player2"], match["caramboles2"]),
        ):
            total = totals.setdefault(player, {"caramboles": 0, "turns": 0})
            total["caramboles"] += caramboles or 0
            total["turns"] += turns

    return {
        player: round(total["caramboles"] / total["turns"], 3)
        if total["turns"] else 0
        for player, total in totals.items()
    }


def create_group_matches(conn, tournament_id, group_no, players, seed_avgs, max_turns):
    for p1, p2 in itertools.combinations(players, 2):
        target1 = int(seed_avgs[p1] * max_turns)
        target2 = int(seed_avgs[p2] * max_turns)

        conn.execute("""
            INSERT INTO tournament_matches
            (tournament_id, group_no, player1, player2, target1, target2, status)
            VALUES (?, ?, ?, ?, ?, ?, 'pending')
        """, (tournament_id, group_no, p1, p2, target1, target2))


def generate_tournament_report(conn, tournament_id):
    """PDF-rapport van een afgesloten tournooi, opgeslagen in de Rapporten-map."""
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    )
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet

    trow = conn.execute(
        "SELECT * FROM tournaments WHERE id=?", (tournament_id,)
    ).fetchone()

    os.makedirs(REPORT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    report_path = os.path.join(
        REPORT_DIR, f"tournooi_{tournament_id}_{timestamp}.pdf"
    )

    doc = SimpleDocTemplate(report_path)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph(f"Tournooi Rapport - {trow['name']}", styles["Title"]))
    elements.append(Paragraph(
        f"Soort: {trow['game_type']} | Max. beurten: {trow['max_turns']}",
        styles["Normal"]
    ))
    elements.append(Spacer(1, 10))

    averages = tournament_averages(conn, tournament_id)

    def add_group(title, group_no):
        elements.append(Paragraph(title, styles["Heading2"]))

        standings = group_standings(conn, tournament_id, group_no)
        data = [["Speler", "Punten", "Weerstand", "Tournooi moyenne"]]
        for s in standings:
            data.append([
                s["player"], s["points"], s["weerstand"],
                averages.get(s["player"], 0)
            ])

        table = Table(data)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 10))

        data = [["Speler 1", "Car.", "Speler 2", "Car.", "Winnaar"]]
        for m in matches_for_group(conn, tournament_id, group_no):
            uitslag = "gelijk" if m["winner"] == "draw" else (
                m["player1"] if m["winner"] == "player1" else m["player2"]
            )
            data.append([
                m["player1"], m["caramboles1"],
                m["player2"], m["caramboles2"],
                uitslag
            ])

        table = Table(data)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 20))

    for group_no in range(1, tournament_group_count(conn, tournament_id) + 1):
        add_group(f"Groep {group_no}", group_no)

    if matches_for_group(conn, tournament_id, 0):
        add_group("Finale", 0)

    final_standings = group_standings(conn, tournament_id, 0)
    if final_standings:
        champion = final_standings[0]["player"]
    else:
        champion = group_standings(conn, tournament_id, 1)[0]["player"]
    elements.append(Paragraph(f"Tournooiwinnaar: {champion}", styles["Heading1"]))

    doc.build(elements)

    return os.path.basename(report_path)


@tournament_bp.route("/tournament")
@coordinator_required
def tournament_page():
    conn = get_db()

    players = [r["name"] for r in conn.execute(
        "SELECT name FROM players ORDER BY name"
    ).fetchall()]

    tournaments = conn.execute("""
        SELECT id, name, game_type, max_turns, status, created_at
        FROM tournaments
        ORDER BY id DESC
    """).fetchall()

    return render_template(
        "tournament.html",
        players=players,
        tournaments=[dict(t) for t in tournaments]
    )


@tournament_bp.route("/tournament/help")
@coordinator_required
def tournament_help():
    return render_template("tournament_help.html")


@tournament_bp.route("/tournament/create", methods=["POST"])
@coordinator_required
def create_tournament():
    data = request.json or {}

    name = (data.get("name") or "").strip()
    game_type = data.get("game_type")
    max_turns = data.get("max_turns")
    players = data.get("players") or []

    if not name:
        return {"error": "naam ontbreekt"}, 400

    if game_type not in GAME_TYPES:
        return {"error": "kies libre of band"}, 400

    if (
        isinstance(max_turns, bool)
        or not isinstance(max_turns, (int, float))
        or not math.isfinite(max_turns)
        or max_turns <= 0
        or max_turns != int(max_turns)
    ):
        return {"error": "beurten moet een positief geheel getal zijn"}, 400

    max_turns = int(max_turns)

    players = list(dict.fromkeys(players))
    if len(players) < 3 or len(players) > 20:
        return {"error": "kies minimaal 3 en maximaal 20 spelers"}, 400

    conn = get_db()

    seed_avgs = {p: get_seed_avg(conn, p, game_type) for p in players}
    players_sorted = sorted(players, key=lambda p: seed_avgs[p], reverse=True)

    cur = conn.execute("""
        INSERT INTO tournaments (name, game_type, max_turns, status, created_at)
        VALUES (?, ?, ?, 'groups', ?)
    """, (name, game_type, max_turns, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

    tournament_id = cur.lastrowid

    number_of_groups = group_count(len(players_sorted))
    groups = {group_no: [] for group_no in range(1, number_of_groups + 1)}

    for i, player in enumerate(players_sorted):
        group_no = (i % number_of_groups) + 1
        groups[group_no].append(player)

        conn.execute("""
            INSERT INTO tournament_players (tournament_id, player, seed_avg, group_no)
            VALUES (?, ?, ?, ?)
        """, (tournament_id, player, seed_avgs[player], group_no))

    for group_no, group_players in groups.items():
        create_group_matches(
            conn, tournament_id, group_no, group_players, seed_avgs, max_turns
        )

    conn.commit()

    return {"ok": True, "id": tournament_id}


@tournament_bp.route("/tournament/<int:tournament_id>/data")
@coordinator_required
def tournament_data(tournament_id):
    conn = get_db()

    trow = conn.execute(
        "SELECT * FROM tournaments WHERE id=?", (tournament_id,)
    ).fetchone()

    if not trow:
        return {"error": "tournooi niet gevonden"}, 404

    groups = {}
    for group_no in range(1, tournament_group_count(conn, tournament_id) + 1):
        groups[group_no] = {
            "standings": group_standings(conn, tournament_id, group_no),
            "matches": matches_for_group(conn, tournament_id, group_no)
        }

    final = None
    final_matches = matches_for_group(conn, tournament_id, 0)
    if final_matches:
        final = {
            "standings": group_standings(conn, tournament_id, 0),
            "matches": final_matches
        }

    champion = None
    report_file = None
    if trow["status"] == "done" and final:
        champion = final["standings"][0]["player"]
        reports = sorted(
            (f for f in os.listdir(REPORT_DIR) if f.startswith(f"tournooi_{tournament_id}_")),
            reverse=True
        )
        report_file = reports[0] if reports else None

    return {
        "tournament": dict(trow),
        "groups": groups,
        "final": final,
        "champion": champion,
        "report": report_file
    }


@tournament_bp.route("/tournament/<int:tournament_id>/result", methods=["POST"])
@coordinator_required
def tournament_result(tournament_id):
    data = request.json or {}

    match_id = data.get("match_id")

    conn = get_db()

    match = conn.execute(
        "SELECT * FROM tournament_matches WHERE id=? AND tournament_id=?",
        (match_id, tournament_id)
    ).fetchone()

    if not match:
        return {"error": "wedstrijd niet gevonden"}, 404

    if match["status"] == "done":
        return {"error": "resultaat al verwerkt"}, 400

    trow = conn.execute(
        "SELECT * FROM tournaments WHERE id=?", (tournament_id,)
    ).fetchone()

    try:
        caramboles1 = int(data.get("caramboles1", 0))
        caramboles2 = int(data.get("caramboles2", 0))
        turns_played = int(data.get("turns_played") or trow["max_turns"])
    except (TypeError, ValueError):
        return {"error": "ongeldige invoer"}, 400

    if caramboles1 < 0 or caramboles2 < 0 or turns_played <= 0:
        return {"error": "waarden moeten 0 of positief zijn"}, 400

    if turns_played > trow["max_turns"]:
        return {"error": "gespeelde beurten mogen niet hoger zijn dan het maximum"}, 400

    turn_reached1 = data.get("turn_reached1")
    turn_reached2 = data.get("turn_reached2")

    turn_reached1 = int(turn_reached1) if turn_reached1 not in (None, "") else None
    turn_reached2 = int(turn_reached2) if turn_reached2 not in (None, "") else None

    if turn_reached1 is None and turn_reached2 is None and turns_played < trow["max_turns"]:
        return {
            "error": "Als beide spelers niet hun target hebben gehaald moet het aantal beurten gelijk zijn aan het maximum aantal beurten."
        }, 400

    seed_row1 = conn.execute(
        "SELECT seed_avg FROM tournament_players WHERE tournament_id=? AND player=?",
        (tournament_id, match["player1"])
    ).fetchone()
    seed_row2 = conn.execute(
        "SELECT seed_avg FROM tournament_players WHERE tournament_id=? AND player=?",
        (tournament_id, match["player2"])
    ).fetchone()

    seed_avg1 = seed_row1["seed_avg"] if seed_row1 else (match["target1"] / trow["max_turns"] if trow["max_turns"] else 0)
    seed_avg2 = seed_row2["seed_avg"] if seed_row2 else (match["target2"] / trow["max_turns"] if trow["max_turns"] else 0)

    winner, points1, points2 = compute_result(
        seed_avg1, seed_avg2, caramboles1, caramboles2,
        turn_reached1, turn_reached2, turns_played
    )

    conn.execute("""
        UPDATE tournament_matches
        SET caramboles1=?, caramboles2=?, turn_reached1=?, turn_reached2=?,
            turns_played=?, points1=?, points2=?, winner=?, status='done'
        WHERE id=?
    """, (
        caramboles1, caramboles2, turn_reached1, turn_reached2,
        turns_played, points1, points2, winner, match_id
    ))

    conn.commit()

    return {"ok": True}


@tournament_bp.route("/tournament/<int:tournament_id>/final", methods=["POST"])
@coordinator_required
def tournament_final(tournament_id):
    conn = get_db()

    trow = conn.execute(
        "SELECT * FROM tournaments WHERE id=?", (tournament_id,)
    ).fetchone()

    if not trow:
        return {"error": "tournooi niet gevonden"}, 404

    existing_final = conn.execute(
        "SELECT COUNT(*) AS cnt FROM tournament_matches WHERE tournament_id=? AND group_no=0",
        (tournament_id,)
    ).fetchone()["cnt"]

    if existing_final:
        return {"error": "finalegroep bestaat al"}, 400

    number_of_groups = tournament_group_count(conn, tournament_id)
    if number_of_groups == 1:
        return {"error": "bij één groep is geen finale nodig"}, 400

    winners = []
    seed_avgs = {}

    for group_no in range(1, number_of_groups + 1):
        matches = matches_for_group(conn, tournament_id, group_no)
        if not matches or any(m["status"] != "done" for m in matches):
            return {"error": f"groep {group_no} is nog niet volledig gespeeld"}, 400

        standings = group_standings(conn, tournament_id, group_no)
        winner = standings[0]["player"]
        winners.append(winner)
        seed_avgs[winner] = standings[0]["seed_avg"]

    create_group_matches(conn, tournament_id, 0, winners, seed_avgs, trow["max_turns"])

    conn.execute("UPDATE tournaments SET status='final' WHERE id=?", (tournament_id,))
    conn.commit()

    return {"ok": True, "winners": winners}


@tournament_bp.route("/tournament/<int:tournament_id>/finish", methods=["POST"])
@coordinator_required
def tournament_finish(tournament_id):
    conn = get_db()

    final_matches = matches_for_group(conn, tournament_id, 0)

    if final_matches:
        if any(m["status"] != "done" for m in final_matches):
            return {"error": "finale is nog niet volledig gespeeld"}, 400
    else:
        number_of_groups = tournament_group_count(conn, tournament_id)
        group_matches = matches_for_group(conn, tournament_id, 1)
        if number_of_groups != 1 or not group_matches or any(
            m["status"] != "done" for m in group_matches
        ):
            return {"error": "de groepsfase is nog niet volledig gespeeld"}, 400

    conn.execute("UPDATE tournaments SET status='done' WHERE id=?", (tournament_id,))
    conn.commit()

    standings = group_standings(conn, tournament_id, 0 if final_matches else 1)
    report_file = generate_tournament_report(conn, tournament_id)

    return {"ok": True, "champion": standings[0]["player"], "report": report_file}


@tournament_bp.route("/tournament/<int:tournament_id>/delete", methods=["POST"])
@coordinator_required
def tournament_delete(tournament_id):
    conn = get_db()

    conn.execute("DELETE FROM tournament_matches WHERE tournament_id=?", (tournament_id,))
    conn.execute("DELETE FROM tournament_players WHERE tournament_id=?", (tournament_id,))
    conn.execute("DELETE FROM tournaments WHERE id=?", (tournament_id,))

    conn.commit()

    return {"ok": True}
