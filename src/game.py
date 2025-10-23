import queue
import random
import threading
import time
from src.action import Action, ActionType
from src.base import COMMAND_QUEUE, Point, PointOffset
from src.entities.player import Player
from src.dungeon import Dungeon
from src.constants import CELL_TYPE
from src.turn import GamePhase, Turn
from src.visualization import render_thread


class Game:
    def __init__(
        self, dungeon: Dungeon, players: list[Player], with_plot: bool = False
    ):
        self.plt_thread: threading.Thread = None
        self.dungeon = dungeon
        self.with_plot = with_plot
        self.player_position = None
        self.turn: Turn = Turn()
        self.players = players
        if not players:
            raise ValueError("No players passed")

    def init(self):
        self._init_players(self.dungeon.start_point)
        if self.with_plot:
            self.plt_thread = threading.Thread(target=render_thread, args=[self])
            self.plt_thread.start()

    def perform_player_action(self, player: Player, action: Action):
        match action.type:
            case ActionType.MOVE:
                self.move_player(player, action.cell)
            case _:
                print("Performing action", action)
        print()

    def move_player(self, player: Player, cell: Point):
        self.dungeon.map.set(player.position, CELL_TYPE.FLOOR.value)
        player.position = cell
        self.dungeon.map.set(cell, CELL_TYPE.PLAYER.value)

    def peform_player_turn(self, player: Player):
        self.turn.available_moves = self.dungeon.map.get_avaliable_moves(player)
        # возможная предобработка доступных клеток для перемещения
        # можно выполнять сколько угодно действий, не завершающих ход
        player_turn_end = False
        while not player_turn_end:
            action = self._get_player_action(player)
            self.perform_player_action(player, action)
            player_turn_end = action.ends_turn
        # очищаем доступные для хода клетки

    def run_turn(self):
        self.turn.next()
        print(f"=== TURN {self.turn.number} ===")
        self.turn.phase = GamePhase.PLAYER_PHASE
        print("Player phase")
        for player in self.players:
            self.turn.current_actor = player
            self.peform_player_turn(player)
        self.phase = GamePhase.ENEMY_PHASE
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
        if all([p.is_dead() for p in self.players]):
            return True
        if all([e.is_dead() for e in self.dungeon.enemies]):
            return True
        return False

    def _get_player_action(self, player: Player):
        print(f"[*] Player {player.name} turn")
        while True:
            try:
                action: Action = COMMAND_QUEUE.get_nowait()
                print(f"[Game thread] Получена команда: {action}")
                return action
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
