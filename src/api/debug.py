from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from dto.base import StartGameResponse
from dto.debug import (
    DebugDumpRequest,
    DebugDumpResponse,
    DebugRestoreRequest,
    DebugRestoreResponse,
)
from dto.garage import PilotSummaryState, RematchRequest
from src.api.deps import get_garage_manager, get_lobby_manager
from src.debug.game_state_utils import (
    create_debug_dump_response,
    create_restore_response,
    restore_game_state as restore_game_state_util,
)
from src.lobby.manager import LobbyManager
from src.garage_manager import GarageManager

router = APIRouter(prefix="/debug")


@router.get("/pilots", description="Краткий список сохранённых пилотов (только debug)")
async def list_pilots(
    garage_manager: GarageManager = Depends(get_garage_manager),
) -> list[PilotSummaryState]:
    return await garage_manager.list_pilots()


@router.post("/rematch", description="Начать рематч тем же составом (debug only)")
async def start_rematch(
    request: RematchRequest,
    lobby_manager: LobbyManager = Depends(get_lobby_manager),
) -> StartGameResponse:
    lobby = lobby_manager.get_lobby(request.lobby_id)
    if not lobby:
        raise HTTPException(status_code=404, detail="Lobby not found")
    result, detail = await lobby.start_rematch(str(request.host_player_id))
    if result:
        await lobby.publish_started_game()
    return StartGameResponse(lobby_id=request.lobby_id, result=result, detail=detail)


@router.post(
    "/dump_game_state", description="Dump current game state to JSON (debug only)"
)
async def dump_game_state(
    request: DebugDumpRequest,
    lobby_manager: LobbyManager = Depends(get_lobby_manager),
) -> DebugDumpResponse:
    """Dump game state for debugging purposes"""
    lobby = lobby_manager.get_lobby(request.lobby_id)
    if not lobby:
        raise HTTPException(status_code=404, detail="Lobby not found")

    if not lobby.game:
        raise HTTPException(
            status_code=400, detail="No game in progress for this lobby"
        )

    try:
        game_state = lobby.game.to_dict()
        return create_debug_dump_response(lobby, game_state)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to dump game state: {str(e)}"
        )


@router.post(
    "/restore_game_state", description="Restore game state from JSON (debug only)"
)
async def restore_game_state(
    request: DebugRestoreRequest,
    lobby_manager: LobbyManager = Depends(get_lobby_manager),
    garage_manager: GarageManager = Depends(get_garage_manager),
) -> DebugRestoreResponse:
    """Restore game state for debugging purposes - creates a fresh lobby with provided ID"""
    try:
        game_data = request.game_state
        lobby_id = UUID(request.lobby_id)
        lobby_name = request.lobby_name or f"Restored Lobby {request.lobby_id[:8]}"

        # Restore game state using utility function
        lobby = await restore_game_state_util(
            game_data, lobby_id, lobby_name, garage_manager
        )

        # Add the restored lobby to the lobby manager
        lobby_manager.lobbies[str(lobby_id)] = lobby

        return create_restore_response(lobby_id, lobby_name)

    except Exception as e:
        import traceback

        error_details = f"Failed to restore game state: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        raise HTTPException(status_code=500, detail=error_details)
