import random
from typing import ClassVar, Optional

from pydantic import BaseModel, model_validator

from src.entities.base import CharacterStats
from src.entities.part import Part, PartSlot


class Mech(BaseModel):
    # веса случайного выбора части при попадании (locational damage,
    # см. ROADMAP.md, Этап 2 п.2) - торс чаще конечностей, конкретные
    # числа не балансировались отдельно.
    HIT_WEIGHTS: ClassVar[dict[str, float]] = {
        "torso": 0.4,
        "legs": 0.2,
        "arms": 0.2,
        "head": 0.2,
    }

    torso: Part
    legs: Part
    arms: Part
    head: Part
    # имя пресета (см. src/mech_presets.py), из которого собран этот мех -
    # None для мехов без пресета (default_mech() и т.п.); нужно только для
    # показа лора пресета в дебаг-инспекторе, на игровую логику не влияет
    preset_name: Optional[str] = None

    @model_validator(mode="after")
    def check_slots(self) -> "Mech":
        expected_slots = {
            "torso": PartSlot.TORSO,
            "legs": PartSlot.LEGS,
            "arms": PartSlot.ARMS,
            "head": PartSlot.HEAD,
        }
        for field_name, expected_slot in expected_slots.items():
            part: Part = getattr(self, field_name)
            if part.slot != expected_slot:
                raise ValueError(
                    f"{field_name} ожидает деталь слота {expected_slot}, получена {part.slot}"
                )
        return self

    def build_character_stats(self, action_points: int) -> CharacterStats:
        "Совокупные статы меха = сумма характеристик всех деталей + очки действия пилота"
        parts = [self.torso, self.legs, self.arms, self.head]
        return CharacterStats(
            health=sum(p.health for p in parts),
            melee_power=sum(p.melee_power for p in parts),
            speed=sum(p.speed for p in parts),
            action_points=action_points,
            view_distance=sum(p.view_distance for p in parts),
            accuracy=sum(p.accuracy for p in parts),
        )

    def apply_random_part_damage(self, damage: int) -> Optional[Part]:
        """Наносит локальный урон случайной ещё не уничтоженной части меха
        (веса HIT_WEIGHTS). Возвращает задетую часть, либо None, если все
        части уже уничтожены (у меха бывает лишний общий запас HP)."""
        parts = {
            "torso": self.torso,
            "legs": self.legs,
            "arms": self.arms,
            "head": self.head,
        }
        alive = {name: part for name, part in parts.items() if not part.destroyed}
        if not alive:
            return None
        field_name = random.choices(
            list(alive.keys()), weights=[self.HIT_WEIGHTS[k] for k in alive], k=1
        )[0]
        part = alive[field_name]
        part.apply_damage(damage)
        return part

    def recompute_live_stats(self, stats: CharacterStats) -> None:
        """Обновляет зависящие от деталей статы (speed/accuracy/melee_power/
        view_distance) с учётом уничтоженных частей - см. ROADMAP.md, Этап 2 п.2.
        health/max_health/action_points не трогает - общий пул HP считается
        отдельно через Actor.apply_damage, торс не требует спецкейса."""
        all_parts = (self.torso, self.legs, self.arms, self.head)
        alive = [p for p in all_parts if not p.destroyed]
        stats.melee_power = sum(p.melee_power for p in alive)
        stats.speed = sum(p.speed for p in alive)
        stats.view_distance = sum(p.view_distance for p in alive)
        stats.accuracy = sum(p.accuracy for p in alive)
