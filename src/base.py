from enum import Enum, auto
import math
from typing import Self

from pydantic import BaseModel


class PointOffset(Enum):
    TOP = auto()
    BOTTOM = auto()
    LEFT = auto()
    RIGHT = auto()


class Point(BaseModel):
    x: int
    y: int

    def on(self, offset: PointOffset):
        match offset:
            case PointOffset.TOP:
                return Point(x=self.x, y=self.y - 1)
            case PointOffset.BOTTOM:
                return Point(x=self.x, y=self.y + 1)
            case PointOffset.LEFT:
                return Point(x=self.x - 1, y=self.y)
            case PointOffset.RIGHT:
                return Point(x=self.x + 1, y=self.y)

    def __eq__(self, value):
        if not isinstance(value, Point):
            raise ValueError(f"Can't compare Point with {type(value)}")
        return self.x == value.x and self.y == value.y

    @staticmethod
    def distance_euklid(point_1: Self, point_2: Self) -> int:
        delta_x = point_2.x - point_1.x
        delta_y = point_2.y - point_1.y
        squared_delta_x = delta_x**2
        squared_delta_y = delta_y**2
        sum_of_squares = squared_delta_x + squared_delta_y
        return math.sqrt(sum_of_squares)

    @staticmethod
    def distance_manhattan(point_1: Self, point_2: Self) -> int:
        return abs(point_1.x - point_2.x) + abs(point_1.y - point_2.y)

    @staticmethod
    def distance_chebyshev(point_1: Self, point_2: Self) -> int:
        delta_x = point_2.x - point_1.x
        delta_y = point_2.y - point_1.y
        return max(abs(delta_x), abs(delta_y))

    def __hash__(self):
        return hash((self.x, self.y))

    @staticmethod
    def get_line_points(p1: Self, p2: Self):
        """Алгоритм Брезенхема для получения списка точек линии"""
        x1, y1 = p1.x, p1.y
        x2, y2 = p2.x, p2.y
        points = []
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        x, y = x1, y1
        sx = -1 if x1 > x2 else 1
        sy = -1 if y1 > y2 else 1

        if dx > dy:
            err = dx / 2.0
            while x != x2:
                points.append(Point(x=x, y=y))
                err -= dy
                if err < 0:
                    y += sy
                    err += dx
                x += sx
        else:
            err = dy / 2.0
            while y != y2:
                points.append(Point(x=x, y=y))
                err -= dx
                if err < 0:
                    x += sx
                    err += dy
                y += sy
        points.append(Point(x=x, y=y))
        return points
