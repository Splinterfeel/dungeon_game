from src.base import Point
from src.entities.base import Entity


class Chest(Entity):
    def __init__(self, position: Point, gold: int):
        super().__init__(position=position)
        self.gold = gold

    def __str__(self):
        return f"Chest [{self.position.x}, {self.position.y}], gold {self.gold}"
