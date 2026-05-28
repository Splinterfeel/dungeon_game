import typing

from dto.event import GameEvent
from src.action import Action, ActionResult, ActionType, AttackActionParams
from src.base import Point
from src.constants import CELL_TYPE
from src.entities.base import Actor
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
                detail=f"{actor.name} попытался походить во время хода {self.turn.current_actor.name}",
            )
        # Enemy и Player приводятся к Actor
        match action.type:
            case ActionType.END_TURN:
                return await self.__perform_action_end_turn(actor=actor, action=action)
            case ActionType.MOVE:
                return await self.__perform_action_move(actor=actor, action=action)
            case ActionType.ATTACK:
                return await self.__perform_action_attack(actor=actor, action=action)
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
        player: Player = next(x for x in self.game.players if x.position == action.cell)
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
        if self.game.turn.current_actor != action.actor:
            print(
                detail=f"{actor.name} попытался закончить ход во время хода {self.turn.current_actor.name}",
            )
        return ActionResult(
            action=action,
            action_cost=30000,  # TODO пока просто завершаем ход немыслимым кол-вом AP
            detail=f"{actor.name} завершает ход",
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
            action.cell, self.game.turn.current_actor.position
        )
        if not path:
            return ActionResult(
                performed=False,
                action=action,
                detail=f"{actor.name}, не получилось построить путь до точки {action.cell}",
            )
        action_ap_cost = len(path) - 1
        assert action_ap_cost > 0
        if self.game.turn.current_actor.current_action_points < action_ap_cost:
            return ActionResult(
                performed=False,
                action=action,
                detail=f"{actor.name}, Недостаточно очков действия для перемещения в {action.cell}!",
            )
        self.game.move_actor(actor, action.cell)
        return ActionResult(
            action=action,
            action_cost=action_ap_cost,
            speed_spent=action_ap_cost,
            detail=f"{actor.name} перемещается в клетку {action.cell}",
        )

    async def __perform_action_attack(
        self, actor: Actor, action: Action
    ) -> ActionResult:
        action_ap_cost = 0
        actor_cell_type = self.game.dungeon.map.get(
            self.game.turn.current_actor.position
        )
        action_cell_type = self.game.dungeon.map.get(action.cell)
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
        # проверка линии видимости
        if weapon.range > 1:
            if not self.game.dungeon.map.can_shoot(actor, weapon, action.cell):
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
        if (
            actor_cell_type == CELL_TYPE.ENEMY.value
            and action_cell_type == CELL_TYPE.PLAYER.value
        ):
            player = next(x for x in self.game.players if x.position == action.cell)
            player.apply_damage(damage)
            if player.is_dead():
                self.game.dungeon.remove_dead_player(player)
                self.game.players.remove(player)
                await self.game.lobby.broadcast_game_event(
                    GameEvent(message=f"Игрок {player.name} погиб!")
                )
            return ActionResult(
                action=action,
                action_cost=action_ap_cost,
                detail=f"{actor.name} атакует {player.name} и наносит {damage} урона",
            )
        elif (
            actor_cell_type == CELL_TYPE.PLAYER.value
            and action_cell_type == CELL_TYPE.ENEMY.value
        ):
            enemy = next(
                x for x in self.game.dungeon.enemies if x.position == action.cell
            )
            enemy.apply_damage(damage)
            if enemy.is_dead():
                self.game.dungeon.remove_dead_enemy(enemy=enemy)
                await self.game.lobby.broadcast_game_event(
                    GameEvent(message=f"Одичалый {enemy.name} погиб!")
                )
            return ActionResult(
                action=action,
                action_cost=action_ap_cost,
                detail=f"{actor.name} атакует {enemy.name} и наносит {damage} урона",
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
            player_attacked.apply_damage(damage)
            if player_attacked.is_dead():
                self.game.dungeon.remove_dead_player(player_attacked)
                self.game.players.remove(player_attacked)
                await self.game.lobby.broadcast_game_event(
                    GameEvent(message=f"Игрок {player_attacked.name} погиб!")
                )
            return ActionResult(
                action=action,
                action_cost=action_ap_cost,
                detail=f"{player_attacking.name} атакует {player_attacked.name} и наносит {damage} урона",
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
