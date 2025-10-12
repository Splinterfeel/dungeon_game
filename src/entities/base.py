from dataclasses import dataclass
from src.base import Point


class Entity:
    position: Point


@dataclass
class CharacterStats:
    health: int
    damage: int
    speed: int


class Actor:
    def is_dead(self) -> bool:
        return self.stats.health <= 0
