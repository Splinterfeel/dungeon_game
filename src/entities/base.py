from pydantic import BaseModel
from src.base import Point


class Entity(BaseModel):
    position: Point | None

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


class CharacterStats(BaseModel):
    health: int
    damage: int
    speed: int  # сколько клеток может пройти за ход
    action_points: int

    def to_dict(self):
        return {
            "health": self.health,
            "damage": self.damage,
            "speed": self.speed,
            "action_points": self.action_points,
        }

    @classmethod
    def from_dict(cls, _dict: dict):
        return cls(**_dict)


class Actor(Entity):
    stats: CharacterStats
    current_action_points: int = 0
    current_speed_spent: int = 0  # сколько клеток прошел за ход

    def is_dead(self) -> bool:
        return self.stats.health <= 0

    def to_dict(self):
        return {
            "position": self.position.to_dict() if self.position else None,
            "stats": self.stats.to_dict(),
        }

    def apply_damage(self, damage: int):
        self.stats.health = max(self.stats.health - damage, 0)

    @classmethod
    def from_dict(cls, _dict: dict):
        return cls(
            **{
                "position": Point.from_dict(_dict["position"]),
                "stats": CharacterStats.from_dict(_dict["stats"]),
            }
        )
