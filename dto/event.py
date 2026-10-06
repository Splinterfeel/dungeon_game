from pydantic import BaseModel, Field
from dto.base import PointState
from dto.state import ActorState, PartState, PlayerState
from src.combat import AttackKind
from src.entities.base import WeaponType


class GameEvent(BaseModel):
    type: str = "game_event"
    message: str
    loot_part: PartState | None = None


class ActionResultEvent(BaseModel):
    type: str = "action_result"
    action_id: str | None
    performed: bool
    detail: str


class ActorMovedEvent(BaseModel):
    type: str = "actor_moved"
    action_id: str
    actor: PlayerState | ActorState
    paths: list[list[PointState]]
    sightings: list[PlayerState | ActorState] = Field(default_factory=list)


class ActorAttackedEvent(BaseModel):
    type: str = "actor_attacked"
    attack_id: str
    attacker_id: str | None
    target_id: str | None
    from_cell: PointState | None
    to_cell: PointState | None
    weapon_type: WeaponType
    kind: AttackKind
    hit: bool
    damage: int
    target_killed: bool
    movement_action_id: str | None = None


class MatchResultEvent(BaseModel):
    type: str = "match_result"
    match_id: str
    winner: int | None
    xp_awarded: int
    level_before: int
    level_after: int
    loot_part: PartState | None


class LobbyClosedEvent(BaseModel):
    type: str = "lobby_closed"
    message: str
