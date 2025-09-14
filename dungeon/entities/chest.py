from base import Point


class Chest:
    def __init__(self, position: Point, gold: int):
        self.position = position
        self.gold = gold

    def __str__(self):
        return f"Chest [{self.position.x}, {self.position.y}], gold {self.gold}"
