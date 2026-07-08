from pydantic import BaseModel, model_validator

from src.entities.base import CharacterStats
from src.entities.part import Part, PartSlot


class Mech(BaseModel):
    torso: Part
    legs: Part
    arms: Part
    head: Part

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
