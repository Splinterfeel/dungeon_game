import random

from pydantic import Field

from src.entities.base import Entity

# Заглушка до появления полноценного каталога деталей меха (см. ROADMAP.md,
# этап 1, п.3) — тогда loot станет ссылкой на конкретную деталь/оружие с редкостью.
PLACEHOLDER_LOOT = [
    "Усиленный привод ног",
    "Облегчённая броневая плита",
    "Экспериментальный лазер",
    "Модуль системы наведения",
]


class Chest(Entity):
    loot: str = Field(default_factory=lambda: random.choice(PLACEHOLDER_LOOT))

    def __str__(self):
        return f"Chest [{self.position.x}, {self.position.y}], loot: {self.loot}"
