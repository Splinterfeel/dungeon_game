import asyncio
import typing

from src.action import (
    Action,
    ActionResult,
    ActionType,
    AttackActionParams,
    OverwatchActionParams,
)
from src.base import Point
from src.constants import CELL_TYPE
from src.entities.base import Actor, OverwatchState, Weapon
from src.entities.player import Player

if typing.TYPE_CHECKING:
    from src.game import Game


class ActionHandler:
    def __init__(self, game: "Game"):
        self.game = game

    def __apply_locational_damage(self, player: Player, damage: int) -> str:
        "Урон случайной живой части меха игрока + пересчёт живых статов; возвращает суффикс для detail"
        part = player.mech.apply_random_part_damage(damage)
        if part is None:
            return ""  # все части уже уничтожены
        player.mech.recompute_live_stats(player.stats)
        if part.destroyed:
            return f" Деталь «{part.name}» ({part.slot.value}) уничтожена!"
        return ""

    async def perform_actor_action(self, actor: Actor, action: Action) -> ActionResult:
        if self.game.turn.current_actor != actor:
            return ActionResult(
                performed=False,
                action=action,
                detail=f"{actor.name} попытался походить во время хода {self.game.turn.current_actor.name}",
            )
        # Enemy и Player приводятся к Actor
        match action.type:
            case ActionType.END_TURN:
                return await self.__perform_action_end_turn(actor=actor, action=action)
            case ActionType.MOVE:
                return await self.__perform_action_move(actor=actor, action=action)
            case ActionType.ATTACK:
                return await self.__perform_action_attack(actor=actor, action=action)
            case ActionType.OVERWATCH:
                return await self.__perform_action_overwatch(actor=actor, action=action)
            case ActionType.OPEN_CHEST:
                return await self.__perform_action_open_chest(
                    actor=actor, action=action
                )
            case ActionType.INSPECT:
                print("INSPECTING", action.cell)
                return ActionResult(action=action)
            case _:
                print("Performing unknown action", action)
                return ActionResult(action=action)

    async def __perform_action_end_turn(
        self, actor: Actor, action: Action
    ) -> ActionResult:
        if str(self.game.turn.current_actor.id) != action.actor_id:
            print(self.game.turn.current_actor.id)
            print(action.actor_id)
            print(
                detail=f"{actor.name} попытался закончить ход во время хода {self.game.turn.current_actor.name}",
            )
        return ActionResult(
            action=action,
            action_cost=30000,  # TODO пока просто завершаем ход немыслимым кол-вом AP
            detail=f"{actor.name} завершает ход",
        )

    async def __perform_action_overwatch(
        self, actor: Actor, action: Action
    ) -> ActionResult:
        if actor.overwatch is not None:
            return ActionResult(
                performed=False,
                action=action,
                detail=f"{actor.name} уже в режиме огневого дозора",
            )
        params: OverwatchActionParams = action.params
        weapon: Weapon | None = next(
            (w for w in actor.inventory.weapons if w.id == params.weapon_id),
            None,
        )
        if weapon is None:
            return ActionResult(
                performed=False,
                action=action,
                detail=f"{actor.name}, в инвентаре нет указанного оружия для огневого дозора",
            )
        if weapon.type != "ranged":
            return ActionResult(
                performed=False,
                action=action,
                detail=f"{actor.name}, огневой дозор доступен только с дальнобойным оружием",
            )
        if actor.current_action_points < weapon.cost_ap:
            return ActionResult(
                performed=False,
                action=action,
                detail=f"{actor.name}, нет очков действия для огневого дозора",
            )
        actor.overwatch = OverwatchState(weapon_id=weapon.id)
        return ActionResult(
            action=action,
            action_cost=weapon.cost_ap,
            detail=f"{actor.name} переходит в режим огневого дозора ({weapon.name})",
        )

    async def __perform_action_open_chest(
        self, actor: Actor, action: Action
    ) -> ActionResult:
        chest = next(
            (c for c in self.game.arena.chests if c.position == action.cell), None
        )
        if chest is None:
            return ActionResult(
                performed=False,
                action=action,
                detail=f"{actor.name}, в клетке {action.cell} нет сундука",
            )
        if Point.distance_chebyshev(actor.position, chest.position) > 1:
            return ActionResult(
                performed=False,
                action=action,
                detail=f"{actor.name}, сундук {action.cell} слишком далеко, чтобы его открыть",
            )
        actor.trophies.append(chest.loot)
        self.game.arena.remove_chest(chest)
        return ActionResult(
            action=action,
            detail=f"{actor.name} открывает сундук и находит: {chest.loot}",
        )

    async def __perform_action_move(self, actor: Actor, action: Action) -> ActionResult:
        if action.cell not in self.game.turn.available_moves:
            print(f"Can't move player {actor} to cell {action.cell}")
            return ActionResult(
                performed=False,
                action=action,
                detail=f"{actor.name}, нельзя переместиться в {action.cell}",
            )
        if not self.game.arena.map.is_free(action.cell):
            return ActionResult(
                performed=False,
                action=action,
                detail=f"{actor.name}, клетка {action.cell} занята, нельзя в нее переместиться",  # noqa
            )
        path = self.game.arena.map.bfs_path(
            action.cell, self.game.turn.current_actor.position
        )
        if not path:
            return ActionResult(
                performed=False,
                action=action,
                detail=f"{actor.name}, не получилось построить путь до точки {action.cell}",
            )
        total_cost = len(path) - 1
        assert total_cost > 0
        if self.game.turn.current_actor.current_action_points < total_cost:
            return ActionResult(
                performed=False,
                action=action,
                detail=f"{actor.name}, Недостаточно очков действия для перемещения в {action.cell}!",
            )
        # шагаем по пути по одной клетке, проверяя огневой дозор
        step_path = list(reversed(path))[1:]  # путь от текущей позиции к цели
        for i, step_cell in enumerate(step_path):
            self.game.move_actor(actor, step_cell)
            self.game.version += 1
            await self.game._notify_state_change()
            await asyncio.sleep(0.1)
            overwatch_fired = await self.game.check_overwatch_triggers(actor)
            if overwatch_fired and actor.is_dead():
                return ActionResult(
                    action=action,
                    action_cost=i + 1,
                    speed_spent=i + 1,
                    detail=f"{actor.name} убит огневым дозором при перемещении!",
                )
        return ActionResult(
            action=action,
            action_cost=total_cost,
            speed_spent=total_cost,
            detail=f"{actor.name} перемещается в клетку {action.cell}",
        )

    async def __perform_action_attack(
        self, actor: Actor, action: Action
    ) -> ActionResult:
        action_ap_cost = 0
        actor_cell_type = self.game.arena.map.get(self.game.turn.current_actor.position)
        action_cell_type = self.game.arena.map.get(action.cell)
        attack_params: AttackActionParams = action.params
        try:
            weapon = next(
                w for w in actor.inventory.weapons if w.id == attack_params.weapon_id
            )
        except StopIteration:
            return ActionResult(
                performed=False,
                action=action,
                detail=f"{actor.name}, в инвентаре нет указанного оружия для атаки: {attack_params.weapon_id}",
            )
        action_ap_cost = weapon.cost_ap
        damage = weapon.roll_damage()
        if weapon.type == "melee":
            damage += actor.stats.melee_power
        current_dist = Point.distance_chebyshev(actor.position, action.cell)
        # проверка линии видимости
        if weapon.range > 1:
            if not self.game.arena.map.can_shoot(actor, weapon, action.cell):
                return ActionResult(
                    performed=False,
                    action=action,
                    detail=f"{actor.name}, клетка {action.cell} нельзя атаковать - слишком далеко или есть преграды",  # noqa
                )
        if self.game.turn.current_actor.current_action_points < action_ap_cost:
            return ActionResult(
                performed=False,
                action=action,
                detail=f"{actor.name}, недостаточно очков действия для выбранной атаки",
            )
        if current_dist > weapon.range:
            print(
                f"Attempt to attack {action.cell}, but it's too far: {current_dist}"  # noqa
            )  # noqa
            return ActionResult(
                performed=False,
                action=action,
                detail=f"Слишком далеко для атаки ({current_dist} / {weapon.range})",
            )
        attack_hit = weapon.check_hit(actor_stats=actor.stats, distance=current_dist)
        if (
            actor_cell_type == CELL_TYPE.ENEMY.value
            and action_cell_type == CELL_TYPE.PLAYER.value
        ):
            player = next(x for x in self.game.players if x.position == action.cell)
            if not attack_hit:
                return ActionResult(
                    performed=True,
                    action=action,
                    action_cost=action_ap_cost,
                    detail=f"{actor.name} промахивается из оружия {weapon.name} по {player.name}",
                )
            player.apply_damage(damage)
            part_detail = self.__apply_locational_damage(player, damage)
            death_detail = ""
            if player.is_dead():
                self.game.arena.remove_dead_player(player)
                self.game.players.remove(player)
                death_detail = f" Игрок {player.name} погиб!"
            return ActionResult(
                action=action,
                action_cost=action_ap_cost,
                detail=f"{actor.name} атакует {player.name} ({weapon.name}) и наносит {damage} урона.{part_detail}{death_detail}",
            )
        elif (
            actor_cell_type == CELL_TYPE.PLAYER.value
            and action_cell_type == CELL_TYPE.ENEMY.value
        ):
            enemy = next(
                x for x in self.game.arena.enemies if x.position == action.cell
            )
            if not attack_hit:
                return ActionResult(
                    performed=True,
                    action=action,
                    action_cost=action_ap_cost,
                    detail=f"{actor.name} промахивается из оружия {weapon.name} по {enemy.name}",
                )
            enemy.apply_damage(damage)
            death_detail = ""
            if enemy.is_dead():
                self.game.arena.remove_dead_enemy(enemy=enemy)
                death_detail = f" {enemy.name} погиб!"
            return ActionResult(
                action=action,
                action_cost=action_ap_cost,
                detail=f"{actor.name} атакует {enemy.name} ({weapon.name}) и наносит {damage} урона{death_detail}",
            )
        elif (
            actor_cell_type == CELL_TYPE.PLAYER.value
            and action_cell_type == CELL_TYPE.PLAYER.value
        ):
            # игрок атакует другого игрока
            player_attacking: Player = next(
                x for x in self.game.players if x.position == actor.position
            )
            player_attacked: Player = next(
                x for x in self.game.players if x.position == action.cell
            )
            if player_attacking.team == player_attacked.team:
                return ActionResult(
                    performed=False,
                    action=action,
                    detail=f"{actor.name}, нельзя атаковать своего сокомандника",
                )
            if not attack_hit:
                return ActionResult(
                    performed=True,
                    action=action,
                    action_cost=action_ap_cost,
                    detail=f"{player_attacking.name} промахивается из оружия {weapon.name} по {player_attacked.name}",
                )
            player_attacked.apply_damage(damage)
            part_detail = self.__apply_locational_damage(player_attacked, damage)
            death_detail = ""
            if player_attacked.is_dead():
                self.game.arena.remove_dead_player(player_attacked)
                self.game.players.remove(player_attacked)
                death_detail = f" Игрок {player_attacked.name} погиб!"
            return ActionResult(
                action=action,
                action_cost=action_ap_cost,
                detail=f"{player_attacking.name} атакует {player_attacked.name} ({weapon.name}) и наносит {damage} урона.{part_detail}{death_detail}",  # noqa
            )
        else:
            print(
                f"Unknown actor_type / cell_type for attack: {actor_cell_type} / {action_cell_type}"
            )
            return ActionResult(
                performed=False,
                action=action,
                detail=f"{actor.name}, нельзя атаковать клетку {action.cell}",
            )
