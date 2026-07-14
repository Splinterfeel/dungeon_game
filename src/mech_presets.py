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
    # лор пресета для дебаг-инспектора (см. ROADMAP.md) - художественное
    # описание архетипа + немного псевдо-истории (кем и когда создан, для
    # каких целей); на игровую логику не влияет
    description: str
    mech: Mech
    weapons: list[Weapon]


STEELMAN_PRESET = MechPreset(
    name="SteelMan",
    description=(
        "«СтилМан» — тяжёлый штурмовой мех корпорации «Дюрандаль Индастриз», "
        "разработанный в 2081 году для взлома укреплённых позиций там, где "
        "лёгкая техника просто вязнет под огнём. Ставка сделана на прочность "
        "корпуса и разрушительную силу удара в ближнем бою: пилоты ценят его "
        "за способность пережить шквал огня и всё-таки дойти до цели, но "
        "платят за это медлительностью и слабым прицельным оборудованием."
    ),
    mech=Mech(
        torso=STEELMAN_TORSO,
        legs=STEELMAN_LEGS,
        arms_left=STEELMAN_ARMS,
        arms_right=STEELMAN_ARMS,
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
            weight=8,
            hand="right",
        ),
        Weapon(
            type="ranged",
            name="Мех-пистолет",
            damage=3,
            cost_ap=6,
            range=3,
            accuracy=75,
            weight=2,
            hand="left",
        ),
    ],
)

FIREWORKS_MK1_PRESET = MechPreset(
    name="Fireworks Mk. 1",
    description=(
        "«Fireworks Mk. 1» — лёгкий разведывательно-штурмовой мех независимой "
        "мастерской «Аэрис Дефенс», выпущенный в 2083 году как ответ на спрос "
        "наёмных пилотских отрядов на манёвренность и точный огонь на "
        "дистанции. Облегчённая рама и продвинутый сенсорный комплекс дают "
        "преимущество в скорости и точности стрельбы, но корпус едва прикрыт "
        "бронёй — среди пилотов ходит мрачная шутка, что мех назвали в честь "
        "того, как эффектно он вспыхивает при первом же серьёзном попадании."
    ),
    mech=Mech(
        torso=FIREWORKS_TORSO,
        legs=FIREWORKS_LEGS,
        arms_left=FIREWORKS_ARMS,
        arms_right=FIREWORKS_ARMS,
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
            weight=5,
            hand="right",
        ),
        Weapon(
            type="melee",
            name="Аварийный клинок",
            damage=2,
            cost_ap=5,
            range=1,
            accuracy=90,
            weight=1,
            hand="left",
        ),
    ],
)

# Архетип "медленный/малое HP/дамажный": основное оружие - рейлган в правой
# руке, вся ставка на один разовый урон. Левая рука несёт "Коготь" - аварийное
# оружие с совсем минимальными статами (2026-07-14): не полноценный план "Б",
# а последний шанс не остаться совсем безоружным, если правую руку выбьют.
# Числа не сбалансированы намеренно, см. комментарий у STRIKEFORCE_* в
# parts_catalog.py - баланс после того, как появится разброс урона.
STRIKEFORCE_PRESET = MechPreset(
    name="StrikeForce",
    description=(
        "«StrikeForce» — экспериментальный мех-«снайпер» лаборатории вооружений "
        "«Кастор Дефенс Системс», построенный в 2084 году вокруг единственного "
        "орудия — рейлгана, изначально проектировавшегося для орбитальных "
        "оборонных платформ. Всё, что можно было снять с ходовой части и брони, "
        "ушло на генератор рейлгана. Военные аналитики прозвали его «мех одного "
        "выстрела»: StrikeForce либо решает бой одним попаданием, либо не "
        "успевает нанести его вовсе."
    ),
    mech=Mech(
        torso=STRIKEFORCE_TORSO,
        legs=STRIKEFORCE_LEGS,
        arms_left=STRIKEFORCE_ARMS,
        arms_right=STRIKEFORCE_ARMS,
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
            weight=14,
            hand="right",
        ),
        # намеренно слабое аварийное оружие: хуже "Аварийного клинка" Fireworks
        # по урону/точности/AP, при этом легче него по весу. Задел под будущий
        # гараж (Этап 2.5): игрок сможет НЕ брать "Коготь" ради экономии веса,
        # сознательно рискуя остаться безоружным при потере правой руки - сейчас
        # выбора нет, пресет фиксирован, но сама механика уже позволяет это.
        Weapon(
            type="melee",
            name="Коготь",
            damage=2,
            cost_ap=4,
            range=1,
            accuracy=65,
            weight=2,
            hand="left",
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
                # руки - две отдельные детали одного типа, каждой свой id и
                # раздельная прочность (ROADMAP.md Этап 2 п.3)
                arms_left=mech.arms_left.model_copy(update={"id": uuid.uuid4()}),
                arms_right=mech.arms_right.model_copy(update={"id": uuid.uuid4()}),
                head=mech.head.model_copy(update={"id": uuid.uuid4()}),
                preset_name=preset.name,
            ),
            # model_copy сохраняет hand у оружия, обновляя только id
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
