from src.base import Point
from src.entities.base import Actor, CharacterStats, Entity


class Player(Actor, Entity):
    def __init__(self, positon: Point, name: str, stats: CharacterStats):
        self.name = name
        self.position = positon
        self.stats = stats
        super().__init__()
