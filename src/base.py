from enum import Enum, auto
import math
from dataclasses import dataclass
import queue
from typing import Self


class Queues:
    COMMAND_QUEUE = queue.Queue()
    RENDER_QUEUE = queue.Queue()
    PLAYER_QUEUES: dict[str, queue.Queue] = dict()


class PointOffset(Enum):
    TOP = auto()
    BOTTOM = auto()
    LEFT = auto()
    RIGHT = auto()


@dataclass
class Point:
    x: int
    y: int

    def on(self, offset: PointOffset):
        match offset:
            case PointOffset.TOP:
                return Point(self.x, self.y - 1)
            case PointOffset.BOTTOM:
                return Point(self.x, self.y + 1)
            case PointOffset.LEFT:
                return Point(self.x - 1, self.y)
            case PointOffset.RIGHT:
                return Point(self.x + 1, self.y)

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

    def to_dict(self):
        return {
            "x": self.x,
            "y": self.y,
        }

    @classmethod
    def from_dict(cls, _dict: dict):
        return cls(**_dict)

    @staticmethod
    def distance_chebyshev(point_1: Self, point_2: Self) -> int:
        delta_x = point_2.x - point_1.x
        delta_y = point_2.y - point_1.y
        return max(abs(delta_x), abs(delta_y))

    def __hash__(self):
        return hash((self.x, self.y))
