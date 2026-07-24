from uuid import UUID
from pydantic import BaseModel, Field


class PlayerDTO(BaseModel):
    id: UUID
    team: int
    # Два стартовых меха пилота. None в конкретной позиции означает случайный
    # пресет. После создания гаража последующие значения игнорируются.
    mech_presets: list[str | None] = Field(
        default_factory=lambda: [None, None],
        min_length=2,
        max_length=2,
    )


class DetailedBoolResponse(BaseModel):
    result: bool
    detail: str


class LobbyDTO(BaseModel):
    id: UUID
    name: str
    players_num: int = Field(gt=0)
    vs_bot: bool = False
    team_1_connected_players: int
    team_2_connected_players: int
    created_by_player_id: str
    game_started: bool


class CreateLobbyRequest(BaseModel):
    name: str | None = None
    players_num: int = Field(gt=0)
    created_by_player_id: UUID
    vs_bot: bool = False


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
