from typing import Optional, Union
import uuid
from pydantic import BaseModel, Field

from enum import Enum
from src.base import Point
from src.entities.base import Actor


class ActionType(str, Enum):
    END_TURN = "END_TURN"
    MOVE = "MOVE"
    INSPECT = "INSPECT"
    ATTACK = "ATTACK"
    HEAVY_ATTACK = "HEAVY_ATTACK"
    OVERWATCH = "OVERWATCH"


class AttackActionParams(BaseModel):
    weapon_id: uuid.UUID


class OverwatchActionParams(BaseModel):
    weapon_id: uuid.UUID


class Action(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    actor_id: str
    type: ActionType
    cell: Point
    params: Optional[Union[AttackActionParams, OverwatchActionParams]] = None


class ActionResult(BaseModel):
    action: Action
    performed: bool = True
    action_cost: int = 0
    speed_spent: int = 0
    detail: str = "ActionResult: no detail"


class ActorMovement(BaseModel):
    """Видимые одной команде участки фактически пройденного маршрута."""

    action_id: uuid.UUID
    actor: Actor
    paths: list[list[Point]] = Field(default_factory=list)
    sightings: list[Actor] = Field(default_factory=list)
