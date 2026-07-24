from uuid import UUID

from pydantic import BaseModel

from dto.state import CharacherStatsState, MechState, PartState, SkillState, WeaponState


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
    reactor_mode: str
    fire_control_mode: str
    mech: MechState
    stats: CharacherStatsState
    weapons: list[WeaponState]


class PendingSkillChoiceState(BaseModel):
    level: int
    options: list[SkillState]


class GarageState(BaseModel):
    player_id: str
    xp: int
    level: int
    owned_skills: list[SkillState]
    pending_skill_choices: list[PendingSkillChoiceState]
    loadouts: list[GarageLoadoutState]
    stored_parts: list[PartState]
    reward_chances: dict[str, float]
    metrics: GarageMetricsState


class EquipGaragePartRequest(BaseModel):
    player_id: UUID
    loadout_id: UUID
    part_id: UUID


class UpdateGarageTuningRequest(BaseModel):
    player_id: UUID
    loadout_id: UUID
    reactor_mode: str
    fire_control_mode: str


class ChooseGarageSkillRequest(BaseModel):
    player_id: UUID
    skill_key: str


class RematchRequest(BaseModel):
    lobby_id: str
    host_player_id: UUID
