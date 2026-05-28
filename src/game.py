import copy
import random
from typing import TYPE_CHECKING

from src.action_handler import ActionHandler

if TYPE_CHECKING:
    from lobby import Lobby

from dto.event import GameEvent
from src.action import Action, ActionResult, ActionType
from src.entities.base import Actor
from src.base import Point
from src.entities.player import Player
from src.entities.enemy import Enemy
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
        actor.current_action_points = actor.stats.action_points
        actor.overwatch = None
        self.turn.available_moves = self.dungeon.map.get_available_moves(actor, self)
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

    def get_actor_at_cell(self, cell: Point) -> Actor | None:
        """
        Find any actor (Player or Enemy) at the given cell position.
        Returns None if no actor found at the position.
        """
        for player in self.players:
            if player.position == cell:
                return player

        for enemy in self.dungeon.enemies:
            if enemy.position == cell:
                return enemy

        return None

    async def handle_actor_death(self, actor: Actor) -> None:
        """
        Handle actor death - remove from appropriate lists and broadcast event.
        Works for both Player and Enemy types.
        """
        if isinstance(actor, Player):
            self.dungeon.remove_dead_player(actor)
            if actor in self.players:
                self.players.remove(actor)
            await self.lobby.broadcast_game_event(
                GameEvent(message=f"Игрок {actor.name} погиб!")
            )
        elif isinstance(actor, Enemy):
            self.dungeon.remove_dead_enemy(enemy=actor)
            await self.lobby.broadcast_game_event(
                GameEvent(message=f"{actor.name} погиб!")
            )

    async def check_overwatch_triggers(self, moving_actor: Actor) -> bool:
        all_actors: list[Actor] = list(self.players) + list(self.dungeon.enemies)
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
            if self.dungeon.map.can_shoot(watcher, weapon, moving_actor.position):
                await self._fire_overwatch_shot(watcher, weapon, moving_actor)
                watcher.overwatch = None
                return True
        return False

    async def _fire_overwatch_shot(self, watcher: Actor, weapon, target: Actor):
        distance = Point.distance_chebyshev(watcher.position, target.position)
        attack_hit = weapon.check_hit(actor_stats=watcher.stats, distance=distance)
        if not attack_hit:
            await self.lobby.broadcast_game_event(
                GameEvent(
                    message=f"Огневой дозор: {watcher.name} промахивается по {target.name} из {weapon.name}"
                )
            )
            return
        target.apply_damage(weapon.damage)
        await self.lobby.broadcast_game_event(
            GameEvent(
                message=f"Огневой дозор: {watcher.name} попадает по {target.name} из {weapon.name} ({weapon.damage} урона)"  # noqa
            )
        )
        if target.is_dead():
            if isinstance(target, Player):
                self.dungeon.remove_dead_player(target)
                self.players.remove(target)
            elif isinstance(target, Enemy):
                self.dungeon.remove_dead_enemy(target)
            await self.lobby.broadcast_game_event(
                GameEvent(message=f"{target.name} убит огневым дозором!")
            )

    def move_actor(self, actor: Actor, cell: Point):
        # Clear old position - set to EMPTY unless it's an exit
        old_position = actor.position
        old_cell_type = self.dungeon.map.get(old_position)

        # Clear old position
        if old_cell_type == CELL_TYPE.EXIT.value:
            self.dungeon.map.set(old_position, CELL_TYPE.EXIT.value)
        elif old_cell_type in [CELL_TYPE.START_TEAM_1.value, CELL_TYPE.START_TEAM_2.value]:
            # For start positions, set to EMPTY after player moves away
            self.dungeon.map.set(old_position, CELL_TYPE.EMPTY.value)
        else:
            self.dungeon.map.set(old_position, CELL_TYPE.EMPTY.value)

        # Set new position
        actor.position = cell
        if isinstance(actor, Player):
            self.dungeon.map.set(cell, CELL_TYPE.PLAYER.value)
        else:
            self.dungeon.map.set(cell, CELL_TYPE.ENEMY.value)

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
            # Overwatch automatically ends the turn only if successfully performed
            if action.type == ActionType.END_TURN or action.type == ActionType.OVERWATCH:
                await self.pass_turn_to_next_actor()
        else:
            # Check game end even if action failed
            self.check_game_end()
            self.turn.available_moves = self.dungeon.map.get_available_moves(
                self.turn.current_actor, self
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
