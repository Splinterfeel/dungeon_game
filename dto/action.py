from typing import Literal
import uuid
from pydantic import BaseModel

from dto.base import PointState
from dto.state import ActorState


class GameActionState(BaseModel):
    id: uuid.UUID
    actor: ActorState
    type: Literal[
        "END_TURN",
        "MOVE",
        "INSPECT",
        "ATTACK",
        "HEAVY_ATTACK",
        "OPEN_CHEST",
        "EXIT"
    ]
    cell: PointState
    params: dict | None = None
