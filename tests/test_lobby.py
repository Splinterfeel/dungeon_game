from fastapi.testclient import TestClient
from main import app
from uuid import UUID, uuid4

# TestClient гоняет ASGI-приложение in-process — отдельный uvicorn поднимать не нужно
client = TestClient(app)


def test_create_lobby():
    response = client.post(
        "/lobbies",
        json={
            "players_num": 2,
            "created_by_player_id": "123e4567-e89b-12d3-a456-426614174000",
        },
    )
    assert response.status_code == 200
    assert "lobby_id" in response.json()


def test_connect_to_nonexistent_lobby():
    nonexistent_lobby_id = UUID("123e4567-e89b-12d3-a456-426614174000")
    response = client.post(
        "/connect_lobby",
        json={
            "lobby_id": str(nonexistent_lobby_id),
            "player": {"id": "123e4567-e89b-12d3-a456-426614174000", "team": 1},
        },
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Lobby not found"}


def test_join_lobby():
    resp = client.post(
        "/lobbies",
        json={
            "players_num": 2,
            "created_by_player_id": "123e4567-e89b-12d3-a456-426614174000",
        },
    )
    response = client.post(
        "/connect_lobby",
        json={
            "lobby_id": resp.json()["lobby_id"],
            "player": {"id": "123e4567-e89b-12d3-a456-426614174000", "team": 1},
        },
    )
    assert response.status_code == 200
    assert response.json()["detail"] == "player connected"


def test_connect_to_full_lobby():
    # Create a lobby with 1 player slot
    resp = client.post(
        "/lobbies",
        json={
            "players_num": 1,
            "created_by_player_id": "123e4567-e89b-12d3-a456-426614174000",
        },
    )
    lobby_id = resp.json()["lobby_id"]

    # Connect the 1st player to fill the lobby
    client.post(
        "/connect_lobby",
        json={
            "lobby_id": lobby_id,
            "player": {"id": "123e4567-e89b-12d3-a456-426614174001", "team": 1},
        },
    )

    # Try to connect the 2nd player to the full lobby
    response = client.post(
        "/connect_lobby",
        json={
            "lobby_id": lobby_id,
            "player": {"id": "123e4567-e89b-12d3-a456-426614174002", "team": 2},
        },
    )
    assert response.status_code == 200
    assert response.json()["detail"] == "lobby full"


def test_websocket_pilot_controls_current_owned_mech():
    player_1 = str(uuid4())
    player_2 = str(uuid4())
    lobby_id = client.post(
        "/lobbies",
        json={"players_num": 2, "created_by_player_id": player_1},
    ).json()["lobby_id"]
    for player_id, team in ((player_1, 1), (player_2, 2)):
        response = client.post(
            "/connect_lobby",
            json={
                "lobby_id": lobby_id,
                "player": {
                    "id": player_id,
                    "team": team,
                    "mech_presets": ["SteelMan", "Fireworks Mk. 1"],
                },
            },
        )
        assert response.json()["result"] is True
    assert client.post("/start_game", json={"lobby_id": lobby_id}).json()["result"]

    with client.websocket_connect(f"/ws/{lobby_id}/{player_1}") as websocket:
        initial_state = websocket.receive_json()
        assert initial_state["type"] == "state_update"
        state = initial_state["payload"]
        owned = [
            player
            for player in state["players"]
            if player["owner_player_id"] == player_1
        ]
        assert len(owned) == 2
        current = state["turn"]["current_actor"]
        assert current["owner_player_id"] == player_1
        assert state["turn"]["available_moves"]

        websocket.send_json(
            {
                "id": str(uuid4()),
                "actor_id": current["id"],
                "type": "END_TURN",
                "cell": current["position"],
                "params": None,
            }
        )

        next_state = None
        for _ in range(8):
            message = websocket.receive_json()
            if message.get("type") != "state_update":
                continue
            candidate = message["payload"]
            candidate_actor = candidate["turn"]["current_actor"]
            if candidate_actor is None or candidate_actor["id"] != current["id"]:
                next_state = candidate
                break

        assert next_state is not None
        next_actor = next_state["turn"]["current_actor"]
        if next_actor is not None:
            assert next_actor["owner_player_id"] == player_2
        assert next_state["turn"]["available_moves"] == []
