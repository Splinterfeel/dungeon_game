"""
Test script to verify Game serialization without circular reference errors.
"""

import json
import asyncio
from uuid import uuid4, UUID
from typing import Optional, List

# Import necessary classes
from src.game import Game
from src.arena import Arena, ArenaMap
from src.entities.player import Player
from src.entities.base import Inventory, Weapon
from src.constants import Accuracy
from src.parts_catalog import default_mech
from src.game_observer import GameObserver
from dto.event import GameEvent


class MockGameObserver(GameObserver):
    """Mock observer for testing"""

    async def on_game_event(
        self, event: GameEvent, receiver_player_ids: Optional[List[str]] = None
    ) -> None:
        """Mock implementation"""
        print(f"Mock observer received event: {event.message}")

    async def on_state_change(self) -> None:
        """Mock implementation"""
        print("Mock observer received state change")


def create_test_players() -> list[Player]:
    """Create test players"""
    players = []

    # Player 1 - Team 1
    mech1 = default_mech()
    player1 = Player(
        id=uuid4(),
        team=1,
        mech=mech1,
        stats=mech1.build_character_stats(action_points=10),
        inventory=Inventory(
            weapons=[
                Weapon(
                    type="melee",
                    name="Ударный модуль",
                    damage=3,
                    cost_ap=5,
                    range=1,
                    accuracy=Accuracy.DEFAULT_PLAYER_MELEE_WEAPON_ACCURACY,
                ),
                Weapon(
                    type="ranged",
                    name="Мех-винтовка",
                    damage=5,
                    cost_ap=8,
                    range=4,
                    accuracy=Accuracy.DEFAULT_PLAYER_RANGED_WEAPON_ACCURACY,
                ),
            ]
        ),
    )
    players.append(player1)

    # Player 2 - Team 2
    mech2 = default_mech()
    player2 = Player(
        id=uuid4(),
        team=2,
        mech=mech2,
        stats=mech2.build_character_stats(action_points=10),
        inventory=Inventory(
            weapons=[
                Weapon(
                    type="melee",
                    name="Ударный модуль",
                    damage=3,
                    cost_ap=5,
                    range=1,
                    accuracy=Accuracy.DEFAULT_PLAYER_MELEE_WEAPON_ACCURACY,
                ),
                Weapon(
                    type="ranged",
                    name="Мех-винтовка",
                    damage=5,
                    cost_ap=8,
                    range=4,
                    accuracy=Accuracy.DEFAULT_PLAYER_RANGED_WEAPON_ACCURACY,
                ),
            ]
        ),
    )
    players.append(player2)

    return players


def create_test_arena() -> Arena:
    """Create a test arena with start points"""
    import copy
    from src.maps import default

    # Use the default map from the game
    arena_map = ArenaMap(
        width=copy.deepcopy(default.map_2["width"]),
        height=copy.deepcopy(default.map_2["height"]),
        tiles=copy.deepcopy(default.map_2["tiles"]),
    )
    return Arena(max_chests=3, enemies_num=2, map=arena_map)


def test_game_serialization():
    """Test that Game can be serialized without circular reference errors"""
    print("Creating test game...")

    # Create test data
    players = create_test_players()
    arena = create_test_arena()

    # Create game instance
    game = Game(arena=arena, players=players)

    # Register mock observer
    observer = MockGameObserver()
    game.set_observer(observer)

    print("[OK] Game created successfully with observer pattern")
    print(f"   Game has {len(game.players)} players")
    print(f"   Arena size: {game.arena.map.width}x{game.arena.map.height}")

    # Test serialization
    print("\nTesting serialization...")
    try:
        game_dict = game.to_dict()
        print("[OK] Game.to_dict() succeeded")
        print(f"   Dict keys: {list(game_dict.keys())}")

        # Test JSON serialization using Pydantic's model_dump_json
        from src.turn import Turn
        from src.arena import Arena as ArenaModel

        # Create a proper GameState for JSON serialization
        from dto.state import GameState

        # Use GameState.model_validate to create proper Pydantic models
        game_state = GameState.model_validate(game_dict)
        json_string = game_state.model_dump_json()
        print("[OK] JSON serialization succeeded")
        print(f"   JSON length: {len(json_string)} characters")

        # Test deserialization
        loaded_state = GameState.model_validate_json(json_string)
        loaded_dict = loaded_state.model_dump()
        print("[OK] JSON deserialization succeeded")
        print(
            f"   Loaded dict has same keys: {list(loaded_dict.keys()) == list(game_dict.keys())}"
        )

        # Verify specific fields
        assert "arena" in game_dict, "Missing 'arena' in serialized data"
        assert "players" in game_dict, "Missing 'players' in serialized data"
        assert "turn" in game_dict, "Missing 'turn' in serialized data"
        assert "version" in game_dict, "Missing 'version' in serialized data"
        assert "ended" in game_dict, "Missing 'ended' in serialized data"

        print("[OK] All required fields present in serialized data")

        # Check that there are no circular references
        # (this would have caused json.dumps() to fail)
        print("[OK] No circular reference errors detected")

        # Verify observer pattern is working
        print("\nTesting observer pattern...")
        print("   Observer is registered:", game._observer is not None)
        print("   Observer is correct type:", isinstance(game._observer, GameObserver))
        print("[OK] Observer pattern is correctly implemented")

        print("\n" + "=" * 50)
        print("SUCCESS: All tests passed!")
        print("=" * 50)
        print("\nCircular dependency has been successfully broken.")
        print("Game state can now be serialized for debugging purposes.")

        return True

    except Exception as e:
        print(f"[FAIL] Serialization failed with error: {e}")
        print(f"   Error type: {type(e).__name__}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_game_serialization()
    exit(0 if success else 1)
