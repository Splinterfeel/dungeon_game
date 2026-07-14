import uuid

from src.constants import Accuracy
from src.entities.mech import Mech
from src.entities.part import Part, PartRarity, PartSlot

# Стартовые детали повторяют числа, ранее захардкоженные в lobby.py,
# чтобы сама реструктуризация на Pilot/Mech/Part не меняла баланс.
# Rarity: common - нейтральный/тестовый набор, доступный всем по умолчанию.
# weight/carry_capacity (ROADMAP.md Этап 2 п.9) - первая прикидка, не
# сбалансировано отдельно; carry_capacity задан с запасом над суммой веса
# деталей+оружия существующих пресетов (см. STEELMAN/FIREWORKS/STRIKEFORCE
# ниже), не финальные числа.
DEFAULT_TORSO = Part(
    slot=PartSlot.TORSO,
    name="Лёгкий корпус",
    rarity=PartRarity.COMMON,
    health=15,
    weight=6,
)
DEFAULT_LEGS = Part(
    slot=PartSlot.LEGS,
    name="Стандартные ноги",
    rarity=PartRarity.COMMON,
    speed=5,
    weight=5,
    carry_capacity=25,
)
DEFAULT_ARMS = Part(
    slot=PartSlot.ARMS,
    name="Стандартные руки",
    rarity=PartRarity.COMMON,
    accuracy=Accuracy.DEFAULT_PLAYER_STATS_ACCURACY,
    melee_power=2,
    weight=4,
)
DEFAULT_HEAD = Part(
    slot=PartSlot.HEAD,
    name="Стандартная электроника",
    rarity=PartRarity.COMMON,
    view_distance=5,
    weight=3,
)

# Детали пресета "SteelMan" — упор в ближний бой: больше здоровья и силы удара,
# ценой скорости, точности и дальности обзора. Rarity: rare - именной набор
# для пресета, доступен не как стартовый common.
# Аудит компромиссов (2026-07-13, см. ROADMAP.md Этап 2 п.1): STEELMAN_LEGS
# в ходе прошлых сессий балансировки win rate дошёл до speed=6 - быстрее,
# чем "манёвренный" FIREWORKS_LEGS (тогда speed=5), что напрямую противоречит
# заявленному архетипу "тяжёлый = медленный". Возвращено к исходной
# направленности (SteelMan медленнее Fireworks: 4 против 6), просадка
# win rate от возросшей уязвимости на подходе скомпенсирована снижением
# точности рук FIREWORKS_ARMS (92 → 85), а не собственными статами SteelMan
# — см. FIREWORKS_ARMS ниже и balance_sim.py.
STEELMAN_TORSO = Part(
    slot=PartSlot.TORSO,
    name="Тяжёлый корпус «Голем»",
    rarity=PartRarity.RARE,
    health=20,
    weight=10,
)
STEELMAN_LEGS = Part(
    slot=PartSlot.LEGS,
    name="Усиленные сервоприводы",
    rarity=PartRarity.RARE,
    speed=4,
    weight=8,
    carry_capacity=42,
)
STEELMAN_ARMS = Part(
    slot=PartSlot.ARMS,
    name="Ударный привод «Молот»",
    rarity=PartRarity.RARE,
    accuracy=85,
    melee_power=6,
    weight=6,
)
STEELMAN_HEAD = Part(
    slot=PartSlot.HEAD,
    name="Штурмовая электроника",
    rarity=PartRarity.RARE,
    view_distance=4,
    weight=4,
)

# Детали пресета "Fireworks Mk. 1" — упор в стрельбу: точность и обзор,
# ценой здоровья и силы удара в ближнем бою. Rarity: rare - именной набор
# для пресета, доступен не как стартовый common.
FIREWORKS_TORSO = Part(
    slot=PartSlot.TORSO,
    name="Лёгкий корпус «Стриж»",
    rarity=PartRarity.RARE,
    health=11,
    weight=4,
)
FIREWORKS_LEGS = Part(
    slot=PartSlot.LEGS,
    name="Манёвренные ноги «Вихрь»",
    rarity=PartRarity.RARE,
    speed=6,
    weight=3,
    carry_capacity=24,
)
FIREWORKS_ARMS = Part(
    slot=PartSlot.ARMS,
    name="Прицельный привод «Соколиный глаз»",
    rarity=PartRarity.RARE,
    accuracy=85,
    melee_power=0,
    weight=3,
)
FIREWORKS_HEAD = Part(
    slot=PartSlot.HEAD,
    name="Дальномерная электроника «Горизонт»",
    rarity=PartRarity.RARE,
    view_distance=7,
    weight=3,
)

# Детали пресета "StrikeForce" — архетип "медленный/малое HP/дамажный":
# вся ставка на разовый урон рейлгана, ценой самой низкой живучести и
# самой низкой скорости в игре (см. ROADMAP.md Этап 2 п.1, расширение
# архетипов сверх "тяжёлый/медленный" и "лёгкий/быстрый"). Числа не
# сбалансированы намеренно — баланс делаем после того, как появится
# разброс урона оружия.
STRIKEFORCE_TORSO = Part(
    slot=PartSlot.TORSO,
    name="Облегчённый каркас «Копьё»",
    rarity=PartRarity.RARE,
    health=9,
    weight=3,
)
STRIKEFORCE_LEGS = Part(
    slot=PartSlot.LEGS,
    name="Опорная платформа «Такт»",
    rarity=PartRarity.RARE,
    speed=3,
    weight=9,
    carry_capacity=40,
)
STRIKEFORCE_ARMS = Part(
    slot=PartSlot.ARMS,
    name="Привод наведения рейлгана",
    rarity=PartRarity.RARE,
    accuracy=78,
    melee_power=0,
    weight=4,
)
STRIKEFORCE_HEAD = Part(
    slot=PartSlot.HEAD,
    name="Баллистический вычислитель",
    rarity=PartRarity.RARE,
    view_distance=6,
    weight=4,
)


def default_mech() -> Mech:
    # каждая деталь копируется со своим id — детали разных мехов не должны его делить
    return Mech(
        torso=DEFAULT_TORSO.model_copy(update={"id": uuid.uuid4()}),
        legs=DEFAULT_LEGS.model_copy(update={"id": uuid.uuid4()}),
        arms=DEFAULT_ARMS.model_copy(update={"id": uuid.uuid4()}),
        head=DEFAULT_HEAD.model_copy(update={"id": uuid.uuid4()}),
    )
