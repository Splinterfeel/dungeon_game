from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class PlayerDTO(BaseModel):
    id: UUID


class LobbyDTO(BaseModel):
    id: UUID = Field(default_factory=uuid4)


class CreateLobbyRequest(BaseModel):
    players: list[PlayerDTO]
