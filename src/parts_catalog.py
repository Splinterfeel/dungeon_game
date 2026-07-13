import uuid

from src.constants import Accuracy
from src.entities.mech import Mech
from src.entities.part import Part, PartSlot

# Стартовые детали повторяют числа, ранее захардкоженные в lobby.py,
# чтобы сама реструктуризация на Pilot/Mech/Part не меняла баланс.
DEFAULT_TORSO = Part(slot=PartSlot.TORSO, name="Лёгкий корпус", health=15)
DEFAULT_LEGS = Part(slot=PartSlot.LEGS, name="Стандартные ноги", speed=5)
DEFAULT_ARMS = Part(
    slot=PartSlot.ARMS,
    name="Стандартные руки",
    accuracy=Accuracy.DEFAULT_PLAYER_STATS_ACCURACY,
    melee_power=2,
)
DEFAULT_HEAD = Part(slot=PartSlot.HEAD, name="Стандартная электроника", view_distance=5)

# Детали пресета "SteelMan" — упор в ближний бой: больше здоровья и силы удара,
# ценой скорости, точности и дальности обзора.
STEELMAN_TORSO = Part(slot=PartSlot.TORSO, name="Тяжёлый корпус «Голем»", health=24)
STEELMAN_LEGS = Part(slot=PartSlot.LEGS, name="Усиленные сервоприводы", speed=6)
STEELMAN_ARMS = Part(
    slot=PartSlot.ARMS,
    name="Ударный привод «Молот»",
    accuracy=85,
    melee_power=6,
)
STEELMAN_HEAD = Part(slot=PartSlot.HEAD, name="Штурмовая электроника", view_distance=4)

# Детали пресета "Fireworks Mk. 1" — упор в стрельбу: точность и обзор,
# ценой здоровья и силы удара в ближнем бою.
FIREWORKS_TORSO = Part(slot=PartSlot.TORSO, name="Лёгкий корпус «Стриж»", health=11)
FIREWORKS_LEGS = Part(slot=PartSlot.LEGS, name="Манёвренные ноги «Вихрь»", speed=5)
FIREWORKS_ARMS = Part(
    slot=PartSlot.ARMS,
    name="Прицельный привод «Соколиный глаз»",
    accuracy=92,
    melee_power=0,
)
FIREWORKS_HEAD = Part(
    slot=PartSlot.HEAD, name="Дальномерная электроника «Горизонт»", view_distance=7
)


def default_mech() -> Mech:
    # каждая деталь копируется со своим id — детали разных мехов не должны его делить
    return Mech(
        torso=DEFAULT_TORSO.model_copy(update={"id": uuid.uuid4()}),
        legs=DEFAULT_LEGS.model_copy(update={"id": uuid.uuid4()}),
        arms=DEFAULT_ARMS.model_copy(update={"id": uuid.uuid4()}),
        head=DEFAULT_HEAD.model_copy(update={"id": uuid.uuid4()}),
    )
