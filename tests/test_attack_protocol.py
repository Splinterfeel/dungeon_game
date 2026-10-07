import asyncio
from uuid import UUID

import pytest

from src.action import Action, ActionType, AttackActionParams
from src.base import Point
from src.combat import AttackKind
from src.entities.base import OverwatchState, WeaponType
from src.entities.enemy import build_default_enemy
from src.skills_catalog import Skills
from tests.test_movement_protocol import make_game, make_lobby, make_player, move_action


def attack_events(socket):
    return [
        message for message in socket.messages if message["type"] == "actor_attacked"
    ]


def prepare_weapon(actor, monkeypatch, hit=True, damage=70):
    weapon = actor.inventory.weapons[0]
    weapon.range = 20
    actor.stats.view_distance = 20
    monkeypatch.setattr(
        "src.entities.base.Weapon.check_hit", lambda *args, **kwargs: hit
    )
    monkeypatch.setattr("src.entities.base.Weapon.roll_damage", lambda *args: damage)
    return weapon


@pytest.mark.parametrize(
    "skill,kind,weapon_type",
    [
        (Skills.ACCURATE_SHOT, AttackKind.REGULAR, WeaponType.RANGED),
        (Skills.ACCURATE_SHOT, AttackKind.OVERWATCH, WeaponType.RANGED),
        (Skills.HEAVY_STRIKE, AttackKind.REGULAR, WeaponType.MELEE),
        (Skills.COMBAT_IMPULSE, AttackKind.REGULAR, WeaponType.RANGED),
    ],
)
def test_attack_reports_actual_skill_and_its_mech(
    monkeypatch, skill, kind, weapon_type
):
    async def scenario():
        attacker = make_player(1, 2, 2)
        target = make_player(2, 3, 2)
        attacker.name = "Мех атаки"
        target.name = "Мех защиты"
        attacker.skills = [skill.model_copy()]
        target.skills = [Skills.DODGE.model_copy()]
        target.stats.view_distance = 20
        weapon = prepare_weapon(attacker, monkeypatch)
        weapon.type = weapon_type
        monkeypatch.setattr("src.combat.random.random", lambda: 0.0)
        lobby = make_lobby(make_game([attacker, target]))

        outcome = await lobby.game.resolve_and_publish_attack(
            attacker, target, weapon, 1, kind
        )

        assert not outcome.hit
        for socket in lobby.connections.values():
            assert attack_events(socket)[0]["skill_procs"] == [
                {
                    "actor_id": str(attacker.id),
                    "actor_name": attacker.name,
                    "skill_key": skill.skill_key,
                    "skill_name": skill.name,
                },
                {
                    "actor_id": str(target.id),
                    "actor_name": target.name,
                    "skill_key": Skills.DODGE.skill_key,
                    "skill_name": Skills.DODGE.name,
                },
            ]

    asyncio.run(scenario())


@pytest.mark.parametrize("hidden_role", ["attacker", "target"])
def test_skill_proc_of_hidden_mech_is_not_disclosed(monkeypatch, hidden_role):
    async def scenario():
        attacker = make_player(1, 2, 2)
        target = make_player(2, 5, 2)
        attacker.skills = [Skills.ACCURATE_SHOT.model_copy()]
        target.skills = [Skills.DODGE.model_copy()]
        weapon = prepare_weapon(attacker, monkeypatch)
        target.stats.view_distance = 20
        observer = target if hidden_role == "attacker" else attacker
        observer.stats.view_distance = 1
        monkeypatch.setattr("src.combat.random.random", lambda: 0.0)
        lobby = make_lobby(make_game([attacker, target]))

        await lobby.game.resolve_and_publish_attack(
            attacker, target, weapon, 3, AttackKind.REGULAR
        )

        event = attack_events(lobby.connections[str(observer.owner_player_id)])[0]
        assert event[f"{hidden_role}_id"] is None
        assert len(event["skill_procs"]) == 1
        assert event["skill_procs"][0]["actor_id"] == str(observer.id)
        assert event["skill_procs"][0]["skill_key"] == observer.skills[0].skill_key

    asyncio.run(scenario())


