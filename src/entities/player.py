from src.entities.base import Actor


class Player(Actor):
    team: int = 1

    def __str__(self):
        return "PLAYER " + super().__str__()
