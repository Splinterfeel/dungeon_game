from src.base import Point
from src.constants import CELL_TYPE


class DungeonMap:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.tiles = [
            [
                CELL_TYPE.WALL.value for _ in range(self.height)
            ] for _ in range(self.width)
        ]

    def get(self, point: Point):
        return self.tiles[point.x][point.y]

    def set(self, point: Point, value):
        self.tiles[point.x][point.y] = value

    def is_free(self, point: Point) -> bool:
        if self.get(point) == CELL_TYPE.FLOOR.value:
            return True
        return False
