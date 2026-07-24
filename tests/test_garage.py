from uuid import uuid4
import asyncio

from fastapi.testclient import TestClient

from main import app
from src.garage import apply_random_affix, fresh_part, roll_match_reward
from src.parts_catalog import FIREWORKS_ARMS, FIREWORKS_TORSO


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


def test_garage_tuning_is_saved_and_reflected_in_garage_state():
    player_id = str(uuid4())
    connect_player(
        create_lobby(player_id),
        player_id,
        ["SteelMan", "Fireworks Mk. 1"],
    )

    garage = client.get(f"/debug/garages/{player_id}").json()
    loadout_id = garage["loadouts"][0]["id"]

    response = client.post(
        "/debug/garages/tuning",
        json={
            "player_id": player_id,
            "loadout_id": loadout_id,
            "reactor_mode": "fortified",
            "fire_control_mode": "impact",
        },
    )

    assert response.status_code == 200
    tuned_loadout = response.json()["loadouts"][0]
    assert tuned_loadout["reactor_mode"] == "fortified"
    assert tuned_loadout["fire_control_mode"] == "impact"
    assert tuned_loadout["stats"]["health"] == 21
    assert tuned_loadout["stats"]["action_points"] == 9
    assert tuned_loadout["weapons"][0]["damage"] == 7


def test_garage_tuning_is_applied_when_match_starts():
    player_id = str(uuid4())
    lobby_id = create_lobby(player_id)
    connect_player(lobby_id, player_id, ["SteelMan", "Fireworks Mk. 1"])

    garage = client.get(f"/debug/garages/{player_id}").json()
    first_loadout_id = garage["loadouts"][0]["id"]
    second_loadout_id = garage["loadouts"][1]["id"]

    for loadout_id, reactor_mode, fire_control_mode in (
        (first_loadout_id, "fortified", "impact"),
        (second_loadout_id, "overdrive", "precision"),
    ):
        response = client.post(
            "/debug/garages/tuning",
            json={
                "player_id": player_id,
                "loadout_id": loadout_id,
                "reactor_mode": reactor_mode,
                "fire_control_mode": fire_control_mode,
            },
        )
        assert response.status_code == 200

    response = client.post("/start_game", json={"lobby_id": lobby_id})
    assert response.status_code == 200
    assert response.json()["result"] is True

    from main import lobby_manager

    lobby = lobby_manager.get_lobby(lobby_id)
    actor_ids = lobby.participants[player_id].actor_ids
    first_actor = lobby.players[actor_ids[0]]
    second_actor = lobby.players[actor_ids[1]]

    assert first_actor.stats.health == 21
    assert first_actor.stats.action_points == 9
    assert first_actor.inventory.weapons[0].damage == 7

    assert second_actor.stats.health == 9
    assert second_actor.stats.action_points == 11
    assert second_actor.stats.accuracy == 90
    assert second_actor.inventory.weapons[0].damage == 4


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


def test_apply_random_affix_updates_part_stats_and_metadata():
    part = fresh_part(FIREWORKS_ARMS)

    apply_random_affix(part, affix_tier=2)

    assert part.affix_tier == 2
    assert part.affix_stat in {"accuracy", "melee_power"}
    assert part.affix_value in {2, 8}
    assert "+2 к " in part.name
    if part.affix_stat == "accuracy":
        assert part.accuracy == FIREWORKS_ARMS.accuracy + 8
    else:
        assert part.melee_power == FIREWORKS_ARMS.melee_power + 2


def test_match_reward_can_drop_affixed_copy_of_known_base_part(monkeypatch):
    player_id = str(uuid4())
    connect_player(
        create_lobby(player_id),
        player_id,
        ["SteelMan", "Fireworks Mk. 1"],
    )

    from main import lobby_manager

    garage = lobby_manager.garages[player_id]
    existing_keys = [part["catalog_key"] for part in client.get(f"/debug/garages/{player_id}").json()["loadouts"][0]["mech"].values() if isinstance(part, dict) and "catalog_key" in part]

    random_values = iter((0.0, 0.95, 0.10))
    monkeypatch.setattr("src.garage.random.random", lambda: next(random_values))
    monkeypatch.setattr("src.garage.random.choice", lambda seq: seq[0])

    reward = roll_match_reward(garage, is_winner=True)

    assert reward.awarded_part is not None
    assert reward.awarded_part.affix_tier == 2
    assert reward.awarded_part.catalog_key in existing_keys


def test_garage_shows_xp_level_and_pending_skill_choice():
    player_id = str(uuid4())
    connect_player(create_lobby(player_id), player_id, ["SteelMan", "Fireworks Mk. 1"])

    from main import lobby_manager

    garage = lobby_manager.garages[player_id]
    progression = garage.award_xp(100)

    assert progression.level_after == 2
    state = client.get(f"/debug/garages/{player_id}").json()
    assert state["xp"] == 100
    assert state["level"] == 2
    assert state["owned_skills"] == []
    assert len(state["pending_skill_choices"]) == 1
    assert state["pending_skill_choices"][0]["level"] == 2
    assert [skill["skill_key"] for skill in state["pending_skill_choices"][0]["options"]] == [
        "accurate_shot",
        "heavy_strike",
    ]


def test_skill_choice_is_saved_and_used_when_match_starts():
    player_id = str(uuid4())
    lobby_id = create_lobby(player_id)
    connect_player(lobby_id, player_id, ["SteelMan", "Fireworks Mk. 1"])

    from main import lobby_manager

    garage = lobby_manager.garages[player_id]
    garage.award_xp(250)

    response = client.post(
        "/debug/garages/choose_skill",
        json={"player_id": player_id, "skill_key": "accurate_shot"},
    )
    assert response.status_code == 200
    response = client.post(
        "/debug/garages/choose_skill",
        json={"player_id": player_id, "skill_key": "combat_impulse"},
    )
    assert response.status_code == 200
    chosen_state = response.json()
    assert [skill["skill_key"] for skill in chosen_state["owned_skills"]] == [
        "accurate_shot",
        "combat_impulse",
    ]
    assert chosen_state["pending_skill_choices"] == []

    start_response = client.post("/start_game", json={"lobby_id": lobby_id})
    assert start_response.status_code == 200
    assert start_response.json()["result"] is True

    lobby = lobby_manager.get_lobby(lobby_id)
    actor_ids = lobby.participants[player_id].actor_ids
    for actor_id in actor_ids:
        assert [skill.skill_key for skill in lobby.players[actor_id].skills] == [
            "accurate_shot",
            "combat_impulse",
        ]


def test_finalize_match_rewards_awards_winner_xp():
    player_id = str(uuid4())
    lobby_id = create_lobby(player_id)
    connect_player(lobby_id, player_id, ["SteelMan", "Fireworks Mk. 1"])

    from main import lobby_manager

    client.post("/start_game", json={"lobby_id": lobby_id})
    lobby = lobby_manager.get_lobby(lobby_id)
    lobby.game.winner = 1

    asyncio.run(lobby.finalize_match_rewards())

    garage = lobby_manager.garages[player_id]
    assert garage.xp == 70
    assert garage.metrics.matches_finished == 1
