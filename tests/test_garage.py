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


def connect_player(
    lobby_id: str,
    player_id: str,
    presets: list[str | None],
) -> None:
    response = client.post(
        "/connect_lobby",
        json={
            "lobby_id": lobby_id,
            "player": {"id": player_id, "team": 1, "mech_presets": presets},
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
    connect_player(
        create_lobby(player_id),
        player_id,
        ["SteelMan", "Fireworks Mk. 1"],
    )

    first_garage = client.get(f"/debug/garages/{player_id}")
    assert first_garage.status_code == 200
    assert [loadout["preset_name"] for loadout in first_garage.json()["loadouts"]] == [
        "SteelMan",
        "Fireworks Mk. 1",
    ]

    connect_player(
        create_lobby(player_id),
        player_id,
        ["StrikeForce", "StrikeForce"],
    )

    second_garage = client.get(f"/debug/garages/{player_id}")
    assert second_garage.status_code == 200
    assert [loadout["preset_name"] for loadout in second_garage.json()["loadouts"]] == [
        "SteelMan",
        "Fireworks Mk. 1",
    ]


def test_identical_presets_create_independent_physical_parts():
    player_id = str(uuid4())
    connect_player(
        create_lobby(player_id),
        player_id,
        ["SteelMan", "SteelMan"],
    )

    garage = client.get(f"/debug/garages/{player_id}").json()
    first_torso = garage["loadouts"][0]["mech"]["torso"]
    second_torso = garage["loadouts"][1]["mech"]["torso"]

    assert first_torso["catalog_key"] == second_torso["catalog_key"]
    assert first_torso["id"] != second_torso["id"]


def test_equipped_garage_part_is_used_when_match_starts():
    player_id = str(uuid4())
    lobby_id = create_lobby(player_id)
    connect_player(lobby_id, player_id, ["SteelMan", "Fireworks Mk. 1"])

    from main import lobby_manager

    stored_part = fresh_part(FIREWORKS_TORSO)
    garage = lobby_manager.garages[player_id]
    garage.owned_parts.append(stored_part)
    first_loadout_id = str(garage.loadouts[0].id)
    response = client.post(
        "/debug/garages/equip",
        json={
            "player_id": player_id,
            "loadout_id": first_loadout_id,
            "part_id": str(stored_part.id),
        },
    )
    assert response.status_code == 200
    assert (
        response.json()["loadouts"][0]["mech"]["torso"]["name"]
        == "Лёгкий корпус «Стриж»"
    )

    response = client.post("/start_game", json={"lobby_id": lobby_id})
    assert response.status_code == 200
    assert response.json()["result"] is True
    assert response.json()["detail"] == "Game started"
    lobby = lobby_manager.get_lobby(lobby_id)
    actor_ids = lobby.participants[player_id].actor_ids
    assert len(actor_ids) == 2
    assert lobby.players[actor_ids[0]].mech.torso.name == "Лёгкий корпус «Стриж»"
    assert lobby.players[actor_ids[1]].mech.torso.name == "Лёгкий корпус «Стриж»"
    assert (
        lobby.players[actor_ids[0]].mech.torso.id
        != lobby.players[actor_ids[1]].mech.torso.id
    )


def test_one_physical_part_cannot_be_equipped_on_two_loadouts():
    player_id = str(uuid4())
    connect_player(
        create_lobby(player_id),
        player_id,
        ["SteelMan", "Fireworks Mk. 1"],
    )

    from main import lobby_manager

    garage = lobby_manager.garages[player_id]
    stored_part = fresh_part(FIREWORKS_TORSO)
    garage.owned_parts.append(stored_part)
    first_loadout_id = str(garage.loadouts[0].id)
    second_loadout_id = str(garage.loadouts[1].id)

    first_response = client.post(
        "/debug/garages/equip",
        json={
            "player_id": player_id,
            "loadout_id": first_loadout_id,
            "part_id": str(stored_part.id),
        },
    )
    assert first_response.status_code == 200

    second_response = client.post(
        "/debug/garages/equip",
        json={
            "player_id": player_id,
            "loadout_id": second_loadout_id,
            "part_id": str(stored_part.id),
        },
    )
    assert second_response.status_code == 400
    assert "Деталь уже установлена на «Мех 1»" in second_response.json()["detail"]
