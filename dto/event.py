from pydantic import BaseModel


class GameEvent(BaseModel):
    type: str = "game_event"
    message: str
