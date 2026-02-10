import queue
import random
import time
from src.action import Action, ActionType
from src.entities.base import Actor
from src.audio import SoundEvent
from src.base import Point, PointOffset, Queues
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
    ):
        self.is_server = is_server
        self.dungeon = dungeon
        self.players = players
        if turn is not None:
            self.turn = turn
        else:
            self.turn = Turn()

        if not players:
            raise ValueError("No players passed")
        if self.is_server:
            self.dump_state()

    def init(self):
        self._init_players(self.dungeon.start_point)

    def send_sound_event(self, event_name: str):
        Queues.SOUND_QUEUE.put(SoundEvent(name=event_name))

    def perform_player_action(self, player: Player, action: Action) -> tuple[bool, int]:
        # возвращает action_performed (bool), AP cost (int)
        "True если действие выполнено успешно, иначе False"
        if self.turn.current_actor != player:
            raise ValueError(
                f"Attempt to perform action of player {player} when turn of player {self.turn.current_actor}"
            )  # noqa
        current_actor = Actor(
            position=self.turn.current_actor.position,
            stats=self.turn.current_actor.stats,
            current_action_points=self.turn.current_actor.current_action_points,
        )
        action_ap_cost = 0
        match action.type:
            case ActionType.END_TURN:
                if current_actor != action.actor:
                    print(f"not turn of actor {action.actor}, now turn of {self.turn.current_actor}")
                print("end turn of actor at", action.actor.position)
                return True, 30000  # TODO пока просто завершаем ход немыслимым кол-вом AP
            case ActionType.MOVE:
                if action.cell not in self.turn.available_moves:
                    print(f"Can't move player {player} to cell {action.cell}")
                    return False, 0
                if not self.dungeon.map.is_free(action.cell):
                    print(f"Cell {action.cell} is not free, can't move {player} here")
                    return False, 0
                path = self.dungeon.map.bfs_path(action.cell, current_actor.position)
                if not path:
                    print(f"Can't reach point (BFS): {action.cell}")
                    return False, 0
                action_ap_cost = len(path) - 1
                assert action_ap_cost > 0
                if current_actor.current_action_points < action_ap_cost:
                    print(f"Not enough AP: {current_actor.current_action_points} / {action_ap_cost}")
                    return False, 0
                self.move_player(player, action.cell)
                self.send_sound_event("move")
                return True, action_ap_cost
            case ActionType.ATTACK:
                attack_action = AttackType.from_dict(action.params)
                action_ap_cost = attack_action.cost
                if current_actor.current_action_points < action_ap_cost:
                    print(f"Not enough AP: {current_actor.current_action_points} / {action_ap_cost}")
                    return False, 0
                print(action.params)
                if self.dungeon.map.get(action.cell) != CELL_TYPE.ENEMY.value:
                    print(f"Attempt to attack {action.cell}, cell is not enemy")
                    return False, 0
                if Point.distance_chebyshev(player.position, action.cell) > 1:
                    print(
                        f"Attempt to attack {action.cell}, but it's too far: {Point.distance_chebyshev(player.position, action.cell)}"
                    )  # noqa
                    return False, 0
                enemy = next(
                    x for x in self.dungeon.enemies if x.position == action.cell
                )
                damage = int(player.stats.damage * attack_action.default_multiplier)
                enemy.apply_damage(damage)
                print(
                    f"Attacked enemy at {action.cell}, DMG {damage}, enemy health: {enemy.stats.health}"
                )
                if enemy.is_dead():
                    self.send_sound_event("kill")
                    self.dungeon.remove_dead_enemy(enemy=enemy)
                else:
                    self.send_sound_event("hit")
                return True, action_ap_cost
            case _:
                print("Performing action", action)
                return True, 0

    def move_player(self, player: Player, cell: Point):
        self.dungeon.map.set(player.position, CELL_TYPE.FLOOR.value)
        player.position = cell
        self.dungeon.map.set(cell, CELL_TYPE.PLAYER.value)

    def dump_state(self):
        if not self.is_server:
            raise ValueError("Can't dump not server instance of Game")
        # положить состояние в очередь
        Queues.RENDER_QUEUE.put(self.to_dict())

    def run_player_turn(self, player: Player):
        # в начале хода задаем базовое количество AP игроку
        player.current_action_points = player.stats.action_points
        self.turn.available_moves = self.dungeon.map.get_available_moves(player)
        self.dump_state()
        while player.current_action_points > 0:
            action = self._get_player_action(player)
            action_performed, ap_cost = self.perform_player_action(player, action)
            if action_performed:
                player.current_action_points -= ap_cost
            self.dump_state()

    def run_enemy_turn(self, enemy: Enemy):
        old_position = enemy.position
        enemy.ai.perform_action(enemy=enemy, game=self)
        new_position = enemy.position
        if old_position != new_position:
            print(f"Enemy moved: {old_position}, {new_position}")
            self.dungeon.map.set(old_position, CELL_TYPE.FLOOR.value)
            self.dungeon.map.set(new_position, CELL_TYPE.ENEMY.value)
            self.dump_state()

    def run_turn(self):
        self.turn.next()
        print(f"=== TURN {self.turn.number} ===")
        self.turn.phase = GamePhase.PLAYER_PHASE
        print("Player phase")

        for player in self.players:
            self.turn.current_actor = player
            self.run_player_turn(player)

        self.turn.phase = GamePhase.ENEMY_PHASE
        print("Enemy phase")
        for enemy in self.dungeon.enemies:
            self.run_enemy_turn(enemy)

        print(f"= END TURN {self.turn.number} =")
        self.send_sound_event("turn")

    def loop(self):
        while True:
            self.run_turn()
            if self.check_game_end():
                break
        print("Game end")

    def check_game_end(self) -> bool:
        return all(p.is_dead() for p in self.players) or all(
            e.is_dead() for e in self.dungeon.enemies
        )

    def _get_player_action(self, player: Player):
        print(f"[*] Player {player.name} turn, AP {player.current_action_points}")
        while True:
            try:
                action: Action = Queues.COMMAND_QUEUE.get_nowait()
                return action
            except queue.Empty:
                pass
            time.sleep(0.05)

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
        return {
            "current_actor": self.turn.current_actor.to_dict() if self.turn.current_actor else None,
            "dungeon": self.dungeon.to_dict(),
            "players": [p.to_dict() for p in self.players],
            "turn": self.turn.to_dict(),
        }

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
        )
        return game
