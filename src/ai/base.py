from abc import ABC, abstractmethod

from src.action import Action, ActionType
from src.entities.base import Actor
import typing_extensions

if typing_extensions.TYPE_CHECKING:
    from src.game import Game


class AI(ABC):
    def __init__(self, actor: Actor, game: "Game"):
        self.actor = actor
        self.game = game

    @abstractmethod
    def decide(self):
        pass

    def end_turn(self) -> Action:
        return Action(
            actor=self.actor, type=ActionType.END_TURN, cell=self.actor.position
        )
