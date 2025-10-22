from dataclasses import dataclass
from src.base import Point


class Entity:
    def __init__(self, position: Point):
        self.position = position


@dataclass
class CharacterStats:
    health: int
    damage: int
    speed: int


class Actor(Entity):
    def __init__(self, position: Point, stats: CharacterStats):
        super().__init__(position=position)
        self.stats = stats

    def is_dead(self) -> bool:
        return self.stats.health <= 0