@pytest.mark.parametrize("hit", [True, False])
def test_regular_attack_publishes_one_structured_result_before_snapshot(
    monkeypatch, hit
):
    async def scenario():
        attacker = make_player(1, 2, 2)
        target = make_player(2, 4, 2)
        target.stats.view_distance = 20
        weapon = prepare_weapon(attacker, monkeypatch, hit)
        lobby = make_lobby(make_game([attacker, target]))
        await lobby.game.prepare_actor_turn(attacker)
        action = Action(
            actor_id=str(attacker.id),
            type=ActionType.ATTACK,
            cell=target.position,
            params=AttackActionParams(weapon_id=weapon.id),
        )

        result = await lobby.game.perform_actor_action(attacker, action)
        await lobby.broadcast_game_state()

        assert result.performed
        shot_ids = set()
        for socket in lobby.connections.values():
            events = attack_events(socket)
            assert len(events) == 1
            event = events[0]
            UUID(event["attack_id"])
            shot_ids.add(event["attack_id"])
            assert event["attacker_id"] == str(attacker.id)
            assert event["target_id"] == str(target.id)
            assert event["from_cell"] == {"x": 2, "y": 2}
            assert event["to_cell"] == {"x": 4, "y": 2}
            assert event["weapon_type"] == "ranged"
            assert event["kind"] == "regular"
            assert event["hit"] is hit
            assert event["damage"] == (70 if hit else 0)
            assert event["target_killed"] is False
            assert event["movement_action_id"] is None
            types = [message["type"] for message in socket.messages]
            assert types.index("actor_attacked") < types.index("state_update")
        assert len(shot_ids) == 1

    asyncio.run(scenario())


def test_rejected_attack_has_no_effect_event():
    async def scenario():
        attacker = make_player(1, 2, 2)
        target = make_player(2, 4, 2)
        lobby = make_lobby(make_game([attacker, target]))
        await lobby.game.prepare_actor_turn(attacker)
        action = Action(
            actor_id=str(attacker.id), type=ActionType.ATTACK, cell=target.position
        )

        result = await lobby.game.perform_actor_action(attacker, action)

        assert not result.performed
        assert all(not attack_events(socket) for socket in lobby.connections.values())

    asyncio.run(scenario())


@pytest.mark.parametrize("lethal", [True, False])
def test_hidden_shooter_stays_hidden_even_when_last_victim_is_killed(
    monkeypatch, lethal
):
    async def scenario():
        attacker = make_player(1, 2, 2)
        target = make_player(2, 5, 2)
        target.stats.view_distance = 1
        if lethal:
            target.stats.health = 10
        weapon = prepare_weapon(attacker, monkeypatch)
        lobby = make_lobby(make_game([attacker, target]))
        await lobby.game.prepare_actor_turn(attacker)
        action = Action(
            actor_id=str(attacker.id),
            type=ActionType.ATTACK,
            cell=target.position,
            params=AttackActionParams(weapon_id=weapon.id),
        )

        result = await lobby.game.perform_actor_action(attacker, action)

        assert result.performed
        event = attack_events(lobby.connections[str(target.owner_player_id)])[0]
        assert event["attacker_id"] is None
        assert event["from_cell"] is None
        assert event["target_id"] == str(target.id)
        assert event["to_cell"] == {"x": 5, "y": 2}
        assert event["damage"] == 70
        assert event["target_killed"] is lethal
        assert target.is_dead() is lethal
        if lethal:
            assert target not in lobby.game.players

    asyncio.run(scenario())


