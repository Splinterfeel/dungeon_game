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
from src.parts_catalog import default_mech
from src.skills_catalog import ACCURATE_SHOT, COMBAT_IMPULSE, DODGE, HEAVY_STRIKE


def build_players(skills_a=None, skills_b=None, weapon_a=None, weapon_b=None):
    arena_map = ArenaMap(
        width=copy.deepcopy(default.map_2["width"]),
        height=copy.deepcopy(default.map_2["height"]),
        tiles=copy.deepcopy(default.map_2["tiles"]),
    )
    arena = Arena(enemies_num=0, map=arena_map)
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
                    damage=5,
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
                    damage=5,
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
    game = Game(arena=arena, players=[player_a, player_b])
    game.turn.current_actor = player_a
    player_a.current_action_points = 10
    return game, player_a, player_b


def test_accurate_shot_can_turn_miss_into_hit(monkeypatch):
    async def scenario():
        game, attacker, target = build_players(skills_a=[ACCURATE_SHOT.model_copy()])
        weapon = attacker.inventory.weapons[0]
        monkeypatch.setattr(
            "src.entities.base.Weapon.check_hit",
            lambda self, actor_stats, distance: actor_stats.accuracy >= 100,
        )
        monkeypatch.setattr("src.entities.base.Weapon.roll_damage", lambda self: 5)
        monkeypatch.setattr("src.action_handler.random.random", lambda: 0.0)
        action = Action(
            actor_id=str(attacker.id),
            type=ActionType.ATTACK,
            cell=target.position,
            params=AttackActionParams(weapon_id=weapon.id),
        )
        result = await game.perform_actor_action(attacker, action)
        assert result.performed
        assert "Точный выстрел" in result.detail
        assert target.stats.health == target.stats.max_health - 5

    asyncio.run(scenario())


def test_heavy_strike_adds_bonus_melee_damage(monkeypatch):
    async def scenario():
        weapon = Weapon(
            type="melee",
            name="Тестовый клинок",
            damage=5,
            cost_ap=5,
            range=1,
            accuracy=90,
            hand="right",
        )
        game, attacker, target = build_players(
            skills_a=[HEAVY_STRIKE.model_copy()],
            weapon_a=weapon,
        )
        target.position = Point(x=4, y=5)
        game.arena.map.set(target.position, CELL_TYPE.PLAYER.value)
        monkeypatch.setattr("src.entities.base.Weapon.check_hit", lambda *args, **kwargs: True)
        monkeypatch.setattr("src.entities.base.Weapon.roll_damage", lambda self: 5)
        monkeypatch.setattr("src.action_handler.random.random", lambda: 0.0)
        action = Action(
            actor_id=str(attacker.id),
            type=ActionType.ATTACK,
            cell=target.position,
            params=AttackActionParams(weapon_id=weapon.id),
        )
        result = await game.perform_actor_action(attacker, action)
        assert result.performed
        assert "Усиленный удар" in result.detail
        assert target.stats.health == target.stats.max_health - 10

    asyncio.run(scenario())


def test_combat_impulse_refunds_action_points(monkeypatch):
    async def scenario():
        game, attacker, target = build_players(skills_a=[COMBAT_IMPULSE.model_copy()])
        weapon = attacker.inventory.weapons[0]
        monkeypatch.setattr("src.entities.base.Weapon.check_hit", lambda *args, **kwargs: True)
        monkeypatch.setattr("src.entities.base.Weapon.roll_damage", lambda self: 5)
        monkeypatch.setattr("src.action_handler.random.random", lambda: 0.0)
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


def test_dodge_avoids_regular_attack(monkeypatch):
    async def scenario():
        game, attacker, target = build_players(skills_b=[DODGE.model_copy()])
        weapon = attacker.inventory.weapons[0]
        monkeypatch.setattr("src.entities.base.Weapon.check_hit", lambda *args, **kwargs: True)
        monkeypatch.setattr("src.entities.base.Weapon.roll_damage", lambda self: 5)
        monkeypatch.setattr("src.action_handler.random.random", lambda: 0.0)
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
        game, watcher, mover = build_players(skills_b=[DODGE.model_copy()])
        weapon = watcher.inventory.weapons[0]
        monkeypatch.setattr("src.entities.base.Weapon.check_hit", lambda *args, **kwargs: True)
        monkeypatch.setattr("src.entities.base.Weapon.roll_damage", lambda self: 5)
        monkeypatch.setattr("src.game.random.random", lambda: 0.0)
        await game._fire_overwatch_shot(watcher, weapon, mover)
        assert mover.stats.health == mover.stats.max_health

    asyncio.run(scenario())


def test_only_one_skill_procs_per_actor_during_regular_attack(monkeypatch):
    async def scenario():
        game, attacker, target = build_players(
            skills_a=[ACCURATE_SHOT.model_copy(), COMBAT_IMPULSE.model_copy()],
            skills_b=[DODGE.model_copy()],
        )
        weapon = attacker.inventory.weapons[0]
        monkeypatch.setattr("src.entities.base.Weapon.check_hit", lambda *args, **kwargs: True)
        monkeypatch.setattr("src.entities.base.Weapon.roll_damage", lambda self: 5)
        monkeypatch.setattr("src.action_handler.random.random", lambda: 0.0)
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
        game, attacker, target = build_players(skills_a=[ACCURATE_SHOT.model_copy()])
        weapon = attacker.inventory.weapons[0]
        attacker.current_action_points = 10
        monkeypatch.setattr("src.entities.base.Weapon.check_hit", lambda *args, **kwargs: True)
        monkeypatch.setattr("src.entities.base.Weapon.roll_damage", lambda self: 5)
        monkeypatch.setattr("src.action_handler.random.random", lambda: 0.0)
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
            skills_a=[ACCURATE_SHOT.model_copy()],
            skills_b=[DODGE.model_copy()],
        )
        weapon = watcher.inventory.weapons[0]
        monkeypatch.setattr("src.entities.base.Weapon.check_hit", lambda *args, **kwargs: True)
        monkeypatch.setattr("src.entities.base.Weapon.roll_damage", lambda self: 5)
        monkeypatch.setattr("src.game.random.random", lambda: 0.0)
        await game._fire_overwatch_shot(watcher, weapon, mover)
        assert mover.stats.health == mover.stats.max_health

    asyncio.run(scenario())
