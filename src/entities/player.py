import names
from pydantic import Field, model_validator

from src.entities.base import Actor, UUIDStr
from src.entities.mech import Mech
from src.skills_catalog import Skill, fresh_default_player_skills


class Player(Actor):
    team: int = 1
    # id — конкретный боевой мех; owner_player_id — подключённый пилот,
    # которому разрешено отправлять действия за этого актора.
    owner_player_id: UUIDStr | None = None
    loadout_id: UUIDStr | None = None
    mech: Mech
    xp: int = 0
    level: int = 1
    skills: list[Skill] = Field(default_factory=fresh_default_player_skills)

    @model_validator(mode="after")
    def set_default_owner(self):
        if self.owner_player_id is None:
            self.owner_player_id = self.id
        return self

    @model_validator(mode="after")
    def set_team_name(self):
        if not self.name:
            self.name = names.get_full_name()
        if not self.name.startswith(f"[{self.team}]"):
            self.name = f"[{self.team}]{self.name}"
        return self

    @model_validator(mode="after")
    def check_weapon_loadout(self):
        # привязка оружия к рукам (ROADMAP.md, Этап 2 п.3-4): у игрока каждое
        # оружие взято в конкретную руку (left/right), не более одного на руку,
        # и минимум одно оружие обязательно (иначе меху нечем атаковать).
        weapons = self.inventory.weapons
        if not weapons:
            raise ValueError(
                f"{self.name or 'Пилот'}: у меха должно быть хотя бы одно оружие"
            )
        if len(weapons) > 2:
            raise ValueError(
                f"{self.name or 'Пилот'}: у меха две руки, оружия не может быть больше двух"
            )
        used_hands = []
        for w in weapons:
            if w.hand not in ("left", "right"):
                raise ValueError(
                    f"{self.name or 'Пилот'}: оружие «{w.name}» должно быть взято в руку (left/right)"
                )
            if w.hand in used_hands:
                raise ValueError(
                    f"{self.name or 'Пилот'}: в руку «{w.hand}» взято более одного оружия"
                )
            used_hands.append(w.hand)
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
