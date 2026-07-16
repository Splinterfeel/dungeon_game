from pydantic import BaseModel
from dto.state import PartState


class GameEvent(BaseModel):
    type: str = "game_event"
    message: str
    loot_part: PartState | None = None