def test_unseen_target_has_no_identity_position_damage_or_kill_disclosure(monkeypatch):
    async def scenario():
        attacker = make_player(1, 2, 2)
        target = make_player(2, 5, 2)
        weapon = prepare_weapon(attacker, monkeypatch)
        attacker.stats.view_distance = 1
        target.stats.health = 10
        lobby = make_lobby(make_game([attacker, target]))

        await lobby.game.resolve_and_publish_attack(
            attacker, target, weapon, 3, AttackKind.REGULAR
        )

        event = attack_events(lobby.connections[str(attacker.owner_player_id)])[0]
        assert event["attacker_id"] == str(attacker.id)
        assert event["target_id"] is None
        assert event["to_cell"] is None
        assert event["damage"] == 0
        assert event["target_killed"] is False
        assert target.is_dead()

    asyncio.run(scenario())


def test_team_that_sees_neither_endpoint_gets_no_attack_event(monkeypatch):
    async def scenario():
        observer = make_player(1, 1, 1)
        observer.stats.view_distance = 1
        attacker = make_player(2, 8, 4)
        target = build_default_enemy(10, 10)
        target.position = Point(x=9, y=4)
        weapon = prepare_weapon(attacker, monkeypatch)
        lobby = make_lobby(make_game([observer, attacker], [target]))
        await lobby.game.prepare_actor_turn(attacker)
        action = Action(
            actor_id=str(attacker.id),
            type=ActionType.ATTACK,
            cell=target.position,
            params=AttackActionParams(weapon_id=weapon.id),
        )

        result = await lobby.game.perform_actor_action(attacker, action)

        assert result.performed
        assert not attack_events(lobby.connections[str(observer.owner_player_id)])
        assert len(attack_events(lobby.connections[str(attacker.owner_player_id)])) == 1

    asyncio.run(scenario())


def test_overwatch_attack_records_actual_cell_and_correlates_completed_route(
    monkeypatch,
):
    async def scenario():
        mover = make_player(1, 1, 1)
        watcher = make_player(2, 4, 3)
        weapon = prepare_weapon(watcher, monkeypatch, damage=9990)
        weapon.range = 2
        mover.stats.health = 10
        lobby = make_lobby(make_game([mover, watcher]))
        await lobby.game.prepare_actor_turn(mover)
        watcher.overwatch = OverwatchState(weapon_id=weapon.id)
        action = move_action(mover, 6)

        result = await lobby.game.perform_actor_action(mover, action)

        assert result.performed
        assert mover.is_dead()
        socket = lobby.connections[str(mover.owner_player_id)]
        event = attack_events(socket)[0]
        route = next(
            message for message in socket.messages if message["type"] == "actor_moved"
        )
        assert event["kind"] == "overwatch"
        assert event["movement_action_id"] == str(action.id) == route["action_id"]
        assert event["to_cell"] == {"x": 4, "y": 1}
        assert route["paths"][0][-1] == event["to_cell"]
        assert route["paths"][0][0] == {"x": 1, "y": 1}
        assert event["target_killed"]
        assert watcher.overwatch is None

    asyncio.run(scenario())


def test_neutral_enemy_melee_attack_uses_same_effect_protocol(monkeypatch):
    async def scenario():
        victim = make_player(1, 2, 2)
        opponent = make_player(2, 10, 6)
        enemy = build_default_enemy(10, 10)
        enemy.position = Point(x=3, y=2)
        weapon = prepare_weapon(enemy, monkeypatch)
        weapon.type = WeaponType.MELEE
        lobby = make_lobby(make_game([victim, opponent], [enemy]))
        await lobby.game.prepare_actor_turn(enemy)
        action = Action(
            actor_id=str(enemy.id),
            type=ActionType.ATTACK,
            cell=victim.position,
            params=AttackActionParams(weapon_id=weapon.id),
        )

        result = await lobby.game.perform_actor_action(enemy, action)

        assert result.performed
        event = attack_events(lobby.connections[str(victim.owner_player_id)])[0]
        assert event["attacker_id"] == str(enemy.id)
        assert event["weapon_type"] == "melee"
        assert event["kind"] == "regular"
        assert event["hit"]

    asyncio.run(scenario())
