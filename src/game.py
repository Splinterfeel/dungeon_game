import queue
import random
import time
from src.action import Action, ActionType
from src.base import Point, PointOffset, Queues
from src.entities.player import Player
from src.dungeon import Dungeon
from src.constants import CELL_TYPE
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

    def perform_player_action(self, player: Player, action: Action) -> bool:
        "True если действие выполнено успешно, иначе False"
        if self.turn.current_actor != player:
            raise ValueError(f"Attempt to perform action of player {player} when turn of player {self.turn.current_actor}")  # noqa
        match action.type:
            case ActionType.MOVE:
                if action.cell not in self.turn.available_moves:
                    print(f"Can't move player {player} to cell {action.cell}")
                    return False
                if not self.dungeon.map.is_free(action.cell):
                    print(f"Cell {action.cell} is not free, can't move {player} here")
                    return False
                self.move_player(player, action.cell)
                return True
            case ActionType.ATTACK_ENEMY:
                if self.dungeon.map.get(action.cell) != CELL_TYPE.ENEMY.value:
                    print(f"Attempt to attack {action.cell}, cell is not enemy")
                    return False
                if Point.distance_chebyshev(player.position, action.cell) > 1:
                    print(f"Attempt to attack {action.cell}, but it's too far: {Point.distance_chebyshev(player.position, action.cell)}")  # noqa
                    return False
                print(f"Attacking enemy at {action.cell}")
            case _:
                print("Performing action", action)
                return True

    def move_player(self, player: Player, cell: Point):
        self.dungeon.map.set(player.position, CELL_TYPE.FLOOR.value)
        player.position = cell
        self.dungeon.map.set(cell, CELL_TYPE.PLAYER.value)

    def dump_state(self):
        if not self.is_server:
            raise ValueError("Can't dump not server instance of Game")
        # положить состояние в очередь
        Queues.RENDER_QUEUE.put(self.to_dict())

    def peform_player_turn(self, player: Player):
        self.turn.available_moves = self.dungeon.map.get_avaliable_moves(player)
        player_turn_end = False
        self.dump_state()
        while not player_turn_end:
            action = self._get_player_action(player)
            action_performed = self.perform_player_action(player, action)
            if action_performed:
                player_turn_end = action.ends_turn

    def run_turn(self):
        self.turn.next()
        print(f"=== TURN {self.turn.number} ===")
        self.turn.phase = GamePhase.PLAYER_PHASE
        print("Player phase")

        for player in self.players:
            self.turn.current_actor = player
            self.peform_player_turn(player)

        self.turn.phase = GamePhase.ENEMY_PHASE
        print("Enemy phase")
        for enemy in self.dungeon.enemies:
            print(f"{enemy} turn")

        print(f"= END TURN {self.turn.number} =")

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
        print(f"[*] Player {player.name} turn")
        while True:
            try:
                action: Action = Queues.COMMAND_QUEUE.get_nowait()
                print(f"[Game thread] Получена команда: {action}")
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
