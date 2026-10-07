import asyncio
import copy

from src.action import Action, ActionType, AttackActionParams
from src.arena import Arena
from src.base import Point
from src.constants import CELL_TYPE
from src.entities.base import Inventory, Weapon
from src.entities.player import Player
from src.game import Game
from src.map import ArenaMap
from src.maps import default
from src.mech.catalog import default_mech
from src.skills_catalog import Skills


def build_players(skills_a=None, skills_b=None, weapon_a=None, weapon_b=None):
    arena_map = ArenaMap(
        width=copy.deepcopy(default.map_2["width"]),
        height=copy.deepcopy(default.map_2["height"]),
        tiles=copy.deepcopy(default.map_2["tiles"]),
    )
    arena = Arena(map=arena_map)
    player_a = Player(
        team=1,
        position=Point(x=4, y=4),
        mech=default_mech(),
        stats=default_mech().build_character_stats(action_points=10),
        inventory=Inventory(
            weapons=[
                weapon_a
                or Weapon(
                    type="ranged",
                    name="Тестовый карабин",
                    damage=50,
                    cost_ap=5,
                    range=5,
                    accuracy=90,
                    hand="right",
                )
            ]
        ),
        skills=skills_a or [],
    )
    player_b = Player(
        team=2,
        position=Point(x=4, y=6),
        mech=default_mech(),
        stats=default_mech().build_character_stats(action_points=10),
        inventory=Inventory(
            weapons=[
                weapon_b
                or Weapon(
                    type="ranged",
                    name="Тестовый карабин",
                    damage=50,
                    cost_ap=5,
                    range=5,
                    accuracy=90,
                    hand="right",
                )
            ]
        ),
        skills=skills_b or [],
    )
    arena.map.set(player_a.position, CELL_TYPE.PLAYER.value)
    arena.map.set(player_b.position, CELL_TYPE.PLAYER.value)
    game = Game(arena=arena, players=[player_a, player_b], enemies=[])
    game.turn.current_actor = player_a
    player_a.current_action_points = 10
    return game, player_a, player_b


def test_accurate_shot_can_turn_miss_into_hit(monkeypatch):
    async def scenario():
        game, attacker, target = build_players(
            skills_a=[Skills.ACCURATE_SHOT.model_copy()]
        )
        weapon = attacker.inventory.weapons[0]
        monkeypatch.setattr(
            "src.entities.base.Weapon.check_hit",
            lambda self, actor_stats, distance: actor_stats.accuracy >= 100,
        )
        monkeypatch.setattr("src.entities.base.Weapon.roll_damage", lambda self: 50)
        monkeypatch.setattr("src.combat.random.random", lambda: 0.0)
        action = Action(
            actor_id=str(attacker.id),
            type=ActionType.ATTACK,
            cell=target.position,
            params=AttackActionParams(weapon_id=weapon.id),
        )
        result = await game.perform_actor_action(attacker, action)
        assert result.performed
        assert "Точный выстрел" in result.detail
        assert target.stats.health == target.stats.max_health - 50

    asyncio.run(scenario())


def test_heavy_strike_adds_bonus_melee_damage(monkeypatch):
    async def scenario():
        weapon = Weapon(
            type="melee",
            name="Тестовый клинок",
            damage=50,
            cost_ap=5,
            range=1,
            accuracy=90,
            hand="right",
        )
        game, attacker, target = build_players(
            skills_a=[Skills.HEAVY_STRIKE.model_copy()],
            weapon_a=weapon,
        )
        target.position = Point(x=4, y=5)
        game.arena.map.set(target.position, CELL_TYPE.PLAYER.value)
        monkeypatch.setattr(
            "src.entities.base.Weapon.check_hit", lambda *args, **kwargs: True
        )
        monkeypatch.setattr("src.entities.base.Weapon.roll_damage", lambda self: 50)
        monkeypatch.setattr("src.combat.random.random", lambda: 0.0)
        action = Action(
            actor_id=str(attacker.id),
            type=ActionType.ATTACK,
            cell=target.position,
            params=AttackActionParams(weapon_id=weapon.id),
        )
        result = await game.perform_actor_action(attacker, action)
        assert result.performed
        assert "Усиленный удар" in result.detail
        assert target.stats.health == target.stats.max_health - 100

    asyncio.run(scenario())


