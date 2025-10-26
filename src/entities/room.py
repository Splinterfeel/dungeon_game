from typing import Self

from src.base import Point


class Room:
    def __init__(self, x: int, y: int, width: int, height: int):
        self.x = x
        self.y = y
        self.width = width
        self.height = height

    # A helper method to get the center point of the room, useful for connecting rooms later.
    def center(self) -> Point:
        center_x = self.x + self.width // 2
        center_y = self.y + self.height // 2
        return Point(center_x, center_y)

    def intersects(self, other: Self) -> bool:
        # Check if they don't overlap first.
        # If any of these conditions are true, they do not intersect.
        if self.x > other.x + other.width:
            return False
        if self.x + self.width < other.x:
            return False
        if self.y > other.y + other.height:
            return False
        if self.y + self.height < other.y:
            return False
        # If none of the non-overlapping conditions are true, they must intersect.
        return True

    def to_dict(self):
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }

    @classmethod
    def from_dict(cls, _dict: dict):
        return cls(**_dict)
