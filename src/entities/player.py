import names
from pydantic import Field, model_validator

from src.entities.base import Actor
from src.entities.mech import Mech


class Player(Actor):
    team: int = 1
    mech: Mech
    xp: int = 0
    level: int = 1

    @model_validator(mode="after")
    def set_team_name(self):
        if not self.name:
            self.name = names.get_full_name()
        self.name = f"[{self.team}]{self.name}"
        return self

    @model_validator(mode="after")
    def check_weight_budget(self):
        # весовой бюджет (ROADMAP.md, Этап 2 п.9): вес деталей меха + вес
        # оружия в инвентаре не должен превышать грузоподъёмность ног.
        # Правило при превышении - запрет (вариант по умолчанию из роадмапа),
        # не штраф к статам.
        total_weight = self.mech.parts_weight + sum(
            w.weight for w in self.inventory.weapons
        )
        if total_weight > self.mech.weight_capacity:
            raise ValueError(
                f"{self.name or 'Пилот'}: сборка весит {total_weight}, "
                f"превышен грузоподъём меха ({self.mech.weight_capacity})"
            )
        return self

    def __str__(self):
        return "PLAYER " + super().__str__()
