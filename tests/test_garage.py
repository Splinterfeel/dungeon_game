from uuid import uuid4

from fastapi.testclient import TestClient

from main import app
from src.garage import fresh_part
from src.parts_catalog import FIREWORKS_TORSO


client = TestClient(app)


def create_lobby(player_id: str) -> str:
    response = client.post(
        "/lobbies",
        json={"players_num": 1, "created_by_player_id": player_id},
    )
    assert response.status_code == 200
    return response.json()["lobby_id"]


def connect_player(lobby_id: str, player_id: str, preset: str) -> None:
    response = client.post(
        "/connect_lobby",
        json={
            "lobby_id": lobby_id,
            "player": {"id": player_id, "team": 1, "mech_preset": preset},
        },
    )
    assert response.status_code == 200
    assert response.json()["result"] is True


def test_garage_requires_first_connection():
    response = client.get(f"/debug/garages/{uuid4()}")

    assert response.status_code == 404
    assert "сначала подключитесь" in response.json()["detail"]


def test_garage_page_is_available():
    response = client.get("/garage")

    assert response.status_code == 200
    assert "Debug Garage" in response.text


def test_garage_is_shared_between_lobbies_and_ignores_later_preset():
    player_id = str(uuid4())
    connect_player(create_lobby(player_id), player_id, "SteelMan")

    first_garage = client.get(f"/debug/garages/{player_id}")
    assert first_garage.status_code == 200
    assert first_garage.json()["mech"]["torso"]["name"] == "Тяжёлый корпус «Голем»"

    connect_player(create_lobby(player_id), player_id, "Fireworks Mk. 1")

    second_garage = client.get(f"/debug/garages/{player_id}")
    assert second_garage.status_code == 200
    assert second_garage.json()["mech"]["torso"]["name"] == "Тяжёлый корпус «Голем»"


def test_equipped_garage_part_is_used_when_match_starts():
    player_id = str(uuid4())
    lobby_id = create_lobby(player_id)
    connect_player(lobby_id, player_id, "SteelMan")

    from main import lobby_manager

    stored_part = fresh_part(FIREWORKS_TORSO)
    lobby_manager.garages[player_id].owned_parts.append(stored_part)
    response = client.post(
        "/debug/garages/equip",
        json={"player_id": player_id, "part_id": str(stored_part.id)},
    )
    assert response.status_code == 200
    assert response.json()["mech"]["torso"]["name"] == "Лёгкий корпус «Стриж»"

    response = client.post("/start_game", json={"lobby_id": lobby_id})
    assert response.status_code == 200
    assert response.json()["result"] is True
    assert response.json()["detail"] == "Game started"
    lobby = lobby_manager.get_lobby(lobby_id)
    assert lobby.players[player_id].mech.torso.name == "Лёгкий корпус «Стриж»"
