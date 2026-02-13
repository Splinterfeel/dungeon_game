from typing import ClassVar, Dict
import uuid
import names
from pydantic import BaseModel, ConfigDict, Field, model_validator
from src.base import Point


class Entity(BaseModel):
    position: Point | None = Point(0, 0)
    model_config = ConfigDict(arbitrary_types_allowed=True)

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
    _registry: ClassVar[Dict[uuid.UUID, "Actor"]] = {}
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    stats: CharacterStats
    current_action_points: int = 0
    current_speed_spent: int = 0  # сколько клеток прошел за ход
    name: str = Field(default_factory=names.get_full_name)

    @model_validator(mode="after")
    def register_instance(self):
        self.__class__._registry[self.id] = self
        return self

    @classmethod
    def get_actor_instance(cls, actor_id: uuid.UUID) -> "Actor | None":
        return cls._registry.get(actor_id)

    def is_dead(self) -> bool:
        return self.stats.health <= 0

    def to_dict(self):
        return {
            "id": self.id,
            "position": self.position.to_dict() if self.position else None,
            "stats": self.stats.to_dict(),
            "name": self.name,
            "current_action_points": self.current_action_points,
            "current_speed_spent": self.current_speed_spent,
        }

    def apply_damage(self, damage: int):
        self.stats.health = max(self.stats.health - damage, 0)

    @classmethod
    def from_dict(cls, _dict: dict):
        return cls(
            **{
                "id": _dict["id"],
                "name": _dict["name"],
                "position": (
                    Point.from_dict(_dict["position"]) if _dict["position"] else None
                ),
                "stats": CharacterStats.from_dict(_dict["stats"]),
                "current_action_points": _dict["current_action_points"],
                "current_speed_spent": _dict["current_speed_spent"],
            }
        )

    def __str__(self):
        return f"[{self.id}] {self.name}"

    def __eq__(self, value):
        return self.id == value.id
