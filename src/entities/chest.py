from src.base import Point
from src.entities.base import Entity


class Chest(Entity):
    gold: int

    def __str__(self):
        return f"Chest [{self.position.x}, {self.position.y}], gold {self.gold}"

    def to_dict(self):
        return {
            "position": self.position.to_dict(),
            "gold": self.gold,
        }

    @classmethod
    def from_dict(cls, _dict: dict):
        return cls(
            **{
                "position": Point.from_dict(_dict["position"]),
                "gold": _dict["gold"],
            }
        )
