from typing import Protocol, Optional, List, runtime_checkable

from dto.event import GameEvent
from src.action import ActorMovement
from src.combat import ActorAttack


@runtime_checkable
class GameObserver(Protocol):
    """Interface for observing Game events and state changes"""

    async def on_game_event(
        self, event: GameEvent, receiver_player_ids: Optional[List[str]] = None
    ) -> None:
        """Called when a game event occurs"""
        ...

    async def on_state_change(self) -> None:
        """Called when game state changes"""
        ...

    async def on_actor_moved(self, movements: dict[int, ActorMovement]) -> None:
        """Публикует законченный маршрут отдельно для каждой команды."""
        ...

    async def on_actor_attacked(self, attacks: dict[int, ActorAttack]) -> None:
        """Публикует видимый одной команде исход атаки."""
        ...
