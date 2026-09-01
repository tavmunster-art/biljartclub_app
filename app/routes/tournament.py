import itertools
import hashlib
import math
import os
import random
from datetime import datetime

from flask import Blueprint, render_template, request

from app.database import get_db
from app.paths import REPORT_DIR
from app.auth import coordinator_required

tournament_bp = Blueprint("tournament", __name__)

GAME_TYPES = ("libre", "band")
BYE_MARKER = "(vrijloting)"
MIN_MAX_TURNS = 10  # onder dit aantal beurten is een partij te kort; dan naar knock-out uitwijken


def group_count(player_count):
    if player_count <= 5:
        return 1
    if player_count <= 8:
        return 2
    if player_count <= 12:
        return 3
    return 4


def group_sizes(player_count, groups):
    """Groepsindeling zoals bij het aanmaken van een tournooi (max 1 speler verschil per groep)."""
    base, rem = divmod(player_count, groups)
    return [base + 1 if i < rem else base for i in range(groups)]


def critical_path_matches(player_count, groups, num_tables):
    """Langste keten van wedstrijden op één tafel voor een gegeven aantal groepen."""
    sizes = group_sizes(player_count, groups)
    matches = [math.comb(size, 2) for size in sizes]

    # Groepsfase: bij voldoende tafels speelt elke groep op zijn eigen tafel,
    # dus het langste pad is de grootste groep. Zijn er minder tafels dan
    # groepen, dan draaien er meerdere volledige groepen na elkaar op één
    # tafel (een groep kan niet over tafels gesplitst worden).
    if num_tables >= groups:
        group_path = max(matches)
    else:
        groups_per_table = math.ceil(groups / num_tables)
        group_path = groups_per_table * max(matches)

    # Finaleronde: round-robin tussen de groepswinnaars. Met P finalisten
    # kunnen hoogstens P // 2 partijen tegelijk (geen speler dubbel op een tafel).
    final_matches = math.comb(groups, 2) if groups > 1 else 0
    if final_matches:
        final_tables = max(1, min(num_tables, groups // 2))
        final_path = math.ceil(final_matches / final_tables)
    else:
        final_path = 0

    return group_path + final_path, sum(matches) + final_matches


def optimal_group_count(player_count, num_tables):
    """Zoekt het aantal groepen (max. 1 per tafel) dat de tafels het beste benut,
    d.w.z. het kortste pad aan wedstrijden op de drukste tafel oplevert."""
    max_groups = max(1, min(num_tables, player_count // 2))

    best_groups = 1
    best_path = None
    for groups in range(1, max_groups + 1):
        path, _ = critical_path_matches(player_count, groups, num_tables)
        if best_path is None or path < best_path:
            best_path = path
            best_groups = groups

    return best_groups


MIN_GROUP_SIZE = 3  # kleinste groepsgrootte die nog als volwaardige groepsfase telt


def optimal_group_count_with_min_group_size(player_count, num_tables, min_group_size=MIN_GROUP_SIZE):
    """Zoals optimal_group_count, maar begrensd zodat elke groep minstens min_group_size
    spelers telt (nodig om te bepalen hoeveel speeltijd een volwaardig groepensysteem vergt)."""
    max_groups = max(1, min(num_tables, player_count // 2, player_count // min_group_size))

    best_groups = 1
    best_path = None
    for groups in range(1, max_groups + 1):
        path, _ = critical_path_matches(player_count, groups, num_tables)
        if best_path is None or path < best_path:
            best_path = path
            best_groups = groups

    return best_groups


def minutes_required_for_group_format(player_count, num_tables, avg_turn_seconds,
                                       min_turns=MIN_MAX_TURNS, min_group_size=MIN_GROUP_SIZE):
    """Minimaal aantal minuten om, met genoeg groepen van minstens min_group_size spelers,
    ook nog minstens min_turns beurten per partij te kunnen spelen. Dit is het alternatief
    voor een knock-outsysteem: dezelfde deelnemers en tafels, maar meer speeltijd
    (bijvoorbeeld verspreid over meerdere dagen of met extra tijd)."""
    groups = optimal_group_count_with_min_group_size(player_count, num_tables, min_group_size)
    group_path, _ = critical_path_matches(player_count, groups, num_tables)
    required_seconds = group_path * 2 * avg_turn_seconds * min_turns
    return groups, math.ceil(required_seconds / 60)


def knockout_plan(player_count, num_tables):
    """Kritiek pad + totaal aantal wedstrijden voor het knock-outsysteem: elke ronde
    halveert het deelnemersveld (fold-paring), tot er 2 of 3 spelers over zijn.
    Bij 3 over: round-robin. Bij 2 over: één finale wedstrijd."""
    remaining = player_count
    path = 0
    total_matches = 0

    while remaining > 3:
        pairs = remaining // 2
        bye = remaining % 2
        total_matches += pairs
        path += math.ceil(pairs / num_tables)
        remaining = pairs + bye

    if remaining == 3:
        total_matches += 3
        path += math.ceil(3 / max(1, min(num_tables, 1)))
    elif remaining == 2:
        total_matches += 1
        path += 1

    return path, total_matches


def estimate_max_turns(conn, players, game_type, duration_minutes, num_tables, avg_turn_seconds):
    """Conservatieve schatting: gaat ervan uit dat elke partij het volledige max. aantal beurten duurt."""
    seed_avgs = [get_seed_avg(conn, p, game_type) for p in players]
    avg_moyenne = sum(seed_avgs) / len(seed_avgs)

    player_count = len(players)
    total_seconds = duration_minutes * 60

    groups = optimal_group_count(player_count, num_tables)
    group_path, group_total_matches = critical_path_matches(player_count, groups, num_tables)
    group_max_turns = max(1, math.floor(total_seconds / (group_path * 2 * avg_turn_seconds)))

    if group_max_turns < MIN_MAX_TURNS:
        # partijen worden te kort voor een groepen/poulesysteem: minder wedstrijden
        # per tafel nodig via een knock-outsysteem, dat meer beurten per partij toelaat.
        ko_path, ko_total_matches = knockout_plan(player_count, num_tables)
        ko_max_turns = max(1, math.floor(total_seconds / (ko_path * 2 * avg_turn_seconds)))

        # alternatief: dezelfde deelnemers/tafels maar meer speeltijd, zodat een
        # groepensysteem (met groepen van minstens MIN_GROUP_SIZE spelers) toch haalbaar is.
        alt_group_count, alt_minutes_needed = minutes_required_for_group_format(
            player_count, num_tables, avg_turn_seconds
        )

        return {
            "avg_moyenne": round(avg_moyenne, 3),
            "format": "knockout",
            "group_count": None,
            "total_matches": ko_total_matches,
            "matches_per_table": ko_path,
            "recommended_max_turns": ko_max_turns,
            "alternative_group_count": alt_group_count,
            "alternative_minutes_needed": alt_minutes_needed
        }

    return {
        "avg_moyenne": round(avg_moyenne, 3),
        "format": "groups",
        "group_count": groups,
        "total_matches": group_total_matches,
        "matches_per_table": group_path,
        "recommended_max_turns": group_max_turns
    }


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


def is_round_robin_round(conn, tournament_id, round_no):
    """True als spelers in deze ronde meerdere partijen spelen (de round-robin finaleronde),
    False bij een knock-out-ronde (elke speler hoogstens één partij, bye niet meegerekend)."""
    counts = {}
    for m in matches_for_group(conn, tournament_id, round_no):
        if m["player2"] == BYE_MARKER:
            continue
        counts[m["player1"]] = counts.get(m["player1"], 0) + 1
        counts[m["player2"]] = counts.get(m["player2"], 0) + 1
    return any(c > 1 for c in counts.values())


def resolve_knockout_draw(conn, tournament_id, round_no, player1, player2, caramboles1, caramboles2, turns_played):
    """Gelijkspel is niet bruikbaar in een knock-outronde: eerst wint de hoogste partijmoyenne,
    dan de hoogste weerstand (het moyenne dat de tegenstander de vorige ronde had), en anders het lot."""
    match_avg1 = caramboles1 / turns_played if turns_played else 0
    match_avg2 = caramboles2 / turns_played if turns_played else 0

    if match_avg1 != match_avg2:
        return "player1" if match_avg1 > match_avg2 else "player2"

    seed_avgs = {
        row["player"]: row["seed_avg"]
        for row in conn.execute(
            "SELECT player, seed_avg FROM tournament_players WHERE tournament_id=?",
            (tournament_id,)
        ).fetchall()
    }
    previous_avgs = round_match_averages(conn, tournament_id, round_no - 1) if round_no > 1 else {}

    # weerstand van een speler = het moyenne van zijn tegenstander in de vorige ronde
    weerstand1 = previous_avgs.get(player2, seed_avgs.get(player2, 0))
    weerstand2 = previous_avgs.get(player1, seed_avgs.get(player1, 0))
    if weerstand1 != weerstand2:
        return "player1" if weerstand1 > weerstand2 else "player2"

    random1, random2 = random.random(), random.random()
    while random1 == random2:
        random1, random2 = random.random(), random.random()
    return "player1" if random1 > random2 else "player2"


def round_match_averages(conn, tournament_id, round_no):
    """Partijmoyenne per speler in deze ronde; bij meerdere partijen (round-robin finale)
    het gemiddelde van de moyennes van die partijen. Vrijlotingen tellen niet mee."""
    sums, counts = {}, {}
    for m in matches_for_group(conn, tournament_id, round_no):
        if m["status"] != "done" or m["player2"] == BYE_MARKER:
            continue
        for player, caramboles in ((m["player1"], m["caramboles1"]), (m["player2"], m["caramboles2"])):
            turns = m["turns_played"] or 0
            avg = (caramboles or 0) / turns if turns else 0
            sums[player] = sums.get(player, 0) + avg
            counts[player] = counts.get(player, 0) + 1
    return {p: sums[p] / counts[p] for p in sums}


def round_opponents(conn, tournament_id, round_no):
    """Per speler de tegenstander(s) waartegen in deze ronde daadwerkelijk is gespeeld (bye telt niet mee)."""
    opponents = {}
    for m in matches_for_group(conn, tournament_id, round_no):
        if m["player2"] == BYE_MARKER:
            continue
        opponents.setdefault(m["player1"], []).append(m["player2"])
        opponents.setdefault(m["player2"], []).append(m["player1"])
    return opponents


def _tiebreak_random(tournament_id, round_no, player):
    """Stabiel 'lot': altijd dezelfde uitkomst bij herladen, zodat de stand niet steeds wisselt."""
    digest = hashlib.sha256(f"{tournament_id}:{round_no}:{player}".encode()).hexdigest()
    return int(digest, 16)


def knockout_round_standings(conn, tournament_id, round_no):
    """Stand voor een knock-outronde. Moyenne = eigen partijmoyenne(s) in deze ronde.
    Weerstand in ronde 1 = som van de moyennes van alle andere spelers in het veld;
    vanaf ronde 2 = som van de moyennes die de daadwerkelijke tegenstanders van deze
    ronde de vorige ronde hadden. Bij gelijk eindigen (na punten en weerstand) beslissen
    moyenne en tenslotte het lot, zoals bij de knock-out-gelijkspelregels."""
    rows = matches_for_group(conn, tournament_id, round_no)
    players = sorted(({r["player1"] for r in rows} | {r["player2"] for r in rows}) - {BYE_MARKER})

    seed_avgs = {
        row["player"]: row["seed_avg"]
        for row in conn.execute(
            "SELECT player, seed_avg FROM tournament_players WHERE tournament_id=?",
            (tournament_id,)
        ).fetchall()
    }

    round_avgs = round_match_averages(conn, tournament_id, round_no)
    moyennes = {p: round_avgs.get(p, seed_avgs.get(p, 0)) for p in players}

    points = {p: 0 for p in players}
    for row in rows:
        if row["status"] == "done":
            if row["player1"] != BYE_MARKER:
                points[row["player1"]] += row["points1"]
            if row["player2"] != BYE_MARKER:
                points[row["player2"]] += row["points2"]

    weerstand = {p: 0 for p in players}
    if round_no == 1:
        for player in players:
            for opponent in players:
                if opponent != player:
                    weerstand[player] += moyennes.get(opponent, 0)
    else:
        previous_avgs = round_match_averages(conn, tournament_id, round_no - 1)
        opponents = round_opponents(conn, tournament_id, round_no)
        for player in players:
            for opponent in opponents.get(player, []):
                weerstand[player] += previous_avgs.get(opponent, seed_avgs.get(opponent, 0))

    standings = [
        {
            "player": p,
            "points": points[p],
            "weerstand": round(weerstand[p], 3),
            "seed_avg": round(moyennes.get(p, 0), 3)
        }
        for p in players
    ]

    standings.sort(
        key=lambda s: (
            s["points"], s["weerstand"], s["seed_avg"],
            _tiebreak_random(tournament_id, round_no, s["player"])
        ),
        reverse=True
    )

    return standings


def group_standings(conn, tournament_id, group_no):
    rows = conn.execute("""
        SELECT player1, player2, points1, points2, status
        FROM tournament_matches
        WHERE tournament_id=? AND group_no=?
    """, (tournament_id, group_no)).fetchall()

    players = sorted(({r["player1"] for r in rows} | {r["player2"] for r in rows}) - {BYE_MARKER})

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
            if row["player1"] != BYE_MARKER:
                points[row["player1"]] += row["points1"]
            if row["player2"] != BYE_MARKER:
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


def fold_pairs(players_in_order, bye_player=None):
    """Hoogste tegen middelste, een-na-hoogste tegen eerst-onder-gemiddelde, enz.
    Bij een oneven aantal krijgt bye_player (of anders de laagst geplaatste) een vrije ronde."""
    bye = None
    remaining = players_in_order

    if len(remaining) % 2:
        if bye_player is not None:
            bye = bye_player
            remaining = [p for p in remaining if p != bye_player]
        else:
            bye = remaining[-1]
            remaining = remaining[:-1]

    half = len(remaining) // 2
    top, bottom = remaining[:half], remaining[half:]
    return list(zip(top, bottom)), bye


def create_knockout_round(conn, tournament_id, round_no, players_in_order, seed_avgs, max_turns,
                          previous_round_no=None):
    """Eén knock-outronde: paart via fold_pairs en registreert een eventuele bye
    meteen als afgehandelde partij zodat de speler automatisch doorgaat."""
    bye_player = None
    if len(players_in_order) % 2 and previous_round_no is not None:
        averages = round_match_averages(conn, tournament_id, previous_round_no)
        bye_player = max(players_in_order, key=lambda p: averages.get(p, 0))

    pairs, bye = fold_pairs(players_in_order, bye_player=bye_player)

    for p1, p2 in pairs:
        target1 = int(seed_avgs[p1] * max_turns)
        target2 = int(seed_avgs[p2] * max_turns)

        conn.execute("""
            INSERT INTO tournament_matches
            (tournament_id, group_no, player1, player2, target1, target2, status)
            VALUES (?, ?, ?, ?, ?, ?, 'pending')
        """, (tournament_id, round_no, p1, p2, target1, target2))

    if bye:
        conn.execute("""
            INSERT INTO tournament_matches
            (tournament_id, group_no, player1, player2, target1, target2,
             caramboles1, caramboles2, turns_played, points1, points2, winner, status)
            VALUES (?, ?, ?, ?, 0, 0, 0, 0, 0, 1, 0, 'player1', 'done')
        """, (tournament_id, round_no, bye, BYE_MARKER))


def knockout_seeding(conn, tournament_id):
    """Spelersvolgorde (hoog naar laag moyenne) en hun seed-moyenne, vastgelegd bij aanmaak."""
    rows = conn.execute(
        "SELECT player, seed_avg FROM tournament_players WHERE tournament_id=? ORDER BY seed_avg DESC",
        (tournament_id,)
    ).fetchall()
    order = [row["player"] for row in rows]
    seed_avgs = {row["player"]: row["seed_avg"] for row in rows}
    return order, seed_avgs


def round_winners(conn, tournament_id, round_no, order):
    """Winnaars van een ronde (incl. bye's), in de oorspronkelijke seeding-volgorde."""
    matches = matches_for_group(conn, tournament_id, round_no)
    winners = {m["player1"] if m["winner"] == "player1" else m["player2"] for m in matches}
    return [p for p in order if p in winners]


def build_knockout_tournament(conn, name, game_type, max_turns, players):
    seed_avgs = {p: get_seed_avg(conn, p, game_type) for p in players}
    players_sorted = sorted(players, key=lambda p: seed_avgs[p], reverse=True)

    cur = conn.execute("""
        INSERT INTO tournaments (name, game_type, max_turns, status, format, created_at)
        VALUES (?, ?, ?, 'ronde 1', 'knockout', ?)
    """, (name, game_type, max_turns, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

    tournament_id = cur.lastrowid

    for player in players_sorted:
        conn.execute("""
            INSERT INTO tournament_players (tournament_id, player, seed_avg, group_no)
            VALUES (?, ?, ?, 1)
        """, (tournament_id, player, seed_avgs[player]))

    if len(players_sorted) <= 3:
        create_group_matches(conn, tournament_id, 1, players_sorted, seed_avgs, max_turns)
    else:
        create_knockout_round(conn, tournament_id, 1, players_sorted, seed_avgs, max_turns)

    conn.commit()

    return tournament_id


def tournament_champion(conn, tournament_id):
    """Winnaar van de laatste (afgesloten) ronde van een knock-outtournooi."""
    last_round = conn.execute(
        "SELECT MAX(group_no) AS mx FROM tournament_matches WHERE tournament_id=?",
        (tournament_id,)
    ).fetchone()["mx"]

    if last_round is None:
        return None

    matches = matches_for_group(conn, tournament_id, last_round)
    if not matches or any(m["status"] != "done" for m in matches):
        return None

    if len(matches) == 1:
        m = matches[0]
        return m["player1"] if m["winner"] == "player1" else m["player2"]

    standings = knockout_round_standings(conn, tournament_id, last_round)
    return standings[0]["player"] if standings else None


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


@tournament_bp.route("/tournament/estimate", methods=["POST"])
@coordinator_required
def tournament_estimate():
    data = request.json or {}

    game_type = data.get("game_type")
    players = list(dict.fromkeys(data.get("players") or []))
    duration_minutes = data.get("duration_minutes")
    num_tables = data.get("num_tables")
    avg_turn_seconds = data.get("avg_turn_seconds")

    def is_positive_number(value):
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            and value > 0
        )

    if game_type not in GAME_TYPES:
        return {"error": "kies libre of band"}, 400

    if len(players) < 3:
        return {"error": "kies minimaal 3 spelers"}, 400

    if not is_positive_number(duration_minutes):
        return {"error": "tournooiduur moet een positief getal zijn (minuten)"}, 400

    if not is_positive_number(num_tables) or num_tables != int(num_tables):
        return {"error": "aantal tafels moet een positief geheel getal zijn"}, 400

    if not is_positive_number(avg_turn_seconds):
        return {"error": "gemiddelde beurtduur moet een positief getal zijn (seconden)"}, 400

    conn = get_db()

    result = estimate_max_turns(
        conn, players, game_type, duration_minutes, int(num_tables), avg_turn_seconds
    )

    return result


def build_tournament(conn, name, game_type, max_turns, players, number_of_groups):
    """Slaat een nieuw tournooi op met een gegeven aantal groepen en verdeelt de spelers."""
    seed_avgs = {p: get_seed_avg(conn, p, game_type) for p in players}
    players_sorted = sorted(players, key=lambda p: seed_avgs[p], reverse=True)

    cur = conn.execute("""
        INSERT INTO tournaments (name, game_type, max_turns, status, created_at)
        VALUES (?, ?, ?, 'groups', ?)
    """, (name, game_type, max_turns, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

    tournament_id = cur.lastrowid

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

    return tournament_id


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

    number_of_groups = group_count(len(players))
    tournament_id = build_tournament(
        conn, name, game_type, max_turns, players, number_of_groups
    )

    return {"ok": True, "id": tournament_id}


@tournament_bp.route("/tournament/create_recommended", methods=["POST"])
@coordinator_required
def create_tournament_recommended():
    data = request.json or {}

    name = (data.get("name") or "").strip()
    game_type = data.get("game_type")
    players = list(dict.fromkeys(data.get("players") or []))
    duration_minutes = data.get("duration_minutes")
    num_tables = data.get("num_tables")
    avg_turn_seconds = data.get("avg_turn_seconds")

    def is_positive_number(value):
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            and value > 0
        )

    if not name:
        return {"error": "naam ontbreekt"}, 400

    if game_type not in GAME_TYPES:
        return {"error": "kies libre of band"}, 400

    if len(players) < 3 or len(players) > 20:
        return {"error": "kies minimaal 3 en maximaal 20 spelers"}, 400

    if not is_positive_number(duration_minutes):
        return {"error": "tournooiduur moet een positief getal zijn (minuten)"}, 400

    if not is_positive_number(num_tables) or num_tables != int(num_tables):
        return {"error": "aantal tafels moet een positief geheel getal zijn"}, 400

    if not is_positive_number(avg_turn_seconds):
        return {"error": "gemiddelde beurtduur moet een positief getal zijn (seconden)"}, 400

    conn = get_db()

    estimate = estimate_max_turns(
        conn, players, game_type, duration_minutes, int(num_tables), avg_turn_seconds
    )

    if estimate["format"] == "knockout":
        tournament_id = build_knockout_tournament(
            conn, name, game_type, estimate["recommended_max_turns"], players
        )
    else:
        tournament_id = build_tournament(
            conn, name, game_type, estimate["recommended_max_turns"],
            players, estimate["group_count"]
        )

    return {
        "ok": True,
        "id": tournament_id,
        "format": estimate["format"],
        "group_count": estimate["group_count"],
        "max_turns": estimate["recommended_max_turns"]
    }



@tournament_bp.route("/tournament/<int:tournament_id>/data")
@coordinator_required
def tournament_data(tournament_id):
    conn = get_db()

    trow = conn.execute(
        "SELECT * FROM tournaments WHERE id=?", (tournament_id,)
    ).fetchone()

    if not trow:
        return {"error": "tournooi niet gevonden"}, 404

    if trow["format"] == "knockout":
        round_numbers = sorted({
            row["group_no"] for row in conn.execute(
                "SELECT DISTINCT group_no FROM tournament_matches WHERE tournament_id=?",
                (tournament_id,)
            ).fetchall()
        })

        groups = {
            round_no: {
                # elke ronde toont zijn eigen moyennes/weerstand, niet doorgevoerd vanuit andere rondes
                "standings": knockout_round_standings(conn, tournament_id, round_no),
                "matches": matches_for_group(conn, tournament_id, round_no)
            }
            for round_no in round_numbers
        }

        champion = tournament_champion(conn, tournament_id) if trow["status"] == "done" else None
        report_file = None

        return {
            "tournament": dict(trow),
            "groups": groups,
            "final": None,
            "champion": champion,
            "report": report_file
        }

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

    if trow["format"] == "knockout" and winner == "draw" and not is_round_robin_round(conn, tournament_id, match["group_no"]):
        winner = resolve_knockout_draw(
            conn, tournament_id, match["group_no"], match["player1"], match["player2"],
            caramboles1, caramboles2, turns_played
        )
        points1, points2 = (1, 0) if winner == "player1" else (0, 1)

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

    if trow["format"] == "knockout":
        return {"error": "knock-outtournooi gebruikt /next_round"}, 400

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


@tournament_bp.route("/tournament/<int:tournament_id>/next_round", methods=["POST"])
@coordinator_required
def tournament_next_round(tournament_id):
    conn = get_db()

    trow = conn.execute(
        "SELECT * FROM tournaments WHERE id=?", (tournament_id,)
    ).fetchone()

    if not trow:
        return {"error": "tournooi niet gevonden"}, 404

    if trow["format"] != "knockout":
        return {"error": "alleen voor knock-outtournooien"}, 400

    last_round = conn.execute(
        "SELECT MAX(group_no) AS mx FROM tournament_matches WHERE tournament_id=?",
        (tournament_id,)
    ).fetchone()["mx"]

    matches = matches_for_group(conn, tournament_id, last_round)
    pending = [m for m in matches if m["status"] != "done"]
    if not matches or pending:
        pending_names = ", ".join(f"{m['player1']} - {m['player2']}" for m in pending)
        return {
            "error": "de huidige ronde is nog niet volledig gespeeld"
            + (f": {pending_names}" if pending_names else "")
        }, 400

    participants = set()
    for m in matches:
        participants.update({m["player1"], m["player2"]} - {BYE_MARKER})

    if len(participants) <= 3:
        champion = tournament_champion(conn, tournament_id)
        conn.execute("UPDATE tournaments SET status='done' WHERE id=?", (tournament_id,))
        conn.commit()
        return {"ok": True, "done": True, "champion": champion}

    order, seed_avgs = knockout_seeding(conn, tournament_id)
    winners = round_winners(conn, tournament_id, last_round, order)

    next_round = last_round + 1
    if len(winners) > 3:
        create_knockout_round(
            conn, tournament_id, next_round, winners, seed_avgs, trow["max_turns"],
            previous_round_no=last_round
        )
    else:
        create_group_matches(conn, tournament_id, next_round, winners, seed_avgs, trow["max_turns"])

    conn.execute(
        "UPDATE tournaments SET status=? WHERE id=?",
        (f"ronde {next_round}", tournament_id)
    )
    conn.commit()

    return {"ok": True, "round": next_round}


@tournament_bp.route("/tournament/<int:tournament_id>/finish", methods=["POST"])
@coordinator_required
def tournament_finish(tournament_id):
    conn = get_db()

    trow = conn.execute(
        "SELECT * FROM tournaments WHERE id=?", (tournament_id,)
    ).fetchone()

    if not trow:
        return {"error": "tournooi niet gevonden"}, 404

    if trow["format"] == "knockout":
        champion = tournament_champion(conn, tournament_id)
        if champion is None:
            return {"error": "de huidige ronde is nog niet volledig gespeeld"}, 400

        conn.execute("UPDATE tournaments SET status='done' WHERE id=?", (tournament_id,))
        conn.commit()

        return {"ok": True, "champion": champion, "report": None}

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
