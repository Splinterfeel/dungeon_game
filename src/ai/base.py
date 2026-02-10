from abc import ABC, abstractmethod
from pydantic import BaseModel


class AI(BaseModel, ABC):
    @abstractmethod
    def perform_action(self, actor, game):
        pass
