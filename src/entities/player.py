from src.entities.base import Actor


class Player(Actor):
    def __str__(self):
        return "PLAYER " + super().__str__()
