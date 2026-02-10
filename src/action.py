from pydantic import BaseModel

from enum import Enum, auto
from src.base import Point
from src.entities.base import Actor


class ActionType(Enum):
    END_TURN = auto()
    MOVE = auto()
    INSPECT = auto()
    ATTACK = auto()
    HEAVY_ATTACK = auto()
    OPEN_CHEST = auto()
    EXIT = auto()


class Action(BaseModel):
    actor: Actor
    type: ActionType
    cell: Point = None
    params: dict | None = None
