from collections import deque
from src.base import Point, PointOffset
from src.constants import CELL_TYPE
from src.entities.base import Actor


class DungeonMap:
    def __init__(self, width: int, height: int, tiles: list[str] = None):
        self.width = width
        self.height = height
        if tiles:
            self.tiles = tiles
        else:
            self.tiles = [
                [CELL_TYPE.WALL.value for _ in range(self.height)]
                for _ in range(self.width)
            ]

    def to_dict(self):
        return {
            "width": self.width,
            "height": self.height,
            "tiles": self.tiles,
        }

    @classmethod
    def from_dict(cls, _dict: dict):
        return cls(**_dict)

    def get(self, point: Point):
        return self.tiles[point.x][point.y]

    def set(self, point: Point, value):
        self.tiles[point.x][point.y] = value

    def is_free(self, point: Point) -> bool:
        if self.get(point) == CELL_TYPE.FLOOR.value:
            return True
        return False

    def get_available_moves(self, actor: Actor) -> list[Point]:
        "Возвращает список всех достижимых клеток за указанную скорость (BFS)"
        visited = {actor.position}
        available = []
        queue = deque([(actor.position, 0)])
        directions = [
            PointOffset.LEFT,
            PointOffset.RIGHT,
            PointOffset.TOP,
            PointOffset.BOTTOM,
        ]
        # сколько клеток может пройти
        _speed = actor.stats.speed - actor.current_speed_spent
        assert _speed >= 0
        while queue:
            point, distance = queue.popleft()
            # если точка достижима с текущей скоростью
            if 0 < distance <= _speed:
                available.append(point)
            # если точка - крайняя, которая достижима, то уже не пытаемся идти еще куда-то
            if distance >= _speed:
                continue
            # добавляем соседние точки для анализа
            for offset in directions:
                next_point = point.on(offset)
                if next_point not in visited and self.is_free(next_point):
                    visited.add(next_point)
                    queue.append((next_point, distance + 1))
        return available

    def bfs_path(self, start: Point, goal: Point) -> list[Point] | None:
        """
        Находит кратчайший путь от start до goal (BFS).
        Возвращает список клеток от старта до цели включительно.
        """
        queue = deque([(start, [start])])
        # goal_cell_type = self.get(goal)
        visited = {start}

        directions = [
            PointOffset.LEFT,
            PointOffset.RIGHT,
            PointOffset.TOP,
            PointOffset.BOTTOM,
        ]

        while queue:
            point, path = queue.popleft()
            if point == goal:
                return path

            for offset in directions:
                next_point = point.on(offset)
                if next_point not in visited and (
                    self.is_free(next_point)
                    or next_point == goal
                ):
                    visited.add(next_point)
                    queue.append((next_point, path + [next_point]))
        return None  # путь не найден
