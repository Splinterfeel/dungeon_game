import random

from pydantic import BaseModel

from src.mech.part import Part, PartSlot
from src.mech.catalog import (
    DEFAULT_ARMS,
    DEFAULT_HEAD,
    DEFAULT_LEGS,
    DEFAULT_TORSO,
    FIREWORKS_ARMS,
    FIREWORKS_HEAD,
    FIREWORKS_LEGS,
    FIREWORKS_TORSO,
    STEELMAN_ARMS,
    STEELMAN_HEAD,
    STEELMAN_LEGS,
    STEELMAN_TORSO,
    STRIKEFORCE_ARMS,
    STRIKEFORCE_HEAD,
    STRIKEFORCE_LEGS,
    STRIKEFORCE_TORSO,
)


MATCH_REWARD_CHANCES = {"winner": 0.80, "loser": 0.35}
AFFIX_TIER_WEIGHTS: tuple[tuple[int, float], ...] = (
    (3, 0.05),
    (2, 0.15),
    (1, 0.30),
    (0, 0.50),
)
AFFIX_STAT_POOLS: dict[PartSlot, tuple[str, ...]] = {
    PartSlot.TORSO: ("health",),
    PartSlot.LEGS: ("speed",),
    PartSlot.ARMS: ("accuracy", "melee_power"),
    PartSlot.HEAD: ("view_distance",),
}
AFFIX_VALUES_BY_STAT: dict[str, tuple[int, int, int]] = {
    "health": (1, 1, 2),
    "speed": (1, 2, 3),
    "accuracy": (4, 8, 12),
    "melee_power": (1, 2, 3),
    "view_distance": (1, 2, 3),
}
AFFIX_STAT_LABELS: dict[str, str] = {
    "health": "здоровью",
    "speed": "скорости",
    "accuracy": "точности",
    "melee_power": "силе удара",
    "view_distance": "обзору",
}

PART_TEMPLATES = (
    DEFAULT_TORSO,
    DEFAULT_LEGS,
    DEFAULT_ARMS,
    DEFAULT_HEAD,
    STEELMAN_TORSO,
    STEELMAN_LEGS,
    STEELMAN_ARMS,
    STEELMAN_HEAD,
    FIREWORKS_TORSO,
    FIREWORKS_LEGS,
    FIREWORKS_ARMS,
    FIREWORKS_HEAD,
    STRIKEFORCE_TORSO,
    STRIKEFORCE_LEGS,
    STRIKEFORCE_ARMS,
    STRIKEFORCE_HEAD,
)


class RewardResult(BaseModel):
    awarded_part: Part | None = None
    chance: float
    reason: str


def weighted_roll_int(weighted_values: tuple[tuple[int, float], ...]) -> int:
    roll = random.random()
    cumulative = 0.0
    for value, weight in weighted_values:
        cumulative += weight
        if roll < cumulative:
            return value
    return weighted_values[-1][0]


def apply_random_affix(part: Part, affix_tier: int | None = None) -> Part:
    if affix_tier is None:
        affix_tier = weighted_roll_int(AFFIX_TIER_WEIGHTS)
    if affix_tier == 0:
        return part

    stat_name = random.choice(AFFIX_STAT_POOLS[part.slot])
    affix_value = AFFIX_VALUES_BY_STAT[stat_name][affix_tier - 1]
    setattr(part, stat_name, getattr(part, stat_name) + affix_value)
    part.affix_tier = affix_tier
    part.affix_stat = stat_name
    part.affix_value = affix_value
    part.name = f"{part.name} +{affix_tier} к {AFFIX_STAT_LABELS[stat_name]}"
    return part
