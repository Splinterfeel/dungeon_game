from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class PlayerDTO(BaseModel):
    id: UUID
    team: int = 1


class LobbyDTO(BaseModel):
    id: UUID = Field(default_factory=uuid4)


class CreateLobbyRequest(BaseModel):
    players_num: int


class ConnectLobbyRequest(BaseModel):
    lobby_id: UUID
    player: PlayerDTO


class StartGameRequest(BaseModel):
    lobby_id: UUID


class StartGameResponse(BaseModel):
    lobby_id: UUID
    result: bool
    detail: str
