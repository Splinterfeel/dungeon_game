from src.base import Point
from src.entities.base import Actor, CharacterStats


class Player(Actor):
    name: str

    def to_dict(self):
        return super().to_dict() | {"name": self.name}

    @classmethod
    def from_dict(cls, _dict):
        return cls(
            **{
                "position": (
                    Point.from_dict(_dict["position"]) if _dict["position"] else None
                ),
                "stats": CharacterStats.from_dict(_dict["stats"]),
                "name": _dict["name"],
            }
        )

    def __str__(self):
        return f"Player {self.name}"
