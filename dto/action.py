import uuid
from pydantic import BaseModel

from dto.base import PointState
from src.action import ActionType


class GameActionState(BaseModel):
    id: uuid.UUID
    actor_id: str
    type: ActionType
    cell: PointState
    params: dict | None = None
