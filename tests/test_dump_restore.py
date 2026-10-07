"""Round-trip тест debug-эндпоинтов dump/restore.

In-process через TestClient — внешний сервер на localhost:8000 не нужен.
Помимо самих эндпоинтов проверяет, что mech переживает сериализацию и
восстановление (регрессия на src.debug.game_state_utils.restore_player_from_data).
"""

import asyncio
from uuid import uuid4

from fastapi.testclient import TestClient

from main import app
from src.action import Action, ActionType

client = TestClient(app)


def _start_two_player_game() -> str:
    player1_id = str(uuid4())
    player2_id = str(uuid4())

    lobby_id = client.post(
        "/lobbies",
        json={"players_num": 2, "created_by_player_id": player1_id},
    ).json()["lobby_id"]

    for pid, team in [(player1_id, 1), (player2_id, 2)]:
        resp = client.post(
            "/connect_lobby",
            json={"lobby_id": lobby_id, "player": {"id": pid, "team": team}},
        )
        assert resp.status_code == 200, resp.text

    resp = client.post(
        "/start_game", json={"lobby_id": lobby_id, "host_player_id": player1_id}
    )
    assert resp.status_code == 200, resp.text
    return lobby_id


def test_dump_restore_workflow():
    lobby_id = _start_two_player_game()
    game = app.state.lobby_manager.lobbies[lobby_id].game
    mover = game.turn.current_actor
    initial_moves = [cell.model_dump() for cell in game.turn.available_moves]
    move = Action(
        actor_id=str(mover.id),
        type=ActionType.MOVE,
        cell=game.turn.available_moves[0],
    )
    assert asyncio.run(game.perform_actor_action(mover, move)).performed

    # dump
    dump = client.post("/debug/dump_game_state", json={"lobby_id": lobby_id})
    assert dump.status_code == 200, dump.text
    game_state = dump.json()["game_state"]
    assert {"arena", "players", "turn"} <= game_state.keys()
    assert len(game_state["players"]) == 4
    assert len(game_state["enemies"]) == 2
    assert "enemies" not in game_state["arena"]
    assert len({p["owner_player_id"] for p in game_state["players"]}) == 2
    assert "mech" in game_state["players"][0], "mech должен попадать в дамп"
    assert game_state["turn"]["current_actor"]["current_speed_spent"] == 1
    assert game_state["turn"]["available_moves"] == []
    # Старые дампы могли содержать доступные клетки даже после первого MOVE.
    game_state["turn"]["available_moves"] = initial_moves

    # restore обратно в то же лобби
    restore = client.post(
        "/debug/restore_game_state",
        json={"lobby_id": lobby_id, "game_state": game_state},
    )
    assert restore.status_code == 200, restore.text
    assert restore.json()["success"] is True

    # dump после restore — состояние должно остаться сериализуемым и согласованным
    dump2 = client.post("/debug/dump_game_state", json={"lobby_id": lobby_id})
    assert dump2.status_code == 200, dump2.text
    game_state2 = dump2.json()["game_state"]
    assert len(game_state2["players"]) == len(game_state["players"])
    assert len(game_state2["enemies"]) == len(game_state["enemies"])
    assert (
        game_state2["turn"]["player_actor_order"]
        == game_state["turn"]["player_actor_order"]
    )
    assert "mech" in game_state2["players"][0]
    assert game_state2["turn"]["current_actor"]["current_speed_spent"] == 1
    assert game_state2["turn"]["available_moves"] == []
    restored_game = app.state.lobby_manager.lobbies[lobby_id].game
    repeated = asyncio.run(
        restored_game.perform_actor_action(
            restored_game.turn.current_actor,
            Action(
                actor_id=str(mover.id),
                type=ActionType.MOVE,
                cell=move.cell,
            ),
        )
    )
    assert not repeated.performed
    assert "перемещение уже использовано" in repeated.detail
