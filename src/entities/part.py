import uuid
from enum import Enum

from pydantic import BaseModel, Field

from src.entities.base import UUIDStr


class PartSlot(str, Enum):
    TORSO = "torso"
    LEGS = "legs"
    ARMS = "arms"
    HEAD = "head"


class Part(BaseModel):
    id: UUIDStr = Field(default_factory=uuid.uuid4)
    slot: PartSlot
    name: str
    health: int = 0
    speed: int = 0
    accuracy: int = 0
    melee_power: int = 0
    view_distance: int = 0