def test_combat_impulse_refunds_action_points(monkeypatch):
    async def scenario():
        game, attacker, target = build_players(
            skills_a=[Skills.COMBAT_IMPULSE.model_copy()]
        )
        weapon = attacker.inventory.weapons[0]
        monkeypatch.setattr(
            "src.entities.base.Weapon.check_hit", lambda *args, **kwargs: True
        )
        monkeypatch.setattr("src.entities.base.Weapon.roll_damage", lambda self: 50)
        monkeypatch.setattr("src.combat.random.random", lambda: 0.0)
        action = Action(
            actor_id=str(attacker.id),
            type=ActionType.ATTACK,
            cell=target.position,
            params=AttackActionParams(weapon_id=weapon.id),
        )
        result = await game.perform_actor_action(attacker, action)
        assert result.action_cost == 0
        assert attacker.current_action_points == 10
        assert "Боевой импульс" in result.detail

    asyncio.run(scenario())


def test_combat_impulse_cannot_start_attack_without_base_action_points(monkeypatch):
    async def scenario():
        game, attacker, target = build_players(
            skills_a=[Skills.COMBAT_IMPULSE.model_copy()]
        )
        weapon = attacker.inventory.weapons[0]
        attacker.current_action_points = 0

        def unexpected_rng_call():
            raise AssertionError("RNG не должен запускаться для недоступной атаки")

        monkeypatch.setattr("src.combat.random.random", unexpected_rng_call)
        action = Action(
            actor_id=str(attacker.id),
            type=ActionType.ATTACK,
            cell=target.position,
            params=AttackActionParams(weapon_id=weapon.id),
        )

        result = await game.perform_actor_action(attacker, action)

        assert not result.performed
        assert target.stats.health == target.stats.max_health

    asyncio.run(scenario())


def test_attack_without_weapon_params_is_rejected():
    async def scenario():
        game, attacker, target = build_players()
        action = Action(
            actor_id=str(attacker.id),
            type=ActionType.ATTACK,
            cell=target.position,
        )

        result = await game.perform_actor_action(attacker, action)

        assert not result.performed
        assert "не указано оружие" in result.detail

    asyncio.run(scenario())


def test_melee_attack_reaches_diagonally_adjacent_cell(monkeypatch):
    async def scenario():
        weapon = Weapon(
            type="melee",
            name="Тестовый клинок",
            damage=50,
            cost_ap=5,
            range=1,
            accuracy=90,
            hand="right",
        )
        game, attacker, target = build_players(weapon_a=weapon)
        game.arena.reset_map_cell(target.position)
        target.position = Point(x=5, y=5)
        game.arena.map.set(target.position, CELL_TYPE.PLAYER.value)
        monkeypatch.setattr(
            "src.entities.base.Weapon.check_hit", lambda *args, **kwargs: True
        )
        monkeypatch.setattr("src.entities.base.Weapon.roll_damage", lambda self: 50)
        action = Action(
            actor_id=str(attacker.id),
            type=ActionType.ATTACK,
            cell=target.position,
            params=AttackActionParams(weapon_id=weapon.id),
        )

        result = await game.perform_actor_action(attacker, action)

        assert result.performed
        assert target.stats.health < target.stats.max_health

    asyncio.run(scenario())


def test_dodge_avoids_regular_attack(monkeypatch):
    async def scenario():
        game, attacker, target = build_players(skills_b=[Skills.DODGE.model_copy()])
        weapon = attacker.inventory.weapons[0]
        monkeypatch.setattr(
            "src.entities.base.Weapon.check_hit", lambda *args, **kwargs: True
        )
        monkeypatch.setattr("src.entities.base.Weapon.roll_damage", lambda self: 50)
        monkeypatch.setattr("src.combat.random.random", lambda: 0.0)
        action = Action(
            actor_id=str(attacker.id),
            type=ActionType.ATTACK,
            cell=target.position,
            params=AttackActionParams(weapon_id=weapon.id),
        )
        result = await game.perform_actor_action(attacker, action)
        assert result.performed
        assert "Уклонение" in result.detail
        assert target.stats.health == target.stats.max_health

    asyncio.run(scenario())


