"""Регресс на "залипающие" клетки карты.

Баг был в том, что Arena._initial_map хранил не только террейн (стены/пол),
но и маркеры динамических сущностей (враги `E`). reset_map_cell
восстанавливает по _initial_map клетку, которую покидает актор, поэтому
бывшая клетка врага "восстанавливалась" как занятая, хотя по факту
там уже пусто. Фикс: _initial_map хранит только террейн
(ArenaMap.keep_only_terrain, вызывается в Arena.__save_initial_map).

Проверяем поведенческий контракт напрямую (уровень 0 из AGENTS.md), без
HTTP/WS/браузера. Запускается и как `python test_map_cell_release.py`, и под
pytest.
"""

import copy

from src.arena import Arena
from src.map import ArenaMap
from src.maps import default
from src.entities.player import Player
from src.entities.base import Inventory, Weapon
from src.game import Game
from src.base import Point
from src.parts_catalog import default_mech


def _neighbors(p: Point) -> list[Point]:
    return [
        Point(x=p.x + dx, y=p.y + dy) for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]
    ]


def _build_game() -> tuple[Game, Arena, Player]:
    arena_map = ArenaMap(
        width=copy.deepcopy(default.map_2["width"]),
        height=copy.deepcopy(default.map_2["height"]),
        tiles=copy.deepcopy(default.map_2["tiles"]),
    )
    arena = Arena(enemies_num=2, map=arena_map)
    mech = default_mech()
    player = Player(
        team=1,
        mech=mech,
        stats=mech.build_character_stats(action_points=10),
        # у игрока теперь обязательно хотя бы одно оружие в руке (ROADMAP.md Этап 2 п.3-4)
        inventory=Inventory(
            weapons=[
                Weapon(
                    type="melee",
                    name="Тестовый клинок",
                    damage=3,
                    cost_ap=5,
                    range=1,
                    accuracy=90,
                    hand="right",
                )
            ]
        ),
    )
    game = Game(arena=arena, players=[player])
    return game, arena, player


def test_enemy_vacated_cell_is_free():
    """Клетка, которую покинул враг, должна снова стать свободной."""
    game, arena, _ = _build_game()
    enemy = arena.enemies[0]
    start = enemy.position
    target = next(c for c in _neighbors(start) if arena.map.is_free(c))

    game.move_actor(enemy, target)

    assert arena.map.is_free(start), (
        f"Клетка {start}, покинутая врагом, должна быть свободной, "
        f"а на карте {arena.map.get(start)!r}"
    )


def test_initial_map_keeps_terrain():
    """_initial_map хранит только террейн: стены сохранены, сущностей нет."""
    _, arena, _ = _build_game()
    walls = 0
    for x in range(arena.map.width):
        for y in range(arena.map.height):
            value = arena._initial_map.get(Point(x=x, y=y))
            assert value in (
                "   ",
                " # ",
            ), f"В _initial_map попал не террейн: {value!r}"
            if value == " # ":
                walls += 1
    assert walls > 0, "В _initial_map должны сохраниться стены"


if __name__ == "__main__":
    test_enemy_vacated_cell_is_free()
    test_initial_map_keeps_terrain()
    print("OK: клетки корректно освобождаются, _initial_map хранит только террейн")
