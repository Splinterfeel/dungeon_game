from pydantic import BaseModel

from enum import Enum, auto
from src.base import Point


class ActionType(Enum):
    MOVE = auto()
    INSPECT = auto()
    ATTACK = auto()
    HEAVY_ATTACK = auto()
    OPEN_CHEST = auto()
    EXIT = auto()


class Action(BaseModel):
    type: ActionType
    cell: Point
    ends_turn: bool
    params: dict | None = None
