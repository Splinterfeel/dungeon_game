import uuid
from typing import Literal

from pydantic import BaseModel, Field

from src.entities.base import UUIDStr


SkillTrigger = Literal["attack", "defense"]


class Skill(BaseModel):
    id: UUIDStr = Field(default_factory=uuid.uuid4)
    skill_key: str
    name: str
    trigger: SkillTrigger
    proc_chance: float
    description: str


ACCURATE_SHOT = Skill(
    skill_key="accurate_shot",
    name="Точный выстрел",
    trigger="attack",
    proc_chance=0.15,
    description="Шанс на атаку: +15 к точности для текущего выстрела.",
)

HEAVY_STRIKE = Skill(
    skill_key="heavy_strike",
    name="Усиленный удар",
    trigger="attack",
    proc_chance=0.15,
    description="Шанс на атаку: +3 к силе удара для текущей атаки ближнего боя.",
)

COMBAT_IMPULSE = Skill(
    skill_key="combat_impulse",
    name="Боевой импульс",
    trigger="attack",
    proc_chance=0.12,
    description="Шанс, что текущая атака не потратит очки действия.",
)

DODGE = Skill(
    skill_key="dodge",
    name="Уклонение",
    trigger="defense",
    proc_chance=0.15,
    description="Шанс полностью избежать входящего удара или выстрела.",
)

DEFAULT_PLAYER_SKILLS = [ACCURATE_SHOT, HEAVY_STRIKE, COMBAT_IMPULSE, DODGE]

SKILLS_BY_KEY: dict[str, Skill] = {
    skill.skill_key: skill
    for skill in DEFAULT_PLAYER_SKILLS
}

LEVEL_SKILL_CHOICES: dict[int, tuple[str, ...]] = {
    2: ("accurate_shot", "heavy_strike"),
}

LEVEL_BRANCH_SKILL_CHOICES: dict[int, dict[str, tuple[str, ...]]] = {
    3: {
        "accurate_shot": ("combat_impulse",),
        "heavy_strike": ("dodge",),
    }
}


def fresh_default_player_skills() -> list[Skill]:
    return [skill.model_copy(update={"id": uuid.uuid4()}) for skill in DEFAULT_PLAYER_SKILLS]


def fresh_skills_by_keys(skill_keys: list[str]) -> list[Skill]:
    return [
        SKILLS_BY_KEY[skill_key].model_copy(update={"id": uuid.uuid4()})
        for skill_key in skill_keys
        if skill_key in SKILLS_BY_KEY
    ]


def get_skill_choice_options(level: int, owned_skill_keys: list[str]) -> list[Skill]:
    direct_choices = LEVEL_SKILL_CHOICES.get(level)
    if direct_choices is not None:
        return [
            SKILLS_BY_KEY[skill_key].model_copy(update={"id": uuid.uuid4()})
            for skill_key in direct_choices
        ]

    branch_choices = LEVEL_BRANCH_SKILL_CHOICES.get(level)
    if branch_choices is None:
        return []

    for prerequisite_key, option_keys in branch_choices.items():
        if prerequisite_key in owned_skill_keys:
            return [
                SKILLS_BY_KEY[skill_key].model_copy(update={"id": uuid.uuid4()})
                for skill_key in option_keys
            ]
    return []
