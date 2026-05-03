import uuid
from pydantic import BaseModel, Field, field_validator

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


    @field_validator('type', mode='before')
    @classmethod
    def decode_action_type(cls, value):
        # Если пришла строка (например, с фронта), ищем её в именах ActionType
        if isinstance(value, str):
            try:
                return ActionType[value]
            except KeyError:
                raise ValueError(f"Unknown action type: {value}")
        return value


class ActionResult(BaseModel):
    action: Action
    performed: bool = True
    action_cost: int = 0
    speed_spent: int = 0
