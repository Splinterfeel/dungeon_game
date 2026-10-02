from fastapi import APIRouter, Depends, HTTPException
from uuid import uuid4

from dto.garage import (
    ChooseGarageSkillRequest,
    CreatePilotRequest,
    EquipGaragePartRequest,
    GarageState,
    PilotSummaryState,
    UpdateGarageTuningRequest,
)
from src.api.deps import get_garage_manager
from src.garage_manager import GarageManager

router = APIRouter()


@router.get("/pilots", description="Получить список пилотов для временного входа")
async def list_pilots(
    garage_manager: GarageManager = Depends(get_garage_manager),
) -> list[PilotSummaryState]:
    return await garage_manager.list_pilots()


@router.post("/pilots", description="Создать пилота с двумя стартовыми сборками")
async def create_pilot(
    request: CreatePilotRequest,
    garage_manager: GarageManager = Depends(get_garage_manager),
) -> GarageState:
    name = request.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Имя пилота не должно быть пустым")
    try:
        profile = await garage_manager.create_starting_profile(
            player_id=uuid4(),
            mech_presets=request.mech_presets,
            name=name,
        )
        return await garage_manager.get_garage_state(str(profile.player_id))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.get(
    "/garages/{player_id}",
    description="Состояние постоянного гаража пилота",
)
async def get_garage(
    player_id: str,
    garage_manager: GarageManager = Depends(get_garage_manager),
) -> GarageState:
    try:
        return await garage_manager.get_garage_state(player_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))


@router.post(
    "/garages/equip",
    description="Установить деталь из гаража в сборку пилота",
)
async def equip_garage_part(
    request: EquipGaragePartRequest,
    garage_manager: GarageManager = Depends(get_garage_manager),
) -> GarageState:
    try:
        return await garage_manager.equip_garage_part(
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
async def update_garage_tuning(
    request: UpdateGarageTuningRequest,
    garage_manager: GarageManager = Depends(get_garage_manager),
) -> GarageState:
    try:
        return await garage_manager.update_garage_tuning(
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
async def choose_garage_skill(
    request: ChooseGarageSkillRequest,
    garage_manager: GarageManager = Depends(get_garage_manager),
) -> GarageState:
    try:
        return await garage_manager.choose_garage_skill(
            str(request.player_id),
            request.skill_key,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
