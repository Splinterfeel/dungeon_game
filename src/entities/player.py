import names
from pydantic import Field, model_validator

from src.entities.base import Actor


class Player(Actor):
    team: int = 1

    @model_validator(mode="after")
    def set_team_name(self):
        if not self.name:
            self.name = names.get_full_name()
        self.name = f"[{self.team}]{self.name}"
        return self

    def __str__(self):
        return "PLAYER " + super().__str__()
