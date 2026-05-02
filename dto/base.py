from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class PlayerDTO(BaseModel):
    id: UUID
    team: int = 1


class DetailedBoolResponse(BaseModel):
    result: bool
    detail: str


class LobbyDTO(BaseModel):
    id: UUID = Field(default_factory=uuid4)


class CreateLobbyRequest(BaseModel):
    players_num: int = Field(gt=0)


class ConnectLobbyRequest(BaseModel):
    lobby_id: UUID
    player: PlayerDTO


class StartGameRequest(BaseModel):
    lobby_id: UUID


class StartGameResponse(DetailedBoolResponse):
    lobby_id: UUID


# class GameState(BaseModel):
