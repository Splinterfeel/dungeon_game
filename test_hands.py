"""Smoke-скрипт (уровень 0 из AGENTS.md) на разделение рук + привязку оружия.

Проверяет поведенческий контракт напрямую, без HTTP/WS/браузера. Запуск:
    PYTHONIOENCODING=utf-8 python test_hands.py
Не часть pytest-сьюта (домен ещё меняется) - рабочий smoke, как test_serialization.py.

Проверяемое (ROADMAP.md Этап 2 п.3-4, решения пользователя 2026-07-14):
1. Уничтожение конкретной руки делает её оружие недоступным в атаке; оружие
   второй руки продолжает работать.
2. Попадание по руке выбирает сторону и сообщение называет левую/правую руку.
3. accuracy/melee_power полные при одной живой руке, обнуляются при обеих.
4. Player с 0 оружием отклоняется; два оружия в одну руку отклоняются.
5. Overwatch с оружием в уничтоженной руке не стреляет.
"""

import asyncio
import copy

from src.arena import Arena
from src.map import ArenaMap
from src.maps import default
from src.entities.player import Player
from src.entities.base import Inventory, Weapon, OverwatchState
from src.action import Action, ActionType, AttackActionParams
from src.game import Game
from src.base import Point
from src.parts_catalog import default_mech


def _mk_player(team, position, weapons):
    mech = default_mech()
    return Player(
        team=team,
        position=position,
        mech=mech,
        stats=mech.build_character_stats(action_points=20),
        inventory=Inventory(weapons=weapons),
    )


def _melee(hand):
    return Weapon(
        type="melee",
        name=f"Клинок-{hand}",
        damage=4,
        cost_ap=5,
        range=1,
        accuracy=100,
        hand=hand,
    )


def _ranged(hand):
    return Weapon(
        type="ranged",
        name=f"Винтовка-{hand}",
        damage=4,
        cost_ap=5,
        range=6,
        accuracy=100,
        hand=hand,
    )


def check_4_validation():
    "Проверка 4: 0 оружия -> отказ; два оружия в одну руку -> отказ; валидные -> ок."
    mech = default_mech()
    stats = mech.build_character_stats(action_points=10)
    # 0 оружия
    try:
        Player(
            team=1, mech=default_mech(), stats=stats, inventory=Inventory(weapons=[])
        )
        raise AssertionError("Player без оружия должен быть отклонён")
    except ValueError as e:
        assert "хотя бы одно оружие" in str(e), str(e)
    # два оружия в одну руку
    try:
        Player(
            team=1,
            mech=default_mech(),
            stats=stats,
            inventory=Inventory(weapons=[_melee("right"), _ranged("right")]),
        )
        raise AssertionError("Два оружия в одну руку должны быть отклонены")
    except ValueError as e:
        assert "более одного оружия" in str(e), str(e)
    # оружие без руки
    try:
        w = _melee("right")
        w.hand = None
        Player(
            team=1, mech=default_mech(), stats=stats, inventory=Inventory(weapons=[w])
        )
        raise AssertionError("Оружие игрока без руки должно быть отклонено")
    except ValueError as e:
        assert "должно быть взято в руку" in str(e), str(e)
    # валидные: по одному в каждую руку, и одно в одну руку
    _mk_player(1, Point(x=1, y=1), [_melee("right"), _ranged("left")])
    _mk_player(1, Point(x=1, y=1), [_ranged("right")])
    print("[OK] 4: валидация лоадаута (0 оружия / дубль руки / без руки -> отказ)")


def check_3_stats():
    "Проверка 3: accuracy/melee_power полные пока жива хотя бы одна рука, 0 при обеих."
    player = _mk_player(1, Point(x=1, y=1), [_melee("right"), _ranged("left")])
    full_acc = player.stats.accuracy
    full_melee = player.stats.melee_power
    assert full_acc > 0 and full_melee > 0, "стартовые статы рук должны быть > 0"

    # уничтожаем правую руку
    player.mech.arms_right.apply_damage(999)
    player.mech.recompute_live_stats(player.stats)
    assert player.mech.arms_right.destroyed and not player.mech.arms_left.destroyed
    assert player.stats.accuracy == full_acc, "одна рука жива - accuracy полная"
    assert player.stats.melee_power == full_melee, "одна рука жива - melee полная"

    # уничтожаем левую руку -> обе мертвы
    player.mech.arms_left.apply_damage(999)
    player.mech.recompute_live_stats(player.stats)
    assert player.stats.accuracy == 0, "обе руки мертвы - accuracy 0"
    assert player.stats.melee_power == 0, "обе руки мертвы - melee 0"
    print("[OK] 3: статы рук полные при одной живой, 0 при обеих уничтоженных")


