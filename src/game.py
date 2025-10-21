import enum
import queue
import random
import time
from src.base import COMMAND_QUEUE, Point, PointOffset
from src.entities.player import Player
from src.dungeon import Dungeon
from src.constants import CELL_TYPE
# from InquirerLib import prompt


class GamePhase(enum.Enum):
    PLAYER_PHASE = enum.auto()
    ENEMY_PHASE = enum.auto()


class Game:
    def __init__(self, dungeon: Dungeon, players: list[Player], with_plot: bool = False):
        self.dungeon = dungeon
        self.with_plot = with_plot
        self.player_position = None
        self.phase: GamePhase = None
        self.turn = 1
        self.players = players
        if not players:
            raise ValueError("No players passed")
        self.action_choices = [
            {
                "type": "list",
                "message": "Choose action?",
                "choices": [
                    "MOVE UP",
                    "MOVE DOWN",
                    "MOVE LEFT",
                    "MOVE RIGHT",
                    "<EXIT>",
                ],
                "multiselect": False,
                "name": "class_name"
            },
        ]

    def init(self):
        self._init_players(self.dungeon.start_point)
        if self.with_plot:
            self.dungeon.map.show()

    def perform_action(self, action):
        print("Performing action", action)

    def loop(self):
        while True:
            print(f"=== TURN {self.turn} ===")
            self.phase = GamePhase.PLAYER_PHASE
            print("Player phase")
            for player in self.players:
                action = self._get_player_action(player)
                self.perform_action(action)
                if self.check_game_end():
                    break
            self.phase = GamePhase.ENEMY_PHASE
            game_end = self.enemy_phase()
            if game_end:
                break
            self.turn += 1
            print(f"= END TURN {self.turn} =")
        print("Game end")

    def enemy_phase(self) -> bool:
        print("Enemy phase")
        for enemy in self.dungeon.enemies:
            print(f"{enemy} turn")
            if self.check_game_end():
                return True
        return False

    def check_game_end(self) -> bool:
        if all([p.is_dead() for p in self.players]):
            return True
        if all([e.is_dead() for e in self.dungeon.enemies]):
            return True
        return False

    def _get_player_action(self, player: Player):
        print(f"[*] Player {player.name} turn")
        while True:
            try:
                cmd, data = COMMAND_QUEUE.get_nowait()
                print(f"[Render thread] Получена команда: {cmd}, {data}")
                return {"cmd": cmd, "data": data}
            except queue.Empty:
                pass
            time.sleep(0.05)

    def _init_players(self, point: Point):
        # все точки на расстоянии 1 клетки от point
        point_choices = [
            point,  # центр
            point.on(PointOffset.LEFT),  # слева
            point.on(PointOffset.LEFT).on(PointOffset.TOP),  # сверху-слева
            point.on(PointOffset.TOP),  # сверху
            point.on(PointOffset.TOP).on(PointOffset.RIGHT),  # сверху-справа
            point.on(PointOffset.RIGHT),  # справа
            point.on(PointOffset.RIGHT).on(PointOffset.BOTTOM),  # снизу-справа
            point.on(PointOffset.BOTTOM),  # снизу
            point.on(PointOffset.BOTTOM).on(PointOffset.LEFT),  # снизу-слева
        ]
        choices = [c for c in point_choices if self.dungeon.map.is_free(c)]
        if len(choices) < len(self.players):
            raise ValueError("Not enough place choices for all players")
        for player in self.players:
            position = random.choice(choices)
            choices.remove(position)
            player.position = position
            self.dungeon.map.set(player.position, CELL_TYPE.PLAYER.value)
        if not all(player.position is not None for player in self.players):
            raise ValueError("Not all players were placed!")
