from src.base import Point
from src.entities.base import Actor, CharacterStats


class Player(Actor):
    def __init__(self, position: Point, name: str, stats: CharacterStats):
        super().__init__(position=position, stats=stats)
        self.name = name

    def to_dict(self):
        return super().to_dict() | {"name": self.name}

    @classmethod
    def from_dict(cls, _dict):
        return cls(
            **{
                "position": Point.from_dict(_dict["position"]),
                "stats": CharacterStats.from_dict(_dict["stats"]),
                "name": _dict["name"]
            }
        )
