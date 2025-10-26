from dataclasses import dataclass
from src.base import Point


class Entity:
    def __init__(self, position: Point):
        self.position = position

    def to_dict(self):
        return {
            "position": self.position.to_dict(),
        }

    @classmethod
    def from_dict(cls, _dict: dict):
        return cls(Point.from_dict(_dict["position"]))

    def __eq__(self, value):
        if not isinstance(value, Entity):
            raise ValueError(f"Cant compare {type(self)} with {type(value)}")
        return self.position == value.position


@dataclass
class CharacterStats:
    health: int
    damage: int
    speed: int

    def to_dict(self):
        return {
            "health": self.health,
            "damage": self.damage,
            "speed": self.speed,
        }

    @classmethod
    def from_dict(cls, _dict: dict):
        return cls(**_dict)


class Actor(Entity):
    def __init__(self, position: Point, stats: CharacterStats):
        super().__init__(position=position)
        self.stats = stats

    def is_dead(self) -> bool:
        return self.stats.health <= 0

    def to_dict(self):
        return {
            "position": self.position.to_dict(),
            "stats": self.stats.to_dict(),
        }

    @classmethod
    def from_dict(cls, _dict: dict):
        return cls(
            **{
                "position": Point.from_dict(_dict["position"]),
                "stats": CharacterStats.from_dict(_dict["stats"]),
            }
        )