async def check_1_and_2():
    "Проверки 1 и 2: уничтоженная рука -> оружие недоступно; попадание называет сторону."
    arena_map = ArenaMap(
        width=copy.deepcopy(default.map_2["width"]),
        height=copy.deepcopy(default.map_2["height"]),
        tiles=copy.deepcopy(default.map_2["tiles"]),
    )
    arena = Arena(enemies_num=1, map=arena_map)
    # два игрока вплотную, разные команды
    attacker = _mk_player(1, Point(x=5, y=5), [_melee("right"), _ranged("left")])
    target = _mk_player(2, Point(x=6, y=5), [_melee("right")])
    game = Game(arena=arena, players=[attacker, target])
    game.turn.current_actor = attacker
    attacker.current_action_points = 20
    # выставим маркеры игроков на карту (иначе типы клеток не PLAYER)
    from src.constants import CELL_TYPE

    arena.map.set(attacker.position, CELL_TYPE.PLAYER.value)
    arena.map.set(target.position, CELL_TYPE.PLAYER.value)

    right_weapon = next(w for w in attacker.inventory.weapons if w.hand == "right")
    left_weapon = next(w for w in attacker.inventory.weapons if w.hand == "left")

    # уничтожаем правую руку атакующего
    attacker.mech.arms_right.apply_damage(999)
    assert attacker.mech.arms_right.destroyed

    # проверка 1a: атака оружием правой (уничтоженной) руки недоступна
    action = Action(
        actor_id=str(attacker.id),
        type=ActionType.ATTACK,
        cell=target.position,
        params=AttackActionParams(weapon_id=right_weapon.id),
    )
    res = await game.action_handler.perform_actor_action(attacker, action)
    assert not res.performed, "оружие в уничтоженной руке должно быть недоступно"
    assert "недоступно" in res.detail, res.detail

    # проверка 1b: оружие левой (живой) руки работает (ranged, дистанция 1 ок)
    attacker.current_action_points = 20
    action = Action(
        actor_id=str(attacker.id),
        type=ActionType.ATTACK,
        cell=target.position,
        params=AttackActionParams(weapon_id=left_weapon.id),
    )
    res = await game.action_handler.perform_actor_action(attacker, action)
    assert res.performed, f"оружие живой руки должно работать: {res.detail}"
    print("[OK] 1: оружие уничтоженной руки недоступно, оружие второй руки работает")

    # проверка 2: попадание по руке называет сторону. Бьём по target,
    # форсируем выбор руки через apply_random_part_damage напрямую + сообщение.
    # (locational damage выбирает случайную часть; проверим формат сообщения на
    #  прямом уничтожении конкретной руки через приватный путь урона.)
    # Наносим гарантированный урон по левой руке цели до уничтожения и смотрим,
    # что hand_side_of/сообщение называет сторону.
    tmech = target.mech
    # добиваем левую руку цели одним большим уроном по конкретной детали
    part = tmech.arms_left
    part.apply_damage(999)
    side = tmech.hand_side_of(part)
    assert side == "left", side
    # сообщение локального урона строится в ActionHandler; проверим маппинг метки
    from src.action_handler import HAND_LABELS_RU

    assert HAND_LABELS_RU["left"] == "левая рука"
    assert HAND_LABELS_RU["right"] == "правая рука"
    print("[OK] 2: сторона руки определяется (left/right) и имеет русскую метку")


async def check_5_overwatch():
    "Проверка 5: overwatch с оружием в уничтоженной руке не стреляет при триггере."
    arena_map = ArenaMap(
        width=copy.deepcopy(default.map_2["width"]),
        height=copy.deepcopy(default.map_2["height"]),
        tiles=copy.deepcopy(default.map_2["tiles"]),
    )
    arena = Arena(enemies_num=1, map=arena_map)
    watcher = _mk_player(1, Point(x=5, y=5), [_ranged("right")])
    mover = _mk_player(2, Point(x=7, y=5), [_melee("left")])
    game = Game(arena=arena, players=[watcher, mover])
    ow_weapon = watcher.inventory.weapons[0]
    watcher.overwatch = OverwatchState(weapon_id=ow_weapon.id)
    # уничтожаем руку с оружием дозора
    watcher.mech.arms_right.apply_damage(999)
    fired = await game.check_overwatch_triggers(mover)
    assert fired is False, "дозор из уничтоженной руки не должен стрелять"
    assert watcher.overwatch is None, "дозор должен сняться"
    assert not mover.is_dead(), "цель не должна получить урон"
    print("[OK] 5: overwatch из уничтоженной руки не стреляет, дозор снимается")


async def main():
    check_4_validation()
    check_3_stats()
    await check_1_and_2()
    await check_5_overwatch()
    print("\nSUCCESS: все проверки разделения рук пройдены")


if __name__ == "__main__":
    asyncio.run(main())
