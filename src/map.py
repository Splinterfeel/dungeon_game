from collections import deque
from typing import List

from pydantic import BaseModel, Field, model_validator
from src.base import Point, PointOffset
from src.constants import CELL_TYPE
from src.entities.base import Actor, Entity, Weapon


class DungeonMap(BaseModel):
    width: int
    height: int
    tiles: List[List[str]] = Field(default=None)

    @model_validator(mode="after")
    def initialize_tiles(self) -> "DungeonMap":
        # Если tiles не переданы, создаем пустую карту из стен
        if self.tiles is None:
            self.tiles = [
                [CELL_TYPE.WALL.value for _ in range(self.height)]
                for _ in range(self.width)
            ]
        return self

    def get(self, point: Point):
        return self.tiles[point.x][point.y]

    def set(self, point: Point, value):
        self.tiles[point.x][point.y] = value

    def is_free(self, point: Point, game: "Game" = None) -> bool:
        # Check map cell type
        if self.get(point) != CELL_TYPE.EMPTY.value and self.get(point) != CELL_TYPE.EXIT.value:
            return False

        # If game instance provided, check actual actor occupancy
        if game is not None:
            actor = game.get_actor_at_cell(point)
            if actor is not None:
                return False  # Cell occupied by actor

        return True

    def clear_start_points(self):
        "Поставить EMPTY в точки старта команд"
        start_points = {CELL_TYPE.START_TEAM_1.value, CELL_TYPE.START_TEAM_2.value}
        for x in range(self.width):
            for y in range(self.height):
                p = Point(x=x, y=y)
                if self.get(p) in start_points:
                    self.set(p, CELL_TYPE.EMPTY.value)

    def get_available_moves(self, actor: Actor, game: "Game" = None) -> list[Point]:
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
        _speed = min(
            actor.stats.speed - actor.current_speed_spent, actor.current_action_points
        )
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
                if next_point not in visited and (
                    self.is_free(next_point, game)
                    or self.get(next_point) == CELL_TYPE.EXIT.value
                ):
                    visited.add(next_point)
                    queue.append((next_point, distance + 1))
        return available

    def bfs_path(self, start: Point, goal: Point, game: "Game" = None) -> list[Point] | None:
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
                    self.is_free(next_point, game) or next_point == goal
                ):
                    visited.add(next_point)
                    queue.append((next_point, path + [next_point]))
        return None  # путь не найден

    def has_line_of_sight(
        self, start: Point, end: Point, through_entities: bool
    ) -> bool:
        """Простая проверка: есть ли стены между двумя точками"""
        points = Point.get_line_points(start, end)
        # Убираем первую точку (самого игрока) и последнюю (цель)
        # игроки, враги, сундуки не преграждают видимость
        # только стены
        for p in points[1:-1]:
            # не считаем предметы/игроков/сундуки/врагов как преграды
            if through_entities and self.get(p) == CELL_TYPE.WALL.value:
                return False
            elif not through_entities and not self.is_free(p):
                return False
        return True

    def can_see(self, actor: Actor, entity: Entity) -> bool:
        can_see_by_view_distance = (
            Point.distance_euklid(actor.position, entity.position)
            <= actor.stats.view_distance
        )
        has_line_of_sight = self.has_line_of_sight(
            actor.position, entity.position, through_entities=True
        )
        return can_see_by_view_distance and has_line_of_sight

    def can_shoot(self, actor: Actor, weapon: Weapon, point: Point) -> bool:
        _distance = Point.distance_euklid(actor.position, point)
        can_see_by_view_distance = _distance <= actor.stats.view_distance
        can_shoot_by_range = _distance <= weapon.range
        has_line_of_sight = self.has_line_of_sight(
            actor.position, point, through_entities=False
        )
        return can_see_by_view_distance and can_shoot_by_range and has_line_of_sight
