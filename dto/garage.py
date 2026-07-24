from uuid import UUID

from pydantic import BaseModel

from dto.state import CharacherStatsState, MechState, PartState, WeaponState


class GarageMetricsState(BaseModel):
    matches_finished: int
    reward_rolls: int
    rewards_received: int
    parts_equipped: int
    rematches_started: int


class GarageLoadoutState(BaseModel):
    id: str
    name: str
    preset_name: str | None
    mech: MechState
    stats: CharacherStatsState
    weapons: list[WeaponState]


class GarageState(BaseModel):
    player_id: str
    loadouts: list[GarageLoadoutState]
    stored_parts: list[PartState]
    reward_chances: dict[str, float]
    metrics: GarageMetricsState


class EquipGaragePartRequest(BaseModel):
    player_id: UUID
    loadout_id: UUID
    part_id: UUID


class RematchRequest(BaseModel):
    lobby_id: str
    host_player_id: UUID
