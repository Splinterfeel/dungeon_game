import enum
from typing import List, Optional, Set

from pydantic import BaseModel, Field

from src.base import Point
from src.entities.base import Actor


class GamePhase(enum.Enum):
    PLAYER_PHASE = enum.auto()
    AI_ENEMY_PHASE = enum.auto()

    def __str__(self):
        return self.name


class Turn(BaseModel):
    number: int = 0
    phase: GamePhase = GamePhase.PLAYER_PHASE
    current_actor: Optional[Actor] = None
    available_moves: List[Point] = Field(default_factory=list)
    actor_ids_passed_turn: Set[str] = Field(default_factory=set)
    player_actor_order: List[str] = Field(default_factory=list)
    player_order_index: int = -1

    def next(self):
        self.number += 1
        self.actor_ids_passed_turn = set()
        self.phase = GamePhase.PLAYER_PHASE
        self.player_order_index = -1
        self.current_actor = None

    def set_current_actor(self, actor: Actor):
        actor_id = str(actor.id)
        if actor_id in self.actor_ids_passed_turn:
            raise ValueError("actor already ran his turn:", actor.id)
        self.actor_ids_passed_turn.add(actor_id)
        self.current_actor = actor
