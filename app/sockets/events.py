from flask_socketio import SocketIO, emit
from app.database import get_db
from datetime import datetime
from app.routes.matches import ACTIVE_MATCHES

socketio = SocketIO(
    async_mode="threading"
)


def register_socket_events(socketio):

    @socketio.on("score_update")
    def score_update(data):

        m = ACTIVE_MATCHES.get(data["match_id"])
        if not m:
            return

        player = data["player"]
        total = data["total"]

        if player == m["player1"]:
            m["total1"] = total
        else:
            m["total2"] = total

        emit("match_update", m, broadcast=True)


    @socketio.on("finish_match")
    def finish_match(data):

        match_id = data["match_id"]
        turns = data.get("turns", 0)

        m = ACTIVE_MATCHES.get(match_id)
        if not m:
            return

        p1 = m["player1"]
        p2 = m["player2"]

        total1 = m.get("total1", 0)
        total2 = m.get("total2", 0)

        game = m["game_type"]

        if total1 > total2:
            winner = p1
        elif total2 > total1:
            winner = p2
        else:
            winner = "draw"

        m["status"] = "finished"
        m["winner"] = winner

        conn = get_db()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        avg1 = round(total1 / turns, 3) if turns else 0
        avg2 = round(total2 / turns, 3) if turns else 0

        conn.execute("""
        INSERT INTO results
        (match_id, player, opponent, total, game_type, ts_recorded,
         points, result, avg, turns)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (match_id, p1, p2, total1, game, now, 0, winner, avg1, turns))

        conn.execute("""
        INSERT INTO results
        (match_id, player, opponent, total, game_type, ts_recorded,
         points, result, avg, turns)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (match_id, p2, p1, total2, game, now, 0, winner, avg2, turns))

        conn.commit()

        emit("match_update", m, broadcast=True)