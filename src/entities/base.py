from typing import Annotated, ClassVar, Dict
import uuid
import names
from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, model_validator
from src.base import Point
from typing import Literal


UUIDStr = Annotated[uuid.UUID, PlainSerializer(lambda x: str(x), return_type=str)]


class Entity(BaseModel):
    position: Point | None = Field(default_factory=lambda: Point(x=0, y=0))
    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __eq__(self, value):
        if not isinstance(value, Entity):
            raise ValueError(f"Cant compare {type(self)} with {type(value)}")
        return self.position == value.position


class CharacterStats(BaseModel):
    health: int
    damage: int
    speed: int  # сколько клеток может пройти за ход
    action_points: int


class Weapon(BaseModel):
    id: UUIDStr = Field(default_factory=uuid.uuid4)
    type: Literal["melee", "ranged"]
    name: str
    damage: int
    cost_ap: int
    range: int
    accuracy: int


class Inventory(BaseModel):
    weapons: list[Weapon]


class Actor(Entity):
    _registry: ClassVar[Dict[uuid.UUID, "Actor"]] = {}
    id: UUIDStr = Field(default_factory=uuid.uuid4)
    stats: CharacterStats
    inventory: Inventory
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

    def apply_damage(self, damage: int):
        self.stats.health = max(self.stats.health - damage, 0)

    def __str__(self):
        return f"[{self.id}] {self.name}"

    def __eq__(self, value):
        return self.id == value.id
