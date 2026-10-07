import uuid
from enum import Enum

from pydantic import BaseModel, Field

from src.entities.base import UUIDStr


class SkillTrigger(str, Enum):
    ATTACK = "attack"
    DEFENSE = "defense"


class Skill(BaseModel):
    id: UUIDStr = Field(default_factory=uuid.uuid4)
    skill_key: str
    name: str
    trigger: SkillTrigger
    proc_chance: float
    description: str


class Skills:
    ACCURATE_SHOT = Skill(
        skill_key="accurate_shot",
        name="Точный выстрел",
        trigger=SkillTrigger.ATTACK,
        proc_chance=0.15,
        description="Шанс на атаку: +15 к точности для текущего выстрела.",
    )
    HEAVY_STRIKE = Skill(
        skill_key="heavy_strike",
        name="Усиленный удар",
        trigger=SkillTrigger.ATTACK,
        proc_chance=0.15,
        description="Шанс на атаку: +30 к силе удара для текущей атаки ближнего боя.",
    )
    COMBAT_IMPULSE = Skill(
        skill_key="combat_impulse",
        name="Боевой импульс",
        trigger=SkillTrigger.ATTACK,
        proc_chance=0.12,
        description="Шанс, что текущая атака не потратит очки действия.",
    )
    DODGE = Skill(
        skill_key="dodge",
        name="Уклонение",
        trigger=SkillTrigger.DEFENSE,
        proc_chance=0.15,
        description="Шанс полностью избежать входящего удара или выстрела.",
    )


SKILLS_BY_KEY: dict[str, Skill] = {
    skill.skill_key: skill
    for skill in vars(Skills).values()
    if isinstance(skill, Skill)
}

SKILL_TREE: dict[int, dict[str | None, tuple[Skill, ...]]] = {
    2: {
        None: (Skills.ACCURATE_SHOT, Skills.HEAVY_STRIKE),
    },
    3: {
        Skills.ACCURATE_SHOT.skill_key: (Skills.COMBAT_IMPULSE,),
        Skills.HEAVY_STRIKE.skill_key: (Skills.DODGE,),
    },
}


def build_skills_by_keys(skill_keys: list[str]) -> list[Skill]:
    return [
        SKILLS_BY_KEY[skill_key].model_copy(update={"id": uuid.uuid4()})
        for skill_key in skill_keys
        if skill_key in SKILLS_BY_KEY
    ]


def get_skill_choice_options(level: int, owned_skill_keys: list[str]) -> list[Skill]:
    options = []
    for required_skill_key, skills in SKILL_TREE.get(level, {}).items():
        if required_skill_key is None or required_skill_key in owned_skill_keys:
            options.extend(
                skill.model_copy(update={"id": uuid.uuid4()}) for skill in skills
            )
    return options
