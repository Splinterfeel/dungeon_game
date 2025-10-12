from base import Point
from src.entities.base import Entity


class Chest(Entity):
    def __init__(self, position: Point, gold: int):
        self.position = position
        self.gold = gold
        super().__init__()

    def __str__(self):
        return f"Chest [{self.position.x}, {self.position.y}], gold {self.gold}"
