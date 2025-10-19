from enum import Enum, auto
import math
from dataclasses import dataclass
import queue
from typing import Self


COMMAND_QUEUE = queue.Queue()


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

    @staticmethod
    def get_distance(point_1: Self, point_2: Self) -> int:
        delta_x = point_2.x - point_1.x
        delta_y = point_2.y - point_1.y
        squared_delta_x = delta_x ** 2
        squared_delta_y = delta_y ** 2
        sum_of_squares = squared_delta_x + squared_delta_y
        return math.sqrt(sum_of_squares)
