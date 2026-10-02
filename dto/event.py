from pydantic import BaseModel
from dto.state import PartState


class GameEvent(BaseModel):
    type: str = "game_event"
    message: str
    loot_part: PartState | None = None


class ActionResultEvent(BaseModel):
    type: str = "action_result"
    action_id: str | None
    performed: bool
    detail: str


class MatchResultEvent(BaseModel):
    type: str = "match_result"
    match_id: str
    winner: int | None
    xp_awarded: int
    level_before: int
    level_after: int
    loot_part: PartState | None


class LobbyClosedEvent(BaseModel):
    type: str = "lobby_closed"
    message: str
