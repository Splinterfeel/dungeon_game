import copy
import random
from typing import TYPE_CHECKING

from src.action_handler import ActionHandler

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
        version: int = 0,
    ):
        self.lobby = lobby
        self.ended = False
        self.version = version
        self.dungeon = dungeon
        self.players = players
        if turn is not None:
            self.turn = turn
        else:
            self.turn = Turn()
        self.action_handler = ActionHandler(game=self)

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

    def move_actor(self, actor: Actor, cell: Point):
        actor_cell_type = self.dungeon.map.get(actor.position)
        self.dungeon.reset_map_cell(actor.position)
        actor.position = cell
        self.dungeon.map.set(cell, actor_cell_type)

    def dump_state(self) -> dict:
        return self.to_dict()

    async def perform_actor_action(self, actor: Actor, action: Action) -> ActionResult:
        action_result: ActionResult = await self.action_handler.perform_actor_action(
            actor, action
        )
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
        self.dungeon.map.clear_start_points()

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
