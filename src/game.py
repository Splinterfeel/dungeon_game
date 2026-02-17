import random
import time
from src.action import Action, ActionResult, ActionType
from src.entities.base import Actor
from src.base import Point, PointOffset
from src.entities.enemy import Enemy
from src.entities.player import Player
from src.dungeon import Dungeon
from src.constants import CELL_TYPE, AttackType
from src.turn import GamePhase, Turn


class Game:
    def __init__(
        self,
        dungeon: Dungeon,
        players: list[Player],
        turn: Turn = None,
        is_server: bool = True,
        version: int = 0,
    ):
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

    def launch(self):
        self._init_players(self.dungeon.start_point)

        # ставим ход первому игроку
        self.turn.next()
        self.pass_turn_to_next_actor()

    def prepare_actor_turn(self, actor: Actor):
        print(f"turn - {type(actor)} [{actor.name}]")
        self.turn.set_current_actor(actor)
        self.turn.available_moves = self.dungeon.map.get_available_moves(actor)
        # в начале хода задаем базовое количество AP игроку
        actor.current_action_points = actor.stats.action_points
        # в начале хода еще не прошел ни одной клетки
        actor.current_speed_spent = 0

    def generate_enemy_action(self) -> Action:
        actor = self.turn.current_actor
        print("generating action for actor", str(actor.name))
        if not isinstance(actor, Enemy):
            raise ValueError(f"Can't handle action of {type(actor)}, should be {type(Enemy)}")
        # пропускаем пока что
        time.sleep(1)
        print(actor, "ends turn")
        return Action(actor=actor, type=ActionType.END_TURN, cell=actor.position)

    def _perform_actor_action(self, actor: Actor, action: Action) -> ActionResult:
        # возвращает action_performed (bool), AP cost (int)
        "True если действие выполнено успешно, иначе False"
        if self.turn.current_actor != actor:
            raise ValueError(
                f"Attempt to perform action of player {actor} when turn of player {self.turn.current_actor}"
            )  # noqa
        # Enemy и Player приводятся к Actor
        action_ap_cost = 0
        actor_cell_type = self.dungeon.map.get(self.turn.current_actor.position)
        action_cell_type = self.dungeon.map.get(action.cell)
        match action.type:
            case ActionType.END_TURN:
                if self.turn.current_actor != action.actor:
                    print(
                        f"[!] not turn of actor {action.actor}, now turn of {self.turn.current_actor}"
                    )
                return ActionResult(
                    action=action,
                    action_cost=30000,  # TODO пока просто завершаем ход немыслимым кол-вом AP
                )
            case ActionType.MOVE:
                if action.cell not in self.turn.available_moves:
                    print(f"Can't move player {actor} to cell {action.cell}")
                    return ActionResult(performed=False, action=action)
                if not self.dungeon.map.is_free(action.cell):
                    print(f"Cell {action.cell} is not free, can't move {actor} here")
                    return ActionResult(performed=False, action=action)
                path = self.dungeon.map.bfs_path(
                    action.cell, self.turn.current_actor.position
                )
                if not path:
                    print(f"Can't reach point (BFS): {action.cell}")
                    return ActionResult(performed=False, action=action)
                action_ap_cost = len(path) - 1
                assert action_ap_cost > 0
                if self.turn.current_actor.current_action_points < action_ap_cost:
                    print(
                        f"Not enough AP: {self.turn.current_actor.current_action_points} / {action_ap_cost}"
                    )
                    return ActionResult(performed=False, action=action)
                self.move_actor(actor, action.cell)
                return ActionResult(
                    action=action,
                    action_cost=action_ap_cost,
                    speed_spent=action_ap_cost,
                )
            case ActionType.ATTACK:
                attack_action = AttackType.from_dict(action.params)
                action_ap_cost = attack_action.cost
                if self.turn.current_actor.current_action_points < action_ap_cost:
                    print(
                        f"Not enough AP: {self.turn.current_actor.current_action_points} / {action_ap_cost}"
                    )
                    return ActionResult(performed=False, action=action)
                if Point.distance_chebyshev(actor.position, action.cell) > 1:
                    print(
                        f"Attempt to attack {action.cell}, but it's too far: {Point.distance_chebyshev(actor.position, action.cell)}"  # noqa
                    )  # noqa
                    return ActionResult(performed=False, action=action)
                damage = int(actor.stats.damage * attack_action.default_multiplier)
                if (
                    actor_cell_type == CELL_TYPE.ENEMY.value
                    and action_cell_type == CELL_TYPE.PLAYER.value
                ):
                    print("Enemy атакует Player")
                    player = next(x for x in self.players if x.position == action.cell)
                    player.apply_damage(damage)
                    if player.is_dead():
                        self.dungeon.remove_dead_player(player)
                        print("[!] player", player, "is dead")
                        self.players.remove(player)
                    else:
                        print("attacked player")
                    return ActionResult(action=action)
                elif (
                    actor_cell_type == CELL_TYPE.PLAYER.value
                    and action_cell_type == CELL_TYPE.ENEMY.value
                ):
                    print("Enemy атакует Player")
                    enemy = next(
                        x for x in self.dungeon.enemies if x.position == action.cell
                    )
                    enemy.apply_damage(damage)
                    print(
                        f"     Attacked enemy at {action.cell}, DMG {damage}, enemy health: {enemy.stats.health}"
                    )
                    if enemy.is_dead():
                        self.dungeon.remove_dead_enemy(enemy=enemy)
                    else:
                        print("attacked enemy")
                    return ActionResult(action=action, action_cost=action_ap_cost)
                else:
                    raise ValueError(
                        "Unknown actor_type / cell_type:",
                        actor_cell_type,
                        action_cell_type,
                    )
            case ActionType.INSPECT:
                print("INSPECTING", action.cell, action_cell_type)
                return ActionResult(action=action)
            case _:
                print("Performing unknown action", action)
                return ActionResult(action=action)

    def move_actor(self, actor: Actor, cell: Point):
        actor_cell_type = self.dungeon.map.get(actor.position)
        self.dungeon.map.set(actor.position, CELL_TYPE.FLOOR.value)
        actor.position = cell
        self.dungeon.map.set(cell, actor_cell_type)

    def dump_state(self) -> dict:
        if not self.is_server:
            raise ValueError("Can't dump not server instance of Game")
        # положить состояние в очередь
        return self.to_dict()
        # Queues.RENDER_QUEUE.put(self.to_dict())

    def perform_actor_action(self, actor: Actor, action: Action) -> ActionResult:
        # TODO check if actor same as current_actor
        action_result = self._perform_actor_action(actor, action)
        if action_result.performed:
            actor.current_action_points = max(
                actor.current_action_points - action_result.action_cost, 0
            )
            actor.current_speed_spent += action_result.speed_spent
        self.turn.available_moves = self.dungeon.map.get_available_moves(actor)
        if action.type == ActionType.END_TURN:
            self.pass_turn_to_next_actor()
        self.check_game_end()
        return action_result

    def pass_turn_to_next_actor(self):
        if self.turn.phase == GamePhase.PLAYER_PHASE:
            actors = self.players
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
            self.pass_turn_to_next_actor()
        else:
            self.prepare_actor_turn(next_actor)

    def check_game_end(self) -> bool:
        return all(p.is_dead() for p in self.players) or all(
            e.is_dead() for e in self.dungeon.enemies
        )

    def _init_players(self, point: Point):
        point_choices = [
            point,
            point.on(PointOffset.LEFT),
            point.on(PointOffset.LEFT).on(PointOffset.TOP),
            point.on(PointOffset.TOP),
            point.on(PointOffset.TOP).on(PointOffset.RIGHT),
            point.on(PointOffset.RIGHT),
            point.on(PointOffset.RIGHT).on(PointOffset.BOTTOM),
            point.on(PointOffset.BOTTOM),
            point.on(PointOffset.BOTTOM).on(PointOffset.LEFT),
        ]
        choices = [c for c in point_choices if self.dungeon.map.is_free(c)]
        if len(choices) < len(self.players):
            raise ValueError("Not enough place choices for all players")
        for player in self.players:
            position = random.choice(choices)
            choices.remove(position)
            player.position = position
            self.dungeon.map.set(player.position, CELL_TYPE.PLAYER.value)

    def to_dict(self) -> dict:
        """Сериализует всё состояние игры в словарь"""
        dump = {
            "dungeon": self.dungeon.to_dict(),
            "players": [p.to_dict() for p in self.players],
            "turn": self.turn.to_dict(),
            "version": self.version,
        }
        if self.turn.phase == GamePhase.ENEMY_PHASE:
            dump["turn"]["current_actor"] = None
        return dump

    @classmethod
    def from_dict(cls, _dict: dict) -> "Game":
        """Создает Game из сериализованных данных"""
        dungeon = Dungeon.from_dict(_dict["dungeon"])
        players = [Player.from_dict(p) for p in _dict.get("players", [])]
        if "turn" in _dict:
            turn = Turn.from_dict(_dict["turn"])
        else:
            turn = None
        game = cls(
            dungeon=dungeon,
            players=players,
            turn=turn,
            is_server=_dict.get("is_server", False),
            version=_dict.get("version"),
        )
        return game
