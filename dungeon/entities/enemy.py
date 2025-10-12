from base import Point
from dungeon.entities.base import CharacterStats, Entity


class Enemy(Entity):
    def __init__(self, position: Point, stats: CharacterStats):
        self.position = position
        self.stats = stats
        super().__init__()