def test_dodge_avoids_overwatch_shot(monkeypatch):
    async def scenario():
        game, watcher, mover = build_players(skills_b=[Skills.DODGE.model_copy()])
        weapon = watcher.inventory.weapons[0]
        monkeypatch.setattr(
            "src.entities.base.Weapon.check_hit", lambda *args, **kwargs: True
        )
        monkeypatch.setattr("src.entities.base.Weapon.roll_damage", lambda self: 50)
        monkeypatch.setattr("src.combat.random.random", lambda: 0.0)
        await game._fire_overwatch_shot(watcher, weapon, mover)
        assert mover.stats.health == mover.stats.max_health

    asyncio.run(scenario())


def test_overwatch_hit_applies_locational_damage(monkeypatch):
    async def scenario():
        game, watcher, mover = build_players()
        weapon = watcher.inventory.weapons[0]
        parts = [
            mover.mech.torso,
            mover.mech.legs,
            mover.mech.head,
            mover.mech.arms_left,
            mover.mech.arms_right,
        ]
        part_health_before = sum(part.current_health for part in parts)
        monkeypatch.setattr(
            "src.entities.base.Weapon.check_hit", lambda *args, **kwargs: True
        )
        monkeypatch.setattr("src.entities.base.Weapon.roll_damage", lambda self: 50)

        await game._fire_overwatch_shot(watcher, weapon, mover)

        part_health_after = sum(part.current_health for part in parts)
        assert part_health_before - part_health_after == 50

    asyncio.run(scenario())


def test_only_one_skill_procs_per_actor_during_regular_attack(monkeypatch):
    async def scenario():
        game, attacker, target = build_players(
            skills_a=[
                Skills.ACCURATE_SHOT.model_copy(),
                Skills.COMBAT_IMPULSE.model_copy(),
            ],
            skills_b=[Skills.DODGE.model_copy()],
        )
        weapon = attacker.inventory.weapons[0]
        monkeypatch.setattr(
            "src.entities.base.Weapon.check_hit", lambda *args, **kwargs: True
        )
        monkeypatch.setattr("src.entities.base.Weapon.roll_damage", lambda self: 50)
        monkeypatch.setattr("src.combat.random.random", lambda: 0.0)
        action = Action(
            actor_id=str(attacker.id),
            type=ActionType.ATTACK,
            cell=target.position,
            params=AttackActionParams(weapon_id=weapon.id),
        )
        result = await game.perform_actor_action(attacker, action)
        assert "Точный выстрел" in result.detail
        assert "Боевой импульс" not in result.detail
        assert "Уклонение" in result.detail
        assert result.action_cost == weapon.cost_ap
        assert target.stats.health == target.stats.max_health

    asyncio.run(scenario())


def test_second_attack_same_turn_can_proc_again(monkeypatch):
    async def scenario():
        game, attacker, target = build_players(
            skills_a=[Skills.ACCURATE_SHOT.model_copy()]
        )
        weapon = attacker.inventory.weapons[0]
        attacker.current_action_points = 10
        monkeypatch.setattr(
            "src.entities.base.Weapon.check_hit", lambda *args, **kwargs: True
        )
        monkeypatch.setattr("src.entities.base.Weapon.roll_damage", lambda self: 50)
        monkeypatch.setattr("src.combat.random.random", lambda: 0.0)
        action = Action(
            actor_id=str(attacker.id),
            type=ActionType.ATTACK,
            cell=target.position,
            params=AttackActionParams(weapon_id=weapon.id),
        )
        first_result = await game.perform_actor_action(attacker, action)
        second_result = await game.perform_actor_action(attacker, action)
        assert "Точный выстрел" in first_result.detail
        assert "Точный выстрел" in second_result.detail

    asyncio.run(scenario())


def test_only_one_skill_procs_per_actor_during_overwatch(monkeypatch):
    async def scenario():
        game, watcher, mover = build_players(
            skills_a=[Skills.ACCURATE_SHOT.model_copy()],
            skills_b=[Skills.DODGE.model_copy()],
        )
        weapon = watcher.inventory.weapons[0]
        monkeypatch.setattr(
            "src.entities.base.Weapon.check_hit", lambda *args, **kwargs: True
        )
        monkeypatch.setattr("src.entities.base.Weapon.roll_damage", lambda self: 50)
        monkeypatch.setattr("src.combat.random.random", lambda: 0.0)
        await game._fire_overwatch_shot(watcher, weapon, mover)
        assert mover.stats.health == mover.stats.max_health

    asyncio.run(scenario())
