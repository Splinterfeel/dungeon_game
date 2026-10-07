from uuid import uuid4
import asyncio

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from main import app, garage_manager, lobby_manager
from src.garage import GarageProfile, apply_random_affix, roll_match_reward
from src.garage_manager import GarageManager
from src.mech.catalog import FIREWORKS_ARMS, FIREWORKS_TORSO
from src.persistence.database import get_session_factory
from src.persistence.garage import load_profile
from src.persistence.models import (
    LoadoutPartRecord,
    MatchRewardRecord,
    PartCatalogRecord,
    SkillCatalogRecord,
)

client = TestClient(app)


def test_explicit_zero_affix_does_not_roll(monkeypatch):
    def unexpected_roll(*args):
        raise AssertionError("Явный нулевой аффикс не должен запускать бросок")

    monkeypatch.setattr("src.rewards.weighted_roll_int", unexpected_roll)
    part = FIREWORKS_ARMS.fresh_copy()
    before = part.model_dump()
    assert apply_random_affix(part, affix_tier=0) is part
    assert part.model_dump() == before


def test_destroyed_part_survives_validation_and_fresh_copy_repairs():
    from src.mech.part import Part

    part = Part(catalog_key="test", slot="arms", name="Тест", max_health=170)
    assert part.current_health == 170
    part.apply_damage(170)
    restored = Part.model_validate(part.model_dump())
    assert restored.destroyed
    assert Part.model_validate(restored).destroyed
    fresh = restored.fresh_copy()
    assert fresh.current_health == 170
    assert restored.current_health == 0


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
    response = client.get(f"/garages/{uuid4()}")

    assert response.status_code == 404
    assert "сначала подключитесь" in response.json()["detail"]


def test_debug_pilots_lists_existing_profiles():
    player_id = str(uuid4())
    connect_player(create_lobby(player_id), player_id, ["SteelMan", "Fireworks Mk. 1"])

    response = client.get("/debug/pilots")

    assert response.status_code == 200
    pilot = next(item for item in response.json() if item["id"] == player_id)
    assert set(pilot) == {"id", "name", "xp", "level", "matches_finished"}
    assert pilot["level"] == 1
    assert pilot["matches_finished"] == 0


def test_garage_from_battle_actors_preserves_owner():
    import pytest

    owner_id = str(uuid4())
    connect_player(create_lobby(owner_id), owner_id, ["SteelMan", "Fireworks Mk. 1"])
    actors = asyncio.run(garage_manager.build_players(owner_id, team=1))
    assert actors[0].id != actors[0].owner_player_id
    restored = GarageProfile.from_players(actors)
    assert str(restored.player_id) == owner_id

    actors[1].owner_player_id = uuid4()
    with pytest.raises(ValueError, match="одному пилоту"):
        GarageProfile.from_players(actors)


def test_garage_page_is_available():
    response = client.get("/garage")

    assert response.status_code == 200
    assert "Debug Garage" in response.text


def test_debug_map_can_select_existing_or_new_pilot():
    response = client.get("/")

    assert response.status_code == 200
    assert 'id="player_select"' in response.text
    assert "Новый случайный UUID" in response.text
    assert "refresh_pilots_list" in response.text


def test_garage_is_shared_between_lobbies_and_ignores_later_preset():
    player_id = str(uuid4())
    connect_player(
        create_lobby(player_id),
        player_id,
        ["SteelMan", "Fireworks Mk. 1"],
    )

    first_garage = client.get(f"/garages/{player_id}")
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

    second_garage = client.get(f"/garages/{player_id}")
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

    garage = client.get(f"/garages/{player_id}").json()
    first_torso = garage["loadouts"][0]["mech"]["torso"]
    second_torso = garage["loadouts"][1]["mech"]["torso"]

    assert first_torso["catalog_key"] == second_torso["catalog_key"]
    assert first_torso["id"] != second_torso["id"]


