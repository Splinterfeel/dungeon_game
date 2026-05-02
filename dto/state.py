from pydantic import BaseModel


class LobbyStatePayload(BaseModel):
    status: str
    players_num: int
    connected_players: list[str]


class LobbyState(BaseModel):
    type: str = "lobby_state"
    payload: LobbyStatePayload
