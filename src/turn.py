import enum
from typing import List, Optional, Set

from pydantic import BaseModel, Field

from src.base import Point
from src.entities.base import Actor


class GamePhase(enum.Enum):
    TEAM_1_PHASE = enum.auto()
    TEAM_2_PHASE = enum.auto()
    AI_ENEMY_PHASE = enum.auto()

    def __str__(self):
        return self.name


class Turn(BaseModel):
    number: int = 0
    phase: GamePhase = GamePhase.TEAM_1_PHASE
    current_actor: Optional[Actor] = None
    available_moves: List[Point] = Field(default_factory=list)
    actor_ids_passed_turn: Set[str] = Field(default_factory=set)

    def next(self):
        self.number += 1
        self.actor_ids_passed_turn = set()
        self.phase = GamePhase.TEAM_1_PHASE

    def set_current_actor(self, actor: Actor):
        if actor.id in self.actor_ids_passed_turn:
            raise ValueError("actor already ran his turn:", actor.id)
        self.actor_ids_passed_turn.add(actor.id)
        self.current_actor = actor

    def has_next_phase(self) -> bool:
        if self.phase == GamePhase.TEAM_1_PHASE:
            return True
        if self.phase == GamePhase.TEAM_2_PHASE:
            return True
        return False

    def switch_phase(self):
        if not self.has_next_phase():
            raise ValueError("can't switch phase")
        if self.phase == GamePhase.TEAM_1_PHASE:
            self.phase = GamePhase.TEAM_2_PHASE
        elif self.phase == GamePhase.TEAM_2_PHASE:
            self.phase = GamePhase.AI_ENEMY_PHASE
