from fastapi import APIRouter, Depends, HTTPException

from dto.garage import (
    ChooseGarageSkillRequest,
    EquipGaragePartRequest,
    GarageState,
    UpdateGarageTuningRequest,
)
from src.api.deps import get_lobby_manager
from src.lobby.manager import LobbyManager


router = APIRouter()


@router.get(
    "/garages/{player_id}",
    description="Состояние общего in-memory гаража пилота",
)
def get_garage(
    player_id: str,
    lobby_manager: LobbyManager = Depends(get_lobby_manager),
) -> GarageState:
    try:
        return lobby_manager.get_garage_state(player_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))


@router.post(
    "/garages/equip",
    description="Установить деталь из гаража в сборку пилота",
)
def equip_garage_part(
    request: EquipGaragePartRequest,
    lobby_manager: LobbyManager = Depends(get_lobby_manager),
) -> GarageState:
    try:
        return lobby_manager.equip_garage_part(
            str(request.player_id),
            str(request.loadout_id),
            str(request.part_id),
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.post(
    "/garages/tuning",
    description="Изменить тюнинг сборки пилота",
)
def update_garage_tuning(
    request: UpdateGarageTuningRequest,
    lobby_manager: LobbyManager = Depends(get_lobby_manager),
) -> GarageState:
    try:
        return lobby_manager.update_garage_tuning(
            str(request.player_id),
            str(request.loadout_id),
            request.reactor_mode,
            request.fire_control_mode,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.post(
    "/garages/choose_skill",
    description="Выбрать навык пилота из доступных после level-up",
)
def choose_garage_skill(
    request: ChooseGarageSkillRequest,
    lobby_manager: LobbyManager = Depends(get_lobby_manager),
) -> GarageState:
    try:
        return lobby_manager.choose_garage_skill(
            str(request.player_id),
            request.skill_key,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
