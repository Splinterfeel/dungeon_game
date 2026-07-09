import copy
import random
from typing import Optional, List

from src.action_handler import ActionHandler
from dto.event import GameEvent
from src.action import Action, ActionResult, ActionType
from src.entities.base import Actor
from src.base import Point
from src.entities.player import Player
from src.entities.enemy import Enemy
from src.arena import Arena
from src.constants import CELL_TYPE
from src.turn import GamePhase, Turn
from src.game_observer import GameObserver


ACTIONS_ENDS_TURN = {ActionType.END_TURN, ActionType.OVERWATCH}


class Game:
    def __init__(
        self,
        arena: Arena,
        players: List[Player],
        turn: Turn = None,
        version: int = 0,
    ):
        self._observer: Optional[GameObserver] = None
        self.ended = False
        self.version = version
        self.arena = arena
        self.players = players
        if turn is not None:
            self.turn = turn
        else:
            self.turn = Turn()
        self.action_handler = ActionHandler(game=self)

    def set_observer(self, observer: GameObserver) -> None:
        """Register an observer for game events"""
        self._observer = observer

    async def _notify_event(
        self, event: GameEvent, receiver_player_ids: Optional[List[str]] = None
    ) -> None:
        """Notify observer of game event"""
        if self._observer:
            await self._observer.on_game_event(event, receiver_player_ids)

    async def _notify_state_change(self) -> None:
        """Notify observer of state change"""
        if self._observer:
            await self._observer.on_state_change()

    async def launch(self):
        self._init_players()

        # ставим ход первому игроку
        self.turn.next()
        await self.pass_turn_to_next_actor()

    async def prepare_actor_turn(self, actor: Actor):
        await self._notify_event(GameEvent(message=f"Ход {actor.name}"))
        actor.current_action_points = actor.stats.action_points
        actor.overwatch = None
        self.turn.available_moves = self.arena.map.get_available_moves(actor)
        actor.current_speed_spent = 0
        self.turn.set_current_actor(actor)

    def _is_hostile(self, watcher: Actor, target: Actor) -> bool:
        if isinstance(watcher, Enemy) and isinstance(target, Player):
            return True
        if isinstance(watcher, Player) and isinstance(target, Enemy):
            return True
        if isinstance(watcher, Player) and isinstance(target, Player):
            return watcher.team != target.team
        return False

    async def check_overwatch_triggers(self, moving_actor: Actor) -> bool:
        all_actors: list[Actor] = list(self.players) + list(self.arena.enemies)
        for watcher in all_actors:
            if watcher.overwatch is None or watcher.is_dead():
                continue
            if not self._is_hostile(watcher, moving_actor):
                continue
            weapon = next(
                (
                    w
                    for w in watcher.inventory.weapons
                    if w.id == watcher.overwatch.weapon_id
                ),
                None,
            )
            if weapon is None:
                watcher.overwatch = None
                continue
            if self.arena.map.can_shoot(watcher, weapon, moving_actor.position):
                await self._fire_overwatch_shot(watcher, weapon, moving_actor)
                watcher.overwatch = None
                return True
        return False

    async def _fire_overwatch_shot(self, watcher: Actor, weapon, target: Actor):
        distance = Point.distance_chebyshev(watcher.position, target.position)
        attack_hit = weapon.check_hit(actor_stats=watcher.stats, distance=distance)
        if not attack_hit:
            await self._notify_event(
                GameEvent(
                    message=f"Огневой дозор: {watcher.name} промахивается по {target.name} из {weapon.name}"
                )
            )
            return
        target.apply_damage(weapon.damage)
        await self._notify_event(
            GameEvent(
                message=f"Огневой дозор: {watcher.name} попадает по {target.name} из {weapon.name} ({weapon.damage} урона)"
            )
        )
        if target.is_dead():
            if isinstance(target, Player):
                self.arena.remove_dead_player(target)
                self.players.remove(target)
            elif isinstance(target, Enemy):
                self.arena.remove_dead_enemy(target)

    def move_actor(self, actor: Actor, cell: Point):
        actor_cell_type = self.arena.map.get(actor.position)
        self.arena.reset_map_cell(actor.position)
        actor.position = cell
        self.arena.map.set(cell, actor_cell_type)

    def dump_state(self) -> dict:
        return self.to_dict()

    async def perform_actor_action(self, actor: Actor, action: Action) -> ActionResult:
        action_result: ActionResult = await self.action_handler.perform_actor_action(
            actor, action
        )
        await self._notify_event(GameEvent(message=action_result.detail))
        if action_result.performed:
            actor.current_action_points = max(
                actor.current_action_points - action_result.action_cost, 0
            )
            actor.current_speed_spent += action_result.speed_spent
        if action.type in ACTIONS_ENDS_TURN and action_result.performed:
            await self.pass_turn_to_next_actor()
        self.check_game_end()
        self.turn.available_moves = self.arena.map.get_available_moves(
            self.turn.current_actor
        )
        return action_result

    async def pass_turn_to_next_actor(self):
        if self.turn.phase == GamePhase.TEAM_1_PHASE:
            actors = [x for x in self.players if x.team == 1]
        elif self.turn.phase == GamePhase.TEAM_2_PHASE:
            actors = [x for x in self.players if x.team == 2]
        else:
            actors = self.arena.enemies
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
            all(e.is_dead() for e in self.arena.enemies) or len(self.arena.enemies) == 0
        )
        if team_1_dead and team_2_dead:
            # все игроки мертвы
            self.ended = True
        if enemies_dead and (team_1_dead or team_2_dead):
            # осталась одна команда игроков
            self.ended = True

    def _init_players(self):
        point_choices = {
            1: copy.deepcopy(self.arena.start_points_team_1),
            2: copy.deepcopy(self.arena.start_points_team_2),
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
            self.arena.map.set(player.position, CELL_TYPE.PLAYER.value)
        self.arena.map.clear_start_points()

    def to_dict(self) -> dict:
        """Сериализует всё состояние игры в словарь"""
        dump = {
            "arena": self.arena.model_dump(),
            "players": [p.model_dump() for p in self.players],
            "turn": self.turn.model_dump(),
            "version": self.version,
            "ended": self.ended,
        }
        if self.turn.phase == GamePhase.AI_ENEMY_PHASE:
            dump["turn"]["current_actor"] = None
        return dump
