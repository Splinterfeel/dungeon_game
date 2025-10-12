import random
from src.base import Point, PointOffset
from src.entities.player import Player
from src.dungeon import Dungeon
from src.constants import Constants
from InquirerLib import prompt


class Game:
    def __init__(self, dungeon: Dungeon, players: list[Player], with_plot: bool = False):
        self.dungeon = dungeon
        self.with_plot = with_plot
        self.player_position = None
        self.turn = 0
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

    def prepare(self):
        self._init_players(self.dungeon.start_point)
        if self.with_plot:
            self.dungeon.map.show()

    def perform_action(self, action):
        match action["class_name"]:
            case "<EXIT>":
                self.dungeon.map.destroy()
                exit()
            case _:
                print(f"Unknown action {action}")

    def loop(self):
        while True:
            self.turn += 1
            print(f"=== TURN {self.turn} ===")
            action = self._get_next_player_action()
            self.perform_action(action)
            print("=========================")

    def _get_next_player_action(self):
        return prompt(self.action_choices)

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
            self.dungeon.map.set(player.position, Constants.PLAYER)
        if not all(player.position is not None for player in self.players):
            raise ValueError("Not all players were placed!")
