from flask_socketio import SocketIO, emit
from app.routes.matches import (
    ACTIVE_MATCHES,
    build_pending_result,
    set_pending_result
)

socketio = SocketIO(
    async_mode="threading"
)


def register_socket_events(socketio):

    @socketio.on("score_update")
    def score_update(data):

        m = ACTIVE_MATCHES.get(data["match_id"])
        if not m or m.get("status") != "busy":
            return

        if m.get("claimed_by") != data.get("claim_token"):
            return

        player = data["player"]
        total = data["total"]

        if player == m["player1"]:
            m["total1"] = total
        elif player == m["player2"]:
            m["total2"] = total
        else:
            return

        emit("match_update", m, broadcast=True)


    @socketio.on("finish_match")
    def finish_match(data):

        match_id = data["match_id"]
        turns = data.get("turns", 0)

        m = ACTIVE_MATCHES.get(match_id)
        if not m or m.get("status") != "busy":
            return

        if m.get("claimed_by") != data.get("claim_token"):
            return

        total1 = m.get("total1", 0)
        total2 = m.get("total2", 0)

        result = build_pending_result(m, {
            "total1": total1,
            "total2": total2,
            "turns": turns,
            "high_run1": data.get("high_run1", 0),
            "high_run2": data.get("high_run2", 0)
        })
        set_pending_result(result)
        m["status"] = "pending"
        m["winner"] = result["winner"]

        emit("match_update", m, broadcast=True)