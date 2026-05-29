"""Test script for debug dump/restore functionality"""

import requests
import json
import time
from uuid import uuid4

# API base URL
BASE_URL = "http://localhost:8000"


def test_dump_restore_workflow():
    """Test the complete dump/restore workflow"""
    print("=== Testing Dump/Restore Functionality ===\n")

    # Step 1: Create a test lobby
    print("Step 1: Creating test lobby...")
    player_id = str(uuid4())
    lobby_response = requests.post(
        f"{BASE_URL}/lobbies",
        json={"players_num": 2, "created_by_player_id": player_id},
    )

    if lobby_response.status_code != 200:
        print(f"FAIL: Could not create lobby. Status: {lobby_response.status_code}")
        return False

    lobby_id = lobby_response.json()["lobby_id"]
    print(f"OK: Lobby created with ID: {lobby_id}")

    # Step 2: Connect players
    print("\nStep 2: Connecting players to lobby...")
    player2_id = str(uuid4())

    # Connect player 1 (team 1)
    connect_response = requests.post(
        f"{BASE_URL}/connect_lobby",
        json={"lobby_id": lobby_id, "player": {"id": player_id, "team": 1}},
    )

    if connect_response.status_code != 200:
        print(
            f"FAIL: Could not connect player 1. Status: {connect_response.status_code}"
        )
        return False

    print("OK: Player 1 connected")

    # Connect player 2 (team 2)
    connect_response = requests.post(
        f"{BASE_URL}/connect_lobby",
        json={"lobby_id": lobby_id, "player": {"id": player2_id, "team": 2}},
    )

    if connect_response.status_code != 200:
        print(
            f"FAIL: Could not connect player 2. Status: {connect_response.status_code}"
        )
        return False

    print("OK: Player 2 connected")

    # Step 3: Start game
    print("\nStep 3: Starting game...")
    start_response = requests.post(
        f"{BASE_URL}/start_game", json={"lobby_id": lobby_id}
    )

    if start_response.status_code != 200:
        print(f"FAIL: Could not start game. Status: {start_response.status_code}")
        return False

    print("OK: Game started")

    # Give game a moment to initialize
    time.sleep(1)

    # Step 4: Test dump endpoint
    print("\nStep 4: Testing dump endpoint...")
    dump_response = requests.post(
        f"{BASE_URL}/debug/dump_game_state", json={"lobby_id": lobby_id}
    )

    if dump_response.status_code != 200:
        print(f"FAIL: Could not dump game state. Status: {dump_response.status_code}")
        print(f"Response: {dump_response.text}")
        return False

    dump_data = dump_response.json()
    print(f"OK: Game state dumped successfully")
    print(f"   Lobby: {dump_data['lobby_name']}")
    print(f"   Timestamp: {dump_data['timestamp']}")
    print(f"   Players: {len(dump_data['players_info'])}")

    # Verify dump structure
    assert "game_state" in dump_data, "Missing game_state in response"
    assert "dungeon" in dump_data["game_state"], "Missing dungeon in game_state"
    assert "players" in dump_data["game_state"], "Missing players in game_state"
    assert "turn" in dump_data["game_state"], "Missing turn in game_state"
    print("OK: Dump data structure validated")

    # Save dump to file for manual inspection
    with open(f"game_dump_{lobby_id}.json", "w") as f:
        json.dump(dump_data, f, indent=2)
    print(f"OK: Game state saved to game_dump_{lobby_id}.json")

    # Step 5: Test restore endpoint
    print("\nStep 5: Testing restore endpoint...")
    restore_response = requests.post(
        f"{BASE_URL}/debug/restore_game_state",
        json={"lobby_id": lobby_id, "game_state": dump_data["game_state"]},
    )

    if restore_response.status_code != 200:
        print(
            f"FAIL: Could not restore game state. Status: {restore_response.status_code}"
        )
        print(f"Response: {restore_response.text}")
        return False

    restore_data = restore_response.json()
    print(f"OK: Game state restored successfully")
    print(f"   Message: {restore_data['message']}")
    print(f"   Timestamp: {restore_data['timestamp']}")

    # Step 6: Verify dump still works after restore
    print("\nStep 6: Verifying game state after restore...")
    dump_after_restore = requests.post(
        f"{BASE_URL}/debug/dump_game_state", json={"lobby_id": lobby_id}
    )

    if dump_after_restore.status_code != 200:
        print(
            f"FAIL: Could not dump after restore. Status: {dump_after_restore.status_code}"
        )
        return False

    post_restore_data = dump_after_restore.json()
    print(f"OK: Game state dumpable after restore")
    print(f"   Game version: {post_restore_data['game_state']['version']}")

    print("\n" + "=" * 50)
    print("SUCCESS: All dump/restore tests passed!")
    print("=" * 50)
    print(f"\nYou can test the endpoints manually at: {BASE_URL}/api/docs")
    print(f"Test Lobby ID: {lobby_id}")
    print(f"Player 1 ID: {player_id}")
    print(f"Player 2 ID: {player2_id}")

    return True


if __name__ == "__main__":
    try:
        success = test_dump_restore_workflow()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\nFAIL: Test failed with exception: {e}")
        import traceback

        traceback.print_exc()
        exit(1)
