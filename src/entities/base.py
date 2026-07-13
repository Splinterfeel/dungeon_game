import random
from typing import Annotated, ClassVar, Dict, Optional
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
    max_health: int = 0
    melee_power: int  # бонус к урону оружия ближнего боя, приходит от детали "руки"
    speed: int  # сколько клеток может пройти за ход
    action_points: int
    view_distance: int
    accuracy: int

    @model_validator(mode="after")
    def set_max_health(self):
        if self.max_health == 0:
            self.max_health = self.health
        return self


class Weapon(BaseModel):
    # разброс урона одного попадания: ±DAMAGE_VARIANCE от Weapon.damage
    # (см. ROADMAP.md, Этап 2, "разброс урона") - убирает полную
    # детерминированность урона, одинаково для ближнего и дальнего оружия
    DAMAGE_VARIANCE: ClassVar[float] = 0.125

    id: UUIDStr = Field(default_factory=uuid.uuid4)
    type: Literal["melee", "ranged"]
    name: str
    damage: int
    cost_ap: int
    range: int
    accuracy: int

    def roll_damage(self) -> int:
        "Урон одного попадания с разбросом ±DAMAGE_VARIANCE, округление к целому, минимум 1"
        multiplier = random.uniform(1 - self.DAMAGE_VARIANCE, 1 + self.DAMAGE_VARIANCE)
        return max(1, round(self.damage * multiplier))

    def calculate_hit_chance(self, actor_stats: CharacterStats, distance: int) -> float:
        if distance > self.range:
            return 0.0
        base_chance = actor_stats.accuracy * (self.accuracy / 100.0)
        if self.type != "melee":
            distance_penalty = (distance - 1) * (20 / self.range)
            hit_chance = base_chance - distance_penalty
        else:
            hit_chance = base_chance
        return max(0.05, min(0.95, hit_chance / 100.0))

    def check_hit(self, actor_stats: CharacterStats, distance: int) -> bool:
        chance = self.calculate_hit_chance(actor_stats=actor_stats, distance=distance)
        return random.random() <= chance


class Inventory(BaseModel):
    weapons: list[Weapon]


class OverwatchState(BaseModel):
    weapon_id: UUIDStr


class Actor(Entity):
    _registry: ClassVar[Dict[uuid.UUID, "Actor"]] = {}
    id: UUIDStr = Field(default_factory=uuid.uuid4)
    stats: CharacterStats
    inventory: Inventory
    current_action_points: int = 0
    current_speed_spent: int = 0  # сколько клеток прошел за ход
    name: str = Field(default_factory=names.get_full_name)
    overwatch: Optional[OverwatchState] = None
    trophies: list[str] = Field(default_factory=list)

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
