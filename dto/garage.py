from uuid import UUID

from pydantic import BaseModel

from dto.state import CharacherStatsState, MechState, PartState, WeaponState


class GarageMetricsState(BaseModel):
    matches_finished: int
    reward_rolls: int
    rewards_received: int
    parts_equipped: int
    rematches_started: int


class GarageState(BaseModel):
    player_id: str
    mech: MechState
    stats: CharacherStatsState
    weapons: list[WeaponState]
    stored_parts: list[PartState]
    reward_chances: dict[str, float]
    metrics: GarageMetricsState


class EquipGaragePartRequest(BaseModel):
    player_id: UUID
    part_id: UUID


class RematchRequest(BaseModel):
    lobby_id: str
    host_player_id: UUID
