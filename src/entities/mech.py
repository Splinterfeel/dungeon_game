import random
from typing import ClassVar, Optional

from pydantic import BaseModel, computed_field, model_validator

from src.entities.base import CharacterStats
from src.entities.part import Part, PartSlot

# поля Part, определяющие "тип" детали (без экземплярных id/прочности) - по ним
# сверяется, что левая и правая руки - одна и та же деталь (ROADMAP.md Этап 2 п.3)
_PART_IDENTITY_FIELDS = (
    "slot",
    "name",
    "rarity",
    "health",
    "speed",
    "accuracy",
    "melee_power",
    "view_distance",
    "max_health",
    "weight",
    "carry_capacity",
)


class Mech(BaseModel):
    # веса случайного выбора части при попадании (locational damage,
    # см. ROADMAP.md, Этап 2 п.2) - торс чаще конечностей, конкретные
    # числа не балансировались отдельно. Руки разделены на левую/правую
    # (Этап 2 п.3): суммарный шанс попасть по рукам остаётся 0.2, делится поровну.
    HIT_WEIGHTS: ClassVar[dict[str, float]] = {
        "torso": 0.4,
        "legs": 0.2,
        "head": 0.2,
        "arms_left": 0.1,
        "arms_right": 0.1,
    }

    torso: Part
    legs: Part
    # руки - одна деталь-выбор (нельзя надеть разные типы), но две физические руки
    # с раздельным здоровьем (ROADMAP.md Этап 2 п.3): arms_left/arms_right - копии
    # одного типа детали (проверяется в check_slots). Каждая рука - слот под оружие
    # (Weapon.hand), её уничтожение делает своё оружие недоступным (arm_for).
    arms_left: Part
    arms_right: Part
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
            "arms_left": PartSlot.ARMS,
            "arms_right": PartSlot.ARMS,
            "head": PartSlot.HEAD,
        }
        for field_name, expected_slot in expected_slots.items():
            part: Part = getattr(self, field_name)
            if part.slot != expected_slot:
                raise ValueError(
                    f"{field_name} ожидает деталь слота {expected_slot}, получена {part.slot}"
                )
        # "руки - одна деталь": левая и правая должны быть одного типа (id и
        # текущая прочность могут отличаться - это разные экземпляры в бою)
        if any(
            getattr(self.arms_left, f) != getattr(self.arms_right, f)
            for f in _PART_IDENTITY_FIELDS
        ):
            raise ValueError(
                "Левая и правая руки должны быть одной деталью (одинаковый тип)"
            )
        return self

    def arm_for(self, hand: str) -> Part:
        "Деталь руки по стороне оружия (Weapon.hand): 'left' -> arms_left, иначе arms_right"
        return self.arms_left if hand == "left" else self.arms_right

    def hand_side_of(self, part: Part) -> Optional[str]:
        "Сторона руки ('left'/'right') для конкретного экземпляра детали, иначе None"
        if part is self.arms_left:
            return "left"
        if part is self.arms_right:
            return "right"
        return None

    @computed_field  # type: ignore[misc]
    @property
    def parts_weight(self) -> int:
        "Суммарный вес деталей меха (без оружия - см. Player.check_weight_budget). Руки - одна деталь, вес считается один раз."
        return (
            self.torso.weight
            + self.legs.weight
            + self.head.weight
            + self.arms_left.weight
        )

    @computed_field  # type: ignore[misc]
    @property
    def weight_capacity(self) -> int:
        "Грузоподъёмность меха - см. ROADMAP.md Этап 2 п.9: берётся от ног (конвенция Armored Core)"
        return self.legs.carry_capacity

    def build_character_stats(self, action_points: int) -> CharacterStats:
        "Совокупные статы меха = сумма характеристик деталей + очки действия пилота. Руки идентичны - считаются один раз."
        parts = [self.torso, self.legs, self.head, self.arms_left]
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
            "head": self.head,
            "arms_left": self.arms_left,
            "arms_right": self.arms_right,
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
        отдельно через Actor.apply_damage, торс не требует спецкейса.

        Руки: идентичны, поэтому их статы (accuracy/melee_power) считаются один
        раз и остаются полными, пока жива хотя бы одна рука; обнуляются только
        когда уничтожены обе (решение пользователя, ROADMAP.md Этап 2 п.3)."""
        contributing = [
            p for p in (self.torso, self.legs, self.head) if not p.destroyed
        ]
        if not (self.arms_left.destroyed and self.arms_right.destroyed):
            contributing.append(self.arms_left)  # руки идентичны - считаем один раз
        stats.melee_power = sum(p.melee_power for p in contributing)
        stats.speed = sum(p.speed for p in contributing)
        stats.view_distance = sum(p.view_distance for p in contributing)
        stats.accuracy = sum(p.accuracy for p in contributing)
