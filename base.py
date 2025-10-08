import math
from dataclasses import dataclass


@dataclass
class Point:
    x: int
    y: int


def get_distance(point_1: Point, point_2: Point) -> int:
    delta_x = point_2.x - point_1.x
    delta_y = point_2.y - point_1.y
    squared_delta_x = delta_x ** 2
    squared_delta_y = delta_y ** 2
    sum_of_squares = squared_delta_x + squared_delta_y
    return math.sqrt(sum_of_squares)
