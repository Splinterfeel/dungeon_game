from src.base import Point
from src.entities.base import Actor, CharacterStats, Entity


class Enemy(Actor, Entity):
    def __init__(self, position: Point, stats: CharacterStats):
        self.position = position
        self.stats = stats
        super().__init__()
