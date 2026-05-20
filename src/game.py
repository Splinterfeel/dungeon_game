import copy
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lobby import Lobby

from dto.event import GameEvent
from src.action import Action, ActionResult, ActionType, AttackActionParams
from src.entities.base import Actor
from src.base import Point
from src.entities.player import Player
from src.dungeon import Dungeon
from src.constants import CELL_TYPE
from src.turn import GamePhase, Turn


class Game:
    def __init__(
        self,
        lobby: "Lobby",
        dungeon: Dungeon,
        players: list[Player],
        turn: Turn = None,
        is_server: bool = True,
        version: int = 0,
    ):
        self.lobby = lobby
        self.ended = False
        self.version = version
        self.is_server = is_server
        self.dungeon = dungeon
        self.players = players
        if turn is not None:
            self.turn = turn
        else:
            self.turn = Turn()

        if is_server and not players:
            raise ValueError("No players passed")
        if self.is_server:
            self.dump_state()

    async def launch(self):
        self._init_players()

        # ставим ход первому игроку
        self.turn.next()
        await self.pass_turn_to_next_actor()

    async def prepare_actor_turn(self, actor: Actor):
        await self.lobby.broadcast_game_event(GameEvent(message=f"Ход {actor.name}"))
        # в начале хода задаем базовое количество AP игроку
        actor.current_action_points = actor.stats.action_points
        self.turn.available_moves = self.dungeon.map.get_available_moves(actor)
        # в начале хода еще не прошел ни одной клетки
        actor.current_speed_spent = 0
        self.turn.set_current_actor(actor)

    async def _perform_actor_action(self, actor: Actor, action: Action) -> ActionResult:
        if self.turn.current_actor != actor:
            return ActionResult(
                performed=False,
                action=action,
                detail=f"{actor.name} попытался походить во время хода {self.turn.current_actor.name}",
            )
        # Enemy и Player приводятся к Actor
        match action.type:
            case ActionType.END_TURN:
                return await self._perform_action_end_turn(actor=actor, action=action)
            case ActionType.MOVE:
                return await self._perform_action_move(actor=actor, action=action)
            case ActionType.ATTACK:
                return await self._perform_action_attack(actor=actor, action=action)
            case ActionType.INSPECT:
                print("INSPECTING", action.cell)
                return ActionResult(action=action)
            case _:
                print("Performing unknown action", action)
                return ActionResult(action=action)

    async def _perform_action_end_turn(
        self, actor: Actor, action: Action
    ) -> ActionResult:
        if self.turn.current_actor != action.actor:
            print(
                detail=f"{actor.name} попытался закончить ход во время хода {self.turn.current_actor.name}",
            )
        return ActionResult(
            action=action,
            action_cost=30000,  # TODO пока просто завершаем ход немыслимым кол-вом AP
            detail=f"{actor.name} завершает ход",
        )

    async def _perform_action_move(self, actor: Actor, action: Action) -> ActionResult:
        if action.cell not in self.turn.available_moves:
            print(f"Can't move player {actor} to cell {action.cell}")
            return ActionResult(
                performed=False,
                action=action,
                detail=f"{actor.name}, нельзя переместиться в {action.cell}, слишком далеко",
            )
        if not self.dungeon.map.is_free(action.cell):
            return ActionResult(
                performed=False,
                action=action,
                detail=f"{actor.name}, клетка {action.cell} занята, нельзя в нее переместиться",  # noqa
            )
        path = self.dungeon.map.bfs_path(action.cell, self.turn.current_actor.position)
        if not path:
            return ActionResult(
                performed=False,
                action=action,
                detail=f"{actor.name}, не получилось построить путь до точки {action.cell}",
            )
        action_ap_cost = len(path) - 1
        assert action_ap_cost > 0
        if self.turn.current_actor.current_action_points < action_ap_cost:
            return ActionResult(
                performed=False,
                action=action,
                detail=f"{actor.name}, Недостаточно очков действия для перемещения в {action.cell}!",
            )
        self.move_actor(actor, action.cell)
        return ActionResult(
            action=action,
            action_cost=action_ap_cost,
            speed_spent=action_ap_cost,
            detail=f"{actor.name} перемещается в клетку {action.cell}",
        )

    async def _perform_action_attack(
        self, actor: Actor, action: Action
    ) -> ActionResult:
        action_ap_cost = 0
        actor_cell_type = self.dungeon.map.get(self.turn.current_actor.position)
        action_cell_type = self.dungeon.map.get(action.cell)
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
            if not self.dungeon.map.can_shoot(actor, weapon, action.cell):
                return ActionResult(
                    performed=False,
                    action=action,
                    detail=f"{actor.name}, клетка {action.cell} нельзя атаковать - слишком далеко или есть преграды",  # noqa
                )
        if self.turn.current_actor.current_action_points < action_ap_cost:
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
            player = next(x for x in self.players if x.position == action.cell)
            player.apply_damage(damage)
            if player.is_dead():
                self.dungeon.remove_dead_player(player)
                self.players.remove(player)
                await self.lobby.broadcast_game_event(
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
            enemy = next(x for x in self.dungeon.enemies if x.position == action.cell)
            enemy.apply_damage(damage)
            if enemy.is_dead():
                self.dungeon.remove_dead_enemy(enemy=enemy)
                await self.lobby.broadcast_game_event(
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
                x for x in self.players if x.position == actor.position
            )
            player_attacked: Player = next(
                x for x in self.players if x.position == action.cell
            )
            if player_attacking.team == player_attacked.team:
                return ActionResult(
                    performed=False,
                    action=action,
                    detail=f"{actor.name}, нельзя атаковать своего сокомандника",
                )
            player_attacked.apply_damage(damage)
            if player_attacked.is_dead():
                self.dungeon.remove_dead_player(player_attacked)
                self.players.remove(player_attacked)
                await self.lobby.broadcast_game_event(
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

    def move_actor(self, actor: Actor, cell: Point):
        actor_cell_type = self.dungeon.map.get(actor.position)
        self.dungeon.map.set(actor.position, CELL_TYPE.EMPTY.value)
        actor.position = cell
        self.dungeon.map.set(cell, actor_cell_type)

    def dump_state(self) -> dict:
        if not self.is_server:
            raise ValueError("Can't dump not server instance of Game")
        # положить состояние в очередь
        return self.to_dict()

    async def perform_actor_action(self, actor: Actor, action: Action) -> ActionResult:
        action_result: ActionResult = await self._perform_actor_action(actor, action)
        await self.lobby.broadcast_game_event(GameEvent(message=action_result.detail))
        if action_result.performed:
            actor.current_action_points = max(
                actor.current_action_points - action_result.action_cost, 0
            )
            actor.current_speed_spent += action_result.speed_spent
        if action.type == ActionType.END_TURN:
            await self.pass_turn_to_next_actor()
        self.check_game_end()
        self.turn.available_moves = self.dungeon.map.get_available_moves(
            self.turn.current_actor
        )
        return action_result

    async def pass_turn_to_next_actor(self):
        if self.turn.phase == GamePhase.TEAM_1_PHASE:
            actors = [x for x in self.players if x.team == 1]
        elif self.turn.phase == GamePhase.TEAM_2_PHASE:
            actors = [x for x in self.players if x.team == 2]
        else:
            actors = self.dungeon.enemies
        # находим игрока/врага который еще не ходил
        # пока просто по очереди
        next_actor = None
        for actor in actors:
            if actor.id in self.turn.actor_ids_passed_turn:
                continue
            else:
                next_actor = actor
                break
        if not next_actor:
            if self.turn.has_next_phase():
                self.turn.switch_phase()
            else:
                self.turn.next()
            await self.pass_turn_to_next_actor()
        else:
            await self.prepare_actor_turn(next_actor)

    def check_game_end(self):
        players_team_1 = [x for x in self.players if x.team == 1]
        players_team_2 = [x for x in self.players if x.team == 2]
        team_1_dead = (
            all(p.is_dead() for p in players_team_1) or len(players_team_1) == 0
        )
        team_2_dead = (
            all(p.is_dead() for p in players_team_2) or len(players_team_2) == 0
        )
        enemies_dead = (
            all(e.is_dead() for e in self.dungeon.enemies)
            or len(self.dungeon.enemies) == 0
        )
        if team_1_dead and team_2_dead:
            # все игроки мертвы
            self.ended = True
        if enemies_dead and (team_1_dead or team_2_dead):
            # осталась одна команда игроков
            self.ended = True

    def _init_players(self):
        point_choices = {
            1: copy.deepcopy(self.dungeon.start_points_team_1),
            2: copy.deepcopy(self.dungeon.start_points_team_2),
        }

        players_team_1 = [p for p in self.players if p.team == 1]
        players_team_2 = [p for p in self.players if p.team == 2]
        if len(point_choices[1]) < len(players_team_1):
            raise ValueError("Not enough place choices for all players in team 1")
        if len(point_choices[2]) < len(players_team_2):
            raise ValueError("Not enough place choices for all players in team 2")
        for player in self.players:
            position = random.choice(point_choices[player.team])
            point_choices[player.team].remove(position)
            player.position = position
            self.dungeon.map.set(player.position, CELL_TYPE.PLAYER.value)
        # убираем лишние старт-поинты, которые не пригодились
        for point in point_choices[1]:
            self.dungeon.map.set(point, CELL_TYPE.EMPTY.value)
        for point in point_choices[2]:
            self.dungeon.map.set(point, CELL_TYPE.EMPTY.value)

    def to_dict(self) -> dict:
        """Сериализует всё состояние игры в словарь"""
        dump = {
            "dungeon": self.dungeon.model_dump(),
            "players": [p.model_dump() for p in self.players],
            "turn": self.turn.model_dump(),
            "version": self.version,
            "ended": self.ended,
        }
        if self.turn.phase == GamePhase.AI_ENEMY_PHASE:
            dump["turn"]["current_actor"] = None
        return dump
