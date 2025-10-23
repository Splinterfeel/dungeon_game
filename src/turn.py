import enum

from src.base import Point
from src.entities.base import Actor


class GamePhase(enum.Enum):
    PLAYER_PHASE = enum.auto()
    ENEMY_PHASE = enum.auto()

    def __str__(self):
        return self.name


class Turn:
    def __init__(self):
        self.number = 0
        self.phase = GamePhase.PLAYER_PHASE
        self.current_actor: Actor = None
        self.available_moves: list[Point] = None

    def next(self):
        self.number += 1
        self.phase = GamePhase.PLAYER_PHASE
