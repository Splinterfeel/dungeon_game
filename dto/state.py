from typing import List
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


class StatsState(BaseModel):
    health: int
    damage: int
    speed: int
    action_points: int


class ActorState(BaseModel):
    id: str
    position: PointState
    stats: StatsState
    name: str
    current_action_points: int
    current_speed_spent: int


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
    exit: PointState


class GameState(BaseModel):
    dungeon: DungeonState
    players: list[ActorState]
    turn: TurnState
    version: int
