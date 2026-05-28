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
    damage: int
    speed: int
    action_points: int
    view_distance: int


class WeaponState(BaseModel):
    id: str
    type: Literal["melee", "ranged"]
    name: str
    damage: int
    cost_ap: int
    range: int
    accuracy: int


class InventoryState(BaseModel):
    weapons: list[WeaponState]


class OverwatchStateDTO(BaseModel):
    weapon_id: str


class ActorState(BaseModel):
    id: str
    position: PointState
    stats: CharacherStatsState
    name: str
    current_action_points: int
    current_speed_spent: int
    inventory: InventoryState
    overwatch: Optional[OverwatchStateDTO] = None


class PlayerState(ActorState):
    team: int


class TurnState(BaseModel):
    number: int
    phase: int
    # current_actor ставим в None если это враг
    current_actor: ActorState | None
    available_moves: list[PointState]


class ChestState(BaseModel):
    position: PointState
    # gold не пробрасываем


class MapState(BaseModel):
    width: int
    height: int
    tiles: List[List[str]]


class DungeonState(BaseModel):
    chests: list[ChestState]
    enemies: list[ActorState]
    map: MapState
    exits: List[PointState]


class GameState(BaseModel):
    dungeon: DungeonState
    players: list[PlayerState]
    turn: TurnState
    version: int
    ended: bool
