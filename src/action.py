from dataclasses import dataclass
from enum import Enum, auto
from src.base import Point


class ActionType(Enum):
    MOVE = auto()
    INSPECT = auto()
    ATTACK_ENEMY = auto()
    OPEN_CHEST = auto()
    EXIT = auto()


@dataclass
class Action:
    type: ActionType
    cell: Point
    ends_turn: bool
