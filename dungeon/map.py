import colorama
from base import Point
from dungeon.constants import Colors, Constants


class DungeonMap:
    def __init__(self, width: int, height: int):
        self._width = width
        self._height = height
        self.tiles = [
            [
                Constants.WALL for _ in range(self._height)
            ] for _ in range(self._width)
        ]

    def get(self, point: Point):
        return self.tiles[point.x][point.y]

    def set(self, point: Point, value):
        self.tiles[point.x][point.y] = value

    def print(self):
        for y in range(self._height):
            line = ""
            for x in range(self._width):
                value = self.get(Point(x, y))
                line += Colors.get(value, colorama.Fore.BLACK)
                line += value
            print(line)
