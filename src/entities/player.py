from src.base import Point
from src.entities.base import Actor, CharacterStats


class Player(Actor):
    def __init__(self, positon: Point, name: str, stats: CharacterStats):
        super().__init__(position=positon, stats=stats)
        self.name = name
