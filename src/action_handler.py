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
from src.entities.base import Actor, OverwatchState
from src.entities.player import Player

if typing.TYPE_CHECKING:
    from src.game import Game


class ActionHandler:
    def __init__(self, game: "Game"):
        self.game = game

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
            case ActionType.EXIT:
                return await self.__perform_action_exit(actor=actor, action=action)
            case ActionType.INSPECT:
                print("INSPECTING", action.cell)
                return ActionResult(action=action)
            case _:
                print("Performing unknown action", action)
                return ActionResult(action=action)

    async def __perform_action_exit(self, actor: Actor, action: Action) -> ActionResult:
        # покинуть можно только самым первым действием на ходу, когда AP на максимуме
        player = self.game.get_actor_at_cell(action.cell)
        if not isinstance(player, Player):
            return ActionResult(
                performed=False,
                action=action,
                detail=f"На клетке {action.cell} нет игрока",
            )
        if player.team != 1:
            return ActionResult(
                performed=False,
                action=action,
                detail=f"{player.name}, покинуть данж может только команда 1!",
            )
        if self.game.dungeon._initial_map.get(player.position) != CELL_TYPE.EXIT.value:
            return ActionResult(
                performed=False,
                action=action,
                detail=f"{player.name}, покинуть данж можно только на клетке выхода",
            )
        if player.current_action_points < player.stats.action_points:
            return ActionResult(
                performed=False,
                action=action,
                detail=f"{player.name}, покинуть данж можно только когда AP на максимуме",
            )
        self.game.players.remove(player)
        return ActionResult(
            action=action,
            action_cost=30000,
            detail=f"{player.name} покинул данж!",
        )

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
        try:
            weapon = next(
                w for w in actor.inventory.weapons if w.id == params.weapon_id
            )
        except StopIteration:
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
        ap_cost = weapon.cost_ap
        if actor.current_action_points < ap_cost:
            return ActionResult(
                performed=False,
                action=action,
                detail=f"{actor.name}, нет очков действия для огневого дозора",
            )
        actor.overwatch = OverwatchState(weapon_id=weapon.id)
        return ActionResult(
            action=action,
            action_cost=ap_cost,
            detail=f"{actor.name} переходит в режим огневого дозора ({weapon.name})",
        )

    async def __perform_action_move(self, actor: Actor, action: Action) -> ActionResult:
        if action.cell not in self.game.turn.available_moves:
            print(f"Can't move player {actor} to cell {action.cell}")
            return ActionResult(
                performed=False,
                action=action,
                detail=f"{actor.name}, нельзя переместиться в {action.cell}",
            )
        if not self.game.dungeon.map.is_free(action.cell):
            if self.game.dungeon.map.get(action.cell) != CELL_TYPE.EXIT.value:
                return ActionResult(
                    performed=False,
                    action=action,
                    detail=f"{actor.name}, клетка {action.cell} занята, нельзя в нее переместиться",  # noqa
                )
        path = self.game.dungeon.map.bfs_path(
            action.cell, self.game.turn.current_actor.position, self.game
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
            await self.game.lobby.broadcast_game_state()
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
        # === VALIDATION PHASE ===
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
        damage = weapon.damage
        current_dist = Point.distance_chebyshev(actor.position, action.cell)

        # Line of sight and distance validation
        if weapon.range > 1:
            if not self.game.dungeon.map.can_shoot(actor, weapon, action.cell):
                return ActionResult(
                    performed=False,
                    action=action,
                    detail=f"{actor.name}, клетка {action.cell} нельзя атаковать - слишком далеко или есть преграды",
                )

        if self.game.turn.current_actor.current_action_points < action_ap_cost:
            return ActionResult(
                performed=False,
                action=action,
                detail=f"{actor.name}, недостаточно очков действия для выбранной атаки",
            )

        if current_dist > weapon.range:
            print(f"Attempt to attack {action.cell}, but it's too far: {current_dist}")
            return ActionResult(
                performed=False,
                action=action,
                detail=f"Слишком далеко для атаки ({current_dist} / {weapon.range})",
            )

        # === ATTACK EXECUTION PHASE ===
        # Find target actor using new utility method
        target_actor = self.game.get_actor_at_cell(action.cell)

        if target_actor is None:
            return ActionResult(
                performed=False,
                action=action,
                detail=f"{actor.name}, в клетке {action.cell} никого нет",
            )

        # Validate attack using _is_hostile
        if not self.game._is_hostile(actor, target_actor):
            # Handle friendly fire prevention
            if isinstance(actor, Player) and isinstance(target_actor, Player):
                return ActionResult(
                    performed=False,
                    action=action,
                    detail=f"{actor.name}, нельзя атаковать своего сокомандника",
                )
            else:
                return ActionResult(
                    performed=False,
                    action=action,
                    detail=f"{actor.name}, нельзя атаковать этот объект",
                )

        # Calculate hit
        attack_hit = weapon.check_hit(actor_stats=actor.stats, distance=current_dist)

        if not attack_hit:
            return ActionResult(
                performed=False,
                action=action,
                detail=f"{actor.name} промахивается из оружия {weapon.name} по {target_actor.name}",
            )

        # Apply damage
        target_actor.apply_damage(damage)

        # Handle death if needed
        if target_actor.is_dead():
            await self.game.handle_actor_death(target_actor)

        # Return success result
        return ActionResult(
            action=action,
            action_cost=action_ap_cost,
            detail=f"{actor.name} атакует {target_actor.name} ({weapon.name}) и наносит {damage} урона",
        )
