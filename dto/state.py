from typing import List, Literal, Optional
from pydantic import BaseModel

from dto.base import PointState


class LobbyStatePayload(BaseModel):
    status: str
    players_num: int
    connected_players: list[str]
    created_by_player_id: str


class LobbyState(BaseModel):
    type: str = "lobby_state"
    payload: LobbyStatePayload


class CharacherStatsState(BaseModel):
    health: int
    max_health: int
    melee_power: int
    speed: int
    action_points: int
    view_distance: int
    accuracy: int


class WeaponState(BaseModel):
    id: str
    type: Literal["melee", "ranged"]
    name: str
    damage: int
    cost_ap: int
    range: int
    accuracy: int
    weight: int


class InventoryState(BaseModel):
    weapons: list[WeaponState]


class OverwatchStateDTO(BaseModel):
    weapon_id: str


class PartState(BaseModel):
    slot: str
    name: str
    rarity: str
    health: int
    speed: int
    accuracy: int
    melee_power: int
    view_distance: int
    max_health: int
    current_health: int
    destroyed: bool
    weight: int
    carry_capacity: int


class MechState(BaseModel):
    torso: PartState
    legs: PartState
    arms: PartState
    head: PartState
    preset_name: Optional[str] = None
    parts_weight: int
    weight_capacity: int


class MechPresetState(BaseModel):
    name: str
    description: str
    mech: MechState
    weapons: list[WeaponState]


class ActorState(BaseModel):
    id: str
    position: PointState
    stats: CharacherStatsState
    name: str
    current_action_points: int
    current_speed_spent: int
    inventory: InventoryState
    overwatch: Optional[OverwatchStateDTO] = None
    trophies: list[str] = []


class PlayerState(ActorState):
    team: int
    mech: MechState


class TurnState(BaseModel):
    number: int
    phase: int
    # current_actor ставим в None если это враг
    current_actor: ActorState | None
    available_moves: list[PointState]


class ChestState(BaseModel):
    position: PointState
    # loot не пробрасываем клиенту заранее, чтобы не палить содержимое до открытия


class MapState(BaseModel):
    width: int
    height: int
    tiles: List[List[str]]


class ArenaState(BaseModel):
    chests: list[ChestState]
    enemies: list[ActorState]
    map: MapState


class GameState(BaseModel):
    arena: ArenaState
    players: list[PlayerState]
    turn: TurnState
    version: int
    ended: bool
