"""Минимальный регресс на баг с _initial_map.

_initial_map хранил маркеры сущностей (враги/сундуки), из-за чего
reset_map_cell восстанавливал покинутую актором клетку как занятую.
Фикс: _initial_map хранит только террейн (ArenaMap.keep_only_terrain).

Проверяем поведенческий контракт напрямую: клетка, покинутая врагом,
снова свободна. Запускается и как `python`, и под pytest.
"""

import copy

from src.arena import Arena
from src.map import ArenaMap
from src.maps import default
from src.base import Point
from src.entities.player import Player
from src.entities.base import Inventory
from src.game import Game
from src.parts_catalog import default_mech


def test_enemy_vacated_cell_is_free():
    arena_map = ArenaMap(
        width=copy.deepcopy(default.map_2["width"]),
        height=copy.deepcopy(default.map_2["height"]),
        tiles=copy.deepcopy(default.map_2["tiles"]),
    )
    arena = Arena(max_chests=1, enemies_num=1, map=arena_map)
    mech = default_mech()
    player = Player(
        team=1,
        mech=mech,
        stats=mech.build_character_stats(action_points=10),
        inventory=Inventory(weapons=[]),
    )
    game = Game(arena=arena, players=[player])

    enemy = arena.enemies[0]
    start = enemy.position
    target = next(
        Point(x=start.x + dx, y=start.y + dy)
        for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]
        if arena.map.is_free(Point(x=start.x + dx, y=start.y + dy))
    )

    game.move_actor(enemy, target)

    assert arena.map.is_free(start), (
        f"Покинутая врагом клетка {start} должна быть свободной, "
        f"а на карте {arena.map.get(start)!r}"
    )


if __name__ == "__main__":
    test_enemy_vacated_cell_is_free()
    print("OK")
