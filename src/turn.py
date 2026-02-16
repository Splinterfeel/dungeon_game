import enum

from src.base import Point
from src.entities.base import Actor


class GamePhase(enum.Enum):
    PLAYER_PHASE = enum.auto()
    ENEMY_PHASE = enum.auto()

    def __str__(self):
        return self.name


class Turn:
    def __init__(
        self,
        number: int = None,
        phase: GamePhase = None,
        current_actor: Actor = None,
        available_moves: list[Point] = None,
    ):
        self.number = number if number is not None else 0
        self.phase = GamePhase(phase) if phase is not None else GamePhase.PLAYER_PHASE
        self.current_actor = current_actor if current_actor is not None else None
        self.available_moves = available_moves if available_moves is not None else []
        self.actor_ids_passed_turn: set[str] = set()

    def next(self):
        self.number += 1
        self.actor_ids_passed_turn = set()
        self.phase = GamePhase.PLAYER_PHASE

    def set_current_actor(self, actor: Actor):
        if actor.id in self.actor_ids_passed_turn:
            raise ValueError("actor already ran his turn:", actor.id)
        self.actor_ids_passed_turn.add(actor.id)
        self.current_actor = actor

    def has_next_phase(self) -> bool:
        if self.phase == GamePhase.PLAYER_PHASE:
            return True
        return False

    def switch_phase(self):
        if not self.has_next_phase():
            raise ValueError("can't switch phase")
        if self.phase == GamePhase.PLAYER_PHASE:
            self.phase = GamePhase.ENEMY_PHASE

    def to_dict(self):
        return {
            "number": self.number,
            "phase": self.phase.value,
            "current_actor": (
                self.current_actor.to_dict() if self.current_actor else None
            ),
            "available_moves": [m.to_dict() for m in self.available_moves],
        }

    @classmethod
    def from_dict(cls, _dict):
        return cls(
            **{
                "number": _dict["number"],
                "phase": GamePhase(_dict["phase"]),
                "current_actor": (
                    Actor.from_dict(_dict["current_actor"])
                    if _dict["current_actor"]
                    else None
                ),
                "available_moves": [
                    Point.from_dict(m) for m in _dict["available_moves"]
                ],
            }
        )
