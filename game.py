from base import Point
from dungeon.main import Dungeon
from dungeon.constants import Constants
from InquirerLib import prompt


class Game:
    def __init__(self, dungeon: Dungeon):
        self.dungeon = dungeon
        self.player_position = None
        self.turn = 0
        self.action_choices = [
            {
                "type": "list",
                "message": "Choose action?",
                "choices": [
                    "MOVE UP",
                    "MOVE DOWN",
                    "MOVE LEFT",
                    "MOVE RIGHT",
                ],
                "multiselect": False,
                "name": "class_name"
            },
        ]

    def prepare(self):
        self._place_player(self.dungeon.start_point)
        # self.dungeon.print_map()

    def perform_action(self, action):
        print(f"Performing action {action}")

    def loop(self):
        while True:
            self.turn += 1
            print(f"=== TURN {self.turn} ===")
            action = self._get_next_player_action()
            self.perform_action(action)
            print("=========================")

    def _get_next_player_action(self):
        return prompt(self.action_choices)

    def _place_player(self, point: Point):
        # check for walls
        tile = self.dungeon.tiles[point.x][point.y]
        if tile == Constants.WALL:
            raise ValueError("can't place player on wall")
        self.player_position = point
        self.dungeon.tiles[point.x][point.y] = Constants.PLAYER
