from uuid import UUID
from pydantic import BaseModel, Field


class PlayerDTO(BaseModel):
    id: UUID
    team: int


class DetailedBoolResponse(BaseModel):
    result: bool
    detail: str


class LobbyDTO(BaseModel):
    id: UUID
    name: str
    players_num: int = Field(gt=0)
    team_1_connected_players: int
    team_2_connected_players: int
    created_by_player_id: str
    game_started: bool


class CreateLobbyRequest(BaseModel):
    name: str | None = None
    players_num: int = Field(gt=0)
    created_by_player_id: UUID


class ConnectLobbyRequest(BaseModel):
    lobby_id: str
    player: PlayerDTO


class StartGameRequest(BaseModel):
    lobby_id: str


class StartGameResponse(DetailedBoolResponse):
    lobby_id: UUID


class PointState(BaseModel):
    x: int
    y: int
