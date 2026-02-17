import uuid
from pydantic import BaseModel, Field

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
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    actor: Actor
    type: ActionType
    cell: Point
    params: dict | None = None


class ActionResult(BaseModel):
    action: Action
    performed: bool = True
    action_cost: int = 0
    speed_spent: int = 0