def test_equipped_garage_part_is_used_when_match_starts():
    player_id = str(uuid4())
    lobby_id = create_lobby(player_id)
    connect_player(lobby_id, player_id, ["SteelMan", "Fireworks Mk. 1"])

    stored_part = FIREWORKS_TORSO.fresh_copy()
    garage = asyncio.run(garage_manager.get_profile(player_id))
    garage.owned_parts.append(stored_part)
    asyncio.run(garage_manager.save_profile(garage))
    first_loadout_id = str(garage.loadouts[0].id)
    response = client.post(
        "/garages/equip",
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

    response = client.post(
        "/start_game", json={"lobby_id": lobby_id, "host_player_id": player_id}
    )
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

    garage = client.get(f"/garages/{player_id}").json()
    loadout_id = garage["loadouts"][0]["id"]

    response = client.post(
        "/garages/tuning",
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
    assert tuned_loadout["stats"]["health"] == 210
    assert tuned_loadout["stats"]["action_points"] == 9
    assert tuned_loadout["weapons"][0]["damage"] == 70

    reloaded = asyncio.run(GarageManager().get_garage_state(player_id))
    assert reloaded.loadouts[0].reactor_mode == "fortified"
    assert reloaded.loadouts[0].fire_control_mode == "impact"


def test_garage_tuning_is_applied_when_match_starts():
    player_id = str(uuid4())
    lobby_id = create_lobby(player_id)
    connect_player(lobby_id, player_id, ["SteelMan", "Fireworks Mk. 1"])

    garage = client.get(f"/garages/{player_id}").json()
    first_loadout_id = garage["loadouts"][0]["id"]
    second_loadout_id = garage["loadouts"][1]["id"]

    for loadout_id, reactor_mode, fire_control_mode in (
        (first_loadout_id, "fortified", "impact"),
        (second_loadout_id, "overdrive", "precision"),
    ):
        response = client.post(
            "/garages/tuning",
            json={
                "player_id": player_id,
                "loadout_id": loadout_id,
                "reactor_mode": reactor_mode,
                "fire_control_mode": fire_control_mode,
            },
        )
        assert response.status_code == 200

    response = client.post(
        "/start_game", json={"lobby_id": lobby_id, "host_player_id": player_id}
    )
    assert response.status_code == 200
    assert response.json()["result"] is True

    lobby = lobby_manager.get_lobby(lobby_id)
    actor_ids = lobby.participants[player_id].actor_ids
    first_actor = lobby.players[actor_ids[0]]
    second_actor = lobby.players[actor_ids[1]]

    assert first_actor.stats.health == 210
    assert first_actor.stats.action_points == 9
    assert first_actor.inventory.weapons[0].damage == 70

    assert second_actor.stats.health == 90
    assert second_actor.stats.action_points == 11
    assert second_actor.stats.accuracy == 90
    assert second_actor.inventory.weapons[0].damage == 40


def test_one_physical_part_cannot_be_equipped_on_two_loadouts():
    player_id = str(uuid4())
    connect_player(
        create_lobby(player_id),
        player_id,
        ["SteelMan", "Fireworks Mk. 1"],
    )

    garage = asyncio.run(garage_manager.get_profile(player_id))
    stored_part = FIREWORKS_TORSO.fresh_copy()
    garage.owned_parts.append(stored_part)
    asyncio.run(garage_manager.save_profile(garage))
    first_loadout_id = str(garage.loadouts[0].id)
    second_loadout_id = str(garage.loadouts[1].id)

    first_response = client.post(
        "/garages/equip",
        json={
            "player_id": player_id,
            "loadout_id": first_loadout_id,
            "part_id": str(stored_part.id),
        },
    )
    assert first_response.status_code == 200

    second_response = client.post(
        "/garages/equip",
        json={
            "player_id": player_id,
            "loadout_id": second_loadout_id,
            "part_id": str(stored_part.id),
        },
    )
    assert second_response.status_code == 400
    assert "Деталь уже установлена на «Мех 1»" in second_response.json()["detail"]


def test_apply_random_affix_updates_part_stats_and_metadata():
    part = FIREWORKS_ARMS.fresh_copy()

    apply_random_affix(part, affix_tier=2)

    assert part.affix_tier == 2
    assert part.affix_stat in {"accuracy", "melee_power"}
    assert part.affix_value in {20, 8}
    assert "+2 к " in part.name
    if part.affix_stat == "accuracy":
        assert part.accuracy == FIREWORKS_ARMS.accuracy + 8
    else:
        assert part.melee_power == FIREWORKS_ARMS.melee_power + 20


def test_match_reward_can_drop_affixed_copy_of_known_base_part(monkeypatch):
    player_id = str(uuid4())
    connect_player(
        create_lobby(player_id),
        player_id,
        ["SteelMan", "Fireworks Mk. 1"],
    )

    garage = asyncio.run(garage_manager.get_profile(player_id))
    known_keys = {part.catalog_key for part in garage.owned_parts}

    random_values = iter((0.0, 0.95, 0.10))
    monkeypatch.setattr("src.garage.random.random", lambda: next(random_values))
    monkeypatch.setattr("src.garage.random.choice", lambda seq: seq[0])

    reward = roll_match_reward(garage, is_winner=True)

    assert reward.awarded_part is not None
    assert reward.awarded_part.affix_tier == 2
    assert reward.awarded_part.catalog_key in known_keys


def test_garage_shows_xp_level_and_pending_skill_choice():
    player_id = str(uuid4())
    connect_player(create_lobby(player_id), player_id, ["SteelMan", "Fireworks Mk. 1"])

    garage = asyncio.run(garage_manager.get_profile(player_id))
    progression = garage.award_xp(100)
    asyncio.run(garage_manager.save_profile(garage))

    assert progression.level_after == 2
    state = client.get(f"/garages/{player_id}").json()
    assert state["xp"] == 100
    assert state["level"] == 2
    assert state["owned_skills"] == []
    assert len(state["pending_skill_choices"]) == 1
    assert state["pending_skill_choices"][0]["level"] == 2
    assert [
        skill["skill_key"] for skill in state["pending_skill_choices"][0]["options"]
    ] == [
        "accurate_shot",
        "heavy_strike",
    ]


def test_skill_choice_is_saved_and_used_when_match_starts():
    player_id = str(uuid4())
    lobby_id = create_lobby(player_id)
    connect_player(lobby_id, player_id, ["SteelMan", "Fireworks Mk. 1"])

    garage = asyncio.run(garage_manager.get_profile(player_id))
    garage.award_xp(250)
    asyncio.run(garage_manager.save_profile(garage))

    response = client.post(
        "/garages/choose_skill",
        json={"player_id": player_id, "skill_key": "accurate_shot"},
    )
    assert response.status_code == 200
    response = client.post(
        "/garages/choose_skill",
        json={"player_id": player_id, "skill_key": "combat_impulse"},
    )
    assert response.status_code == 200
    chosen_state = response.json()
    assert [skill["skill_key"] for skill in chosen_state["owned_skills"]] == [
        "accurate_shot",
        "combat_impulse",
    ]
    assert chosen_state["pending_skill_choices"] == []

    start_response = client.post(
        "/start_game", json={"lobby_id": lobby_id, "host_player_id": player_id}
    )
    assert start_response.status_code == 200
    assert start_response.json()["result"] is True

    lobby = lobby_manager.get_lobby(lobby_id)
    actor_ids = lobby.participants[player_id].actor_ids
    for actor_id in actor_ids:
        assert [skill.skill_key for skill in lobby.players[actor_id].skills] == [
            "accurate_shot",
            "combat_impulse",
        ]


def test_finalize_match_rewards_awards_winner_xp(monkeypatch):
    player_id = str(uuid4())
    lobby_id = create_lobby(player_id)
    connect_player(lobby_id, player_id, ["SteelMan", "Fireworks Mk. 1"])

    client.post("/start_game", json={"lobby_id": lobby_id, "host_player_id": player_id})
    lobby = lobby_manager.get_lobby(lobby_id)
    lobby.game.winner = 1
    events = []

    async def collect_event(event, receiver_player_ids=None):
        events.append((event, receiver_player_ids))

    lobby.broadcast_game_event = collect_event
    monkeypatch.setattr("src.garage.random.random", lambda: 0.0)
    monkeypatch.setattr("src.garage.weighted_roll_int", lambda values: 0)

    asyncio.run(lobby.finalize_match_rewards())

    garage = asyncio.run(garage_manager.get_profile(player_id))
    assert garage.xp == 70
    assert garage.metrics.matches_finished == 1
    assert len(garage.owned_parts) == 9

    # Имитируем повторный вызов после потери процесса: in-memory флаг сброшен.
    lobby.game.rewards_granted = False
    asyncio.run(lobby.finalize_match_rewards())
    reloaded = asyncio.run(GarageManager().get_profile(player_id))
    assert reloaded.xp == 70
    assert reloaded.metrics.matches_finished == 1
    assert len(reloaded.owned_parts) == 9

    async def reward_count():
        async with get_session_factory()() as session:
            return await session.get(
                MatchRewardRecord, (lobby.game.id, reloaded.player_id)
            )

    reward_record = asyncio.run(reward_count())
    assert reward_record is not None
    assert reward_record.part_id in {part.id for part in reloaded.owned_parts}
    match_result = next(event for event, _ in events if event.type == "match_result")
    assert match_result.match_id == str(lobby.game.id)
    assert match_result.winner == 1
    assert match_result.xp_awarded == 70
    assert match_result.loot_part is not None


def test_database_rejects_foreign_wrong_slot_and_duplicate_equipment():
    first_id = str(uuid4())
    second_id = str(uuid4())
    for player_id in (first_id, second_id):
        connect_player(
            create_lobby(player_id),
            player_id,
            ["SteelMan", "Fireworks Mk. 1"],
        )
    first = asyncio.run(garage_manager.get_profile(first_id))
    second = asyncio.run(garage_manager.get_profile(second_id))
    first_loadout = first.loadouts[0]
    second_loadout = first.loadouts[1]

    async def replace_torso(loadout_id, part_id):
        async with get_session_factory()() as session:
            async with session.begin():
                await session.execute(
                    update(LoadoutPartRecord)
                    .where(
                        LoadoutPartRecord.loadout_id == loadout_id,
                        LoadoutPartRecord.slot == "torso",
                    )
                    .values(part_id=part_id)
                )

    with pytest.raises(IntegrityError):
        asyncio.run(
            replace_torso(
                first_loadout.id,
                second.loadouts[0].equipped_part_ids["torso"],
            )
        )
    with pytest.raises(IntegrityError):
        asyncio.run(
            replace_torso(first_loadout.id, first_loadout.equipped_part_ids["arms"])
        )
    with pytest.raises(IntegrityError):
        asyncio.run(
            replace_torso(second_loadout.id, first_loadout.equipped_part_ids["torso"])
        )
    reloaded = asyncio.run(GarageManager().get_profile(first_id))
    assert reloaded.loadouts[0].equipped_part_ids == first_loadout.equipped_part_ids
    assert reloaded.loadouts[1].equipped_part_ids == second_loadout.equipped_part_ids


def test_parallel_skill_choice_consumes_one_pending_choice():
    player_id = str(uuid4())
    connect_player(create_lobby(player_id), player_id, ["SteelMan", "Fireworks Mk. 1"])

    async def scenario():
        manager = GarageManager()
        profile = await manager.get_profile(player_id)
        profile.award_xp(100)
        await manager.save_profile(profile)
        results = await asyncio.gather(
            manager.choose_garage_skill(player_id, "accurate_shot"),
            manager.choose_garage_skill(player_id, "heavy_strike"),
            return_exceptions=True,
        )
        assert sum(isinstance(result, ValueError) for result in results) == 1
        reloaded = await manager.get_profile(player_id)
        assert len(reloaded.owned_skill_keys) == 1
        assert reloaded.pending_skill_choices == []

    asyncio.run(scenario())


def test_loaded_profile_uses_current_database_catalogs():
    player_id = str(uuid4())
    connect_player(create_lobby(player_id), player_id, ["SteelMan", "Fireworks Mk. 1"])

    async def scenario():
        async with get_session_factory()() as session:
            try:
                part_row = await session.get(PartCatalogRecord, "steelman_torso")
                skill_row = await session.get(SkillCatalogRecord, "accurate_shot")
                part_row.health += 30
                skill_row.name = "Проверка каталога"
                await session.flush()

                profile = await load_profile(session, player_id)
                torso = profile.equipped_part(profile.loadouts[0], "torso")
                assert torso.health == part_row.health
                profile.award_xp(100)
                options = profile.get_pending_skill_options()[0][1]
                assert options[0].name == "Проверка каталога"
            finally:
                await session.rollback()

    asyncio.run(scenario())
