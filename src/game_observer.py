from typing import Protocol, Optional, List, runtime_checkable

from dto.event import GameEvent


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
