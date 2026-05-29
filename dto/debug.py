"""DTOs for debug operations (dump/restore game state)"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DebugDumpRequest(BaseModel):
    """Request for dumping game state"""

    lobby_id: str = Field(..., description="ID of the lobby to dump game state from")


class DebugDumpResponse(BaseModel):
    """Response containing dumped game state"""

    lobby_id: str = Field(..., description="ID of the lobby")
    lobby_name: str = Field(..., description="Name of the lobby")
    game_state: dict = Field(..., description="Serialized game state")
    timestamp: str = Field(..., description="ISO timestamp when dump was created")
    players_info: list[dict] = Field(..., description="List of connected players info")


class DebugRestoreRequest(BaseModel):
    """Request for restoring game state"""

    lobby_id: str = Field(..., description="ID of the lobby to restore game state to")
    game_state: dict = Field(..., description="Serialized game state to restore")
    lobby_name: Optional[str] = Field(
        None, description="Optional: new lobby name for restored game"
    )


class DebugRestoreResponse(BaseModel):
    """Response for restore operation"""

    success: bool = Field(..., description="Whether restore was successful")
    message: str = Field(
        ..., description="Detailed message about the restore operation"
    )
    lobby_id: str = Field(..., description="ID of the lobby where game was restored")
    timestamp: str = Field(..., description="ISO timestamp when restore was performed")
