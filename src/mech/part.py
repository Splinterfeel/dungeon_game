import uuid
from collections.abc import Mapping
from enum import Enum
from typing import ClassVar

from pydantic import BaseModel, Field, computed_field, model_validator

from src.entities.base import UUIDStr


class PartSlot(str, Enum):
    TORSO = "torso"
    LEGS = "legs"
    ARMS = "arms"
    HEAD = "head"


class PartRarity(str, Enum):
    COMMON = "common"
    RARE = "rare"
    EPIC = "epic"


class Part(BaseModel):
    # локальная прочность детали (locational damage), отдельная от
    # CharacterStats.health - см. ROADMAP.md, Этап 2 п.2. Одна прочность
    # на все детали пока что, веса/числа не балансировались отдельно.
    DEFAULT_MAX_HEALTH: ClassVar[int] = 10

    id: UUIDStr = Field(default_factory=uuid.uuid4)
    # Идентификатор типа детали в каталоге. Экземплярный id отличает две
    # полученные детали, а catalog_key нужен для защиты от дублей в гараже.
    catalog_key: str
    slot: PartSlot
    name: str
    rarity: PartRarity = PartRarity.COMMON
    health: int = 0
    speed: int = 0
    accuracy: int = 0
    melee_power: int = 0
    view_distance: int = 0
    max_health: int = 0
    current_health: int = 0
    # вес детали - расходует весовой бюджет меха (ROADMAP.md, Этап 2 п.9),
    # заполняется у деталей всех слотов
    weight: int = 0
    # грузоподъёмность, которую деталь даёт мехам - по конвенции значима
    # только у slot=LEGS (аналог melee_power, значимого только у ARMS)
    carry_capacity: int = 0
    affix_tier: int = 0
    affix_stat: str | None = None
    affix_value: int = 0

    @model_validator(mode="before")
    @classmethod
    def set_initial_durability(cls, data):
        """Отсутствующая прочность — полная; явный ноль — уничтоженная деталь."""
        if isinstance(data, Mapping):
            data = dict(data)
            data["max_health"] = data.get("max_health") or cls.DEFAULT_MAX_HEALTH
            data.setdefault("current_health", data["max_health"])
        return data

    @computed_field  # type: ignore[misc]
    @property
    def destroyed(self) -> bool:
        return self.current_health <= 0

    def fresh_copy(self, *, keep_id: bool = False) -> "Part":
        max_health = self.max_health or self.DEFAULT_MAX_HEALTH
        return self.model_copy(
            update={
                "id": self.id if keep_id else uuid.uuid4(),
                "max_health": max_health,
                "current_health": max_health,
            }
        )

    def apply_damage(self, damage: int) -> None:
        self.current_health = max(self.current_health - damage, 0)
