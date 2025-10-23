from src.base import Point, PointOffset
from src.constants import CELL_TYPE
from src.entities.base import Actor


class DungeonMap:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.tiles = [
            [CELL_TYPE.WALL.value for _ in range(self.height)]
            for _ in range(self.width)
        ]

    def get(self, point: Point):
        return self.tiles[point.x][point.y]

    def set(self, point: Point, value):
        self.tiles[point.x][point.y] = value

    def is_free(self, point: Point) -> bool:
        if self.get(point) == CELL_TYPE.FLOOR.value:
            return True
        return False

    def get_avaliable_moves(self, actor: Actor) -> list[Point]:
        cells = [
            actor.position.on(PointOffset.LEFT),
            actor.position.on(PointOffset.LEFT).on(PointOffset.LEFT),
            actor.position.on(PointOffset.LEFT).on(PointOffset.TOP),
            actor.position.on(PointOffset.LEFT).on(PointOffset.BOTTOM),
            actor.position.on(PointOffset.RIGHT),
            actor.position.on(PointOffset.RIGHT).on(PointOffset.RIGHT),
            actor.position.on(PointOffset.RIGHT).on(PointOffset.TOP),
            actor.position.on(PointOffset.RIGHT).on(PointOffset.BOTTOM),
            actor.position.on(PointOffset.TOP),
            actor.position.on(PointOffset.TOP).on(PointOffset.TOP),
            actor.position.on(PointOffset.BOTTOM),
            actor.position.on(PointOffset.BOTTOM).on(PointOffset.BOTTOM),
        ]
        free_cells = [cell for cell in cells if self.is_free(cell)]
        return free_cells
