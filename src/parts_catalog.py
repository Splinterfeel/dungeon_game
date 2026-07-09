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


def default_mech() -> Mech:
    # каждая деталь копируется со своим id — детали разных мехов не должны его делить
    return Mech(
        torso=DEFAULT_TORSO.model_copy(update={"id": uuid.uuid4()}),
        legs=DEFAULT_LEGS.model_copy(update={"id": uuid.uuid4()}),
        arms=DEFAULT_ARMS.model_copy(update={"id": uuid.uuid4()}),
        head=DEFAULT_HEAD.model_copy(update={"id": uuid.uuid4()}),
    )
