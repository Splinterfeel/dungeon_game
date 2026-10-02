from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from dto.base import (
    ConnectLobbyRequest,
    CreateLobbyRequest,
    DetailedBoolResponse,
    LeaveLobbyRequest,
    LobbyDTO,
    StartGameRequest,
    StartGameResponse,
)
from dto.state import MechPresetState
from src.api.deps import get_lobby_manager
from src.lobby.manager import LobbyManager
from src.mech.presets import MECH_PRESETS

router = APIRouter()


@router.get("/lobbies", description="Получить список лобби")
def get_lobbies_list(
    lobby_manager: LobbyManager = Depends(get_lobby_manager),
) -> list[LobbyDTO]:
    return lobby_manager.get_lobbies_list()


@router.get(
    "/mech_presets",
    description="Список доступных пресетов меха (для выбора при подключении к лобби)",
)
def get_mech_presets() -> list[MechPresetState]:
    return [
        MechPresetState.model_validate(preset.model_dump()) for preset in MECH_PRESETS
    ]


@router.post("/lobbies", description="Создать лобби")
def create_lobby(
    request: CreateLobbyRequest,
    lobby_manager: LobbyManager = Depends(get_lobby_manager),
) -> dict[str, UUID]:
    game_lobby = lobby_manager.create_lobby(request)
    return {"lobby_id": game_lobby.id}


@router.post("/connect_lobby", description="Присоединиться к лобби (игрок)")
async def connect_lobby(
    request: ConnectLobbyRequest,
    lobby_manager: LobbyManager = Depends(get_lobby_manager),
) -> DetailedBoolResponse:
    lobby = lobby_manager.get_lobby(request.lobby_id)
    if not lobby:
        raise HTTPException(status_code=404, detail="Lobby not found")
    result, detail = await lobby.connect_player(request.player)
    return DetailedBoolResponse(result=result, detail=detail)


@router.post("/leave_lobby", description="Выйти из не начатого лобби")
async def leave_lobby(
    request: LeaveLobbyRequest,
    lobby_manager: LobbyManager = Depends(get_lobby_manager),
) -> DetailedBoolResponse:
    result, detail = await lobby_manager.leave_lobby(
        request.lobby_id, str(request.player_id)
    )
    if not result and detail == "Лобби не найдено":
        raise HTTPException(status_code=404, detail=detail)
    return DetailedBoolResponse(result=result, detail=detail)


@router.post("/start_game", description="Стартовать игру")
async def start_game(
    request: StartGameRequest,
    lobby_manager: LobbyManager = Depends(get_lobby_manager),
) -> StartGameResponse:
    lobby = lobby_manager.get_lobby(request.lobby_id)
    if not lobby:
        raise HTTPException(status_code=404, detail="Lobby not found")
    if str(request.host_player_id) != lobby.created_by_player_id:
        return StartGameResponse(
            lobby_id=request.lobby_id,
            result=False,
            detail="Стартовать матч может только хост",
        )
    result, detail = await lobby.start_game()
    if result:
        await lobby.publish_started_game()
    return StartGameResponse(
        lobby_id=request.lobby_id,
        result=result,
        detail=detail,
    )
