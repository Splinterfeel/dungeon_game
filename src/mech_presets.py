import random
import uuid

from pydantic import BaseModel

from src.entities.base import Weapon
from src.entities.mech import Mech
from src.parts_catalog import (
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


class MechPreset(BaseModel):
    name: str
    mech: Mech
    weapons: list[Weapon]


STEELMAN_PRESET = MechPreset(
    name="SteelMan",
    mech=Mech(
        torso=STEELMAN_TORSO,
        legs=STEELMAN_LEGS,
        arms=STEELMAN_ARMS,
        head=STEELMAN_HEAD,
    ),
    weapons=[
        Weapon(
            type="melee",
            name="Кувалда «SteelMan»",
            damage=6,
            cost_ap=6,
            range=1,
            accuracy=95,
        ),
        Weapon(
            type="ranged",
            name="Мех-пистолет",
            damage=3,
            cost_ap=6,
            range=3,
            accuracy=75,
        ),
    ],
)

FIREWORKS_MK1_PRESET = MechPreset(
    name="Fireworks Mk. 1",
    mech=Mech(
        torso=FIREWORKS_TORSO,
        legs=FIREWORKS_LEGS,
        arms=FIREWORKS_ARMS,
        head=FIREWORKS_HEAD,
    ),
    weapons=[
        Weapon(
            type="ranged",
            name="Штурмовая винтовка «Fireworks»",
            damage=5,
            cost_ap=8,
            range=5,
            accuracy=90,
        ),
        Weapon(
            type="melee",
            name="Аварийный клинок",
            damage=2,
            cost_ap=5,
            range=1,
            accuracy=90,
        ),
    ],
)

# Архетип "медленный/малое HP/дамажный": единственное оружие - рейлган,
# без запасного (в отличие от SteelMan/Fireworks с парой оружий) - весь
# лоадаут поставлен на один разовый урон, без плана "Б" на ближний бой.
# Числа не сбалансированы намеренно, см. комментарий у STRIKEFORCE_* в
# parts_catalog.py - баланс после того, как появится разброс урона.
STRIKEFORCE_PRESET = MechPreset(
    name="StrikeForce",
    mech=Mech(
        torso=STRIKEFORCE_TORSO,
        legs=STRIKEFORCE_LEGS,
        arms=STRIKEFORCE_ARMS,
        head=STRIKEFORCE_HEAD,
    ),
    weapons=[
        Weapon(
            type="ranged",
            name="Рейлган «StrikeForce»",
            damage=10,
            cost_ap=8,
            range=6,
            accuracy=80,
        ),
    ],
)

MECH_PRESETS = [STEELMAN_PRESET, FIREWORKS_MK1_PRESET, STRIKEFORCE_PRESET]


def _fresh_copy(preset: MechPreset) -> MechPreset:
    """Копия пресета со свежими id у всех деталей/оружия (не делят id с оригиналом каталога)."""
    mech = preset.mech
    return preset.model_copy(
        update={
            "mech": Mech(
                torso=mech.torso.model_copy(update={"id": uuid.uuid4()}),
                legs=mech.legs.model_copy(update={"id": uuid.uuid4()}),
                arms=mech.arms.model_copy(update={"id": uuid.uuid4()}),
                head=mech.head.model_copy(update={"id": uuid.uuid4()}),
            ),
            "weapons": [
                w.model_copy(update={"id": uuid.uuid4()}) for w in preset.weapons
            ],
        }
    )


def get_random_mech_preset() -> MechPreset:
    return _fresh_copy(random.choice(MECH_PRESETS))


def get_mech_preset_by_name(name: str) -> MechPreset | None:
    for preset in MECH_PRESETS:
        if preset.name == name:
            return _fresh_copy(preset)
    return None
