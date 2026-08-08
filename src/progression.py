from pydantic import BaseModel, Field

from src.skills_catalog import fresh_skills_by_keys, get_skill_choice_options


MATCH_XP_REWARDS = {"winner": 70, "loser": 30}
LEVEL_XP_THRESHOLDS = {2: 100, 3: 250}


class PendingSkillChoice(BaseModel):
    level: int


class ProgressionResult(BaseModel):
    xp_awarded: int
    level_before: int
    level_after: int
    pending_choices_added: list[int] = Field(default_factory=list)


def build_skills(owned_skill_keys: list[str]):
    return fresh_skills_by_keys(owned_skill_keys)


def get_pending_skill_options(
    pending_skill_choices: list[PendingSkillChoice],
    owned_skill_keys: list[str],
):
    pending_options = []
    for pending_choice in pending_skill_choices:
        options = get_skill_choice_options(pending_choice.level, owned_skill_keys)
        pending_options.append((pending_choice.level, options))
    return pending_options


def award_xp(
    current_xp: int,
    current_level: int,
    pending_skill_choices: list[PendingSkillChoice],
    xp_amount: int,
) -> tuple[int, int, ProgressionResult]:
    level_before = current_level
    updated_xp = current_xp + xp_amount
    updated_level = current_level
    pending_levels_added: list[int] = []
    for level, threshold in sorted(LEVEL_XP_THRESHOLDS.items()):
        if updated_level >= level:
            continue
        if updated_xp < threshold:
            break
        updated_level = level
        pending_skill_choices.append(PendingSkillChoice(level=level))
        pending_levels_added.append(level)
    return (
        updated_xp,
        updated_level,
        ProgressionResult(
            xp_awarded=xp_amount,
            level_before=level_before,
            level_after=updated_level,
            pending_choices_added=pending_levels_added,
        ),
    )


def choose_skill(
    owned_skill_keys: list[str],
    pending_skill_choices: list[PendingSkillChoice],
    skill_key: str,
) -> None:
    if not pending_skill_choices:
        raise ValueError("У пилота нет доступного выбора навыка")
    pending_choice = pending_skill_choices[0]
    allowed_keys = {
        skill.skill_key
        for skill in get_skill_choice_options(
            pending_choice.level, owned_skill_keys
        )
    }
    if not allowed_keys:
        raise ValueError("Для текущего выбора навыка пока не выполнены условия ветки")
    if skill_key not in allowed_keys:
        raise ValueError("Выбран недоступный навык для текущего уровня")
    if skill_key in owned_skill_keys:
        raise ValueError("Этот навык уже выбран у пилота")
    owned_skill_keys.append(skill_key)
    pending_skill_choices.pop(0)
