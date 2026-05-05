from src.base import Point
from src.entities.base import Entity


class Chest(Entity):
    gold: int

    def __str__(self):
        return f"Chest [{self.position.x}, {self.position.y}], gold {self.gold}"
