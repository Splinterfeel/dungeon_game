"""Game state dump/restore utilities"""

from uuid import UUID
from datetime import datetime
from typing import Dict, Any

from dto.debug import DebugDumpResponse, DebugRestoreResponse
from src.dungeon import Dungeon, DungeonMap
from src.entities.player import Player
from src.entities.enemy import Enemy
from src.entities.chest import Chest
from src.entities.base import CharacterStats
from src.entities.mech import Mech
from src.turn import Turn, GamePhase
from src.base import Point
from src.game import Game
from lobby import Lobby


def create_debug_dump_response(
    lobby: Lobby, game_state: Dict[str, Any]
) -> DebugDumpResponse:
    """Create a debug dump response from lobby and game state"""
    # Get players info
    players_info = [
        {
            "id": str(player.id),
            "name": player.name,
            "team": player.team,
            "is_connected": str(player.id) in lobby.connections,
        }
        for player in lobby.players.values()
    ]

    return DebugDumpResponse(
        lobby_id=str(lobby.id),
        lobby_name=lobby.name,
        game_state=game_state,
        timestamp=datetime.now().isoformat(),
        players_info=players_info,
    )


def restore_player_from_data(player_data: Dict[str, Any]) -> Player:
    """Restore a Player object from dump data"""
    player_uuid = UUID(player_data["id"])

    # Create player with restored state
    restored_player = Player(
        id=player_uuid,
        team=player_data["team"],
        mech=Mech.model_validate(player_data["mech"]),
        xp=player_data.get("xp", 0),
        level=player_data.get("level", 1),
        stats=CharacterStats(
            health=player_data["stats"]["health"],
            melee_power=player_data["stats"]["melee_power"],
            speed=player_data["stats"]["speed"],
            action_points=player_data["stats"]["action_points"],
            view_distance=player_data["stats"]["view_distance"],
            accuracy=player_data["stats"]["accuracy"],
        ),
        inventory=player_data["inventory"],
    )

    # Restore current state
    restored_player.position = (
        Point(**player_data["position"])
        if isinstance(player_data["position"], dict)
        else player_data["position"]
    )
    restored_player.current_action_points = player_data["current_action_points"]
    restored_player.current_speed_spent = player_data.get("current_speed_spent", 0)
    restored_player.overwatch = player_data.get("overwatch")
    restored_player.name = player_data.get("name", f"Player {player_data['team']}")

    return restored_player


def restore_dungeon_from_data(dungeon_data: Dict[str, Any]) -> Dungeon:
    """Restore a Dungeon object from dump data"""
    map_data = dungeon_data["map"]

    # Extract start points from tiles
    tiles = map_data["tiles"]
    start_points_team_1 = []
    start_points_team_2 = []

    for y, row in enumerate(tiles):
        for x, cell in enumerate(row):
            if isinstance(cell, str):
                if "S1" in cell:
                    start_points_team_1.append(Point(x=x, y=y))
                elif "S2" in cell:
                    start_points_team_2.append(Point(x=x, y=y))

    # Create DungeonMap
    dungeon_map = DungeonMap.model_construct(
        width=map_data["width"],
        height=map_data["height"],
        tiles=map_data["tiles"],
        start_points_team_1=start_points_team_1,
        start_points_team_2=start_points_team_2,
    )

    # Restore enemies and chests
    restored_enemies = []
    for e in dungeon_data["enemies"]:
        restored_enemies.append(Enemy.model_validate(e))

    restored_chests = []
    for c in dungeon_data["chests"]:
        restored_chests.append(Chest(**c) if isinstance(c, dict) else c)

    # Create Dungeon
    dungeon = Dungeon.model_construct(
        max_chests=dungeon_data["max_chests"],
        enemies_num=dungeon_data["enemies_num"],
        map=dungeon_map,
        start_points_team_1=start_points_team_1,
        start_points_team_2=start_points_team_2,
        enemies=restored_enemies,
        chests=restored_chests,
    )

    # Initialize _initial_map since model_construct bypasses validation
    dungeon._initial_map = dungeon_map.model_copy(deep=True)
    dungeon._initial_map.clear_start_points(clear_players_points=True)

    return dungeon


def restore_turn_from_data(turn_data: Dict[str, Any]) -> Turn:
    """Restore a Turn object from dump data"""
    turn = Turn(
        number=turn_data["number"],
        phase=turn_data["phase"],
        actor_ids_passed_turn=set(turn_data.get("actor_ids_passed_turn", [])),
    )

    turn.available_moves = [
        Point(x=m["x"], y=m["y"]) if isinstance(m, dict) else Point(x=m[0], y=m[1])
        for m in turn_data.get("available_moves", [])
    ]

    return turn


def find_current_actor(
    current_actor_data: Dict[str, Any], players: list, enemies: list
):
    """Find and restore the current actor reference"""
    actor_id = current_actor_data["id"]

    # Find actor in players or enemies
    for player in players:
        if str(player.id) == actor_id:
            return player

    for enemy in enemies:
        if str(enemy.id) == actor_id:
            return enemy

    return None


def restore_game_state(
    game_data: Dict[str, Any], lobby_id: UUID, lobby_name: str
) -> Lobby:
    """Restore complete game state from dump data"""
    # Create a fresh lobby with the provided ID
    lobby = Lobby(name=lobby_name, players_num=2, created_by_player_id=lobby_id)
    lobby.id = lobby_id  # Override the generated ID with the provided one

    # Extract and add players from the dump
    player_states = {p["id"]: p for p in game_data["players"]}

    for player_id, player_data in player_states.items():
        restored_player = restore_player_from_data(player_data)
        lobby.players[str(player_id)] = restored_player

    # Restore dungeon
    dungeon = restore_dungeon_from_data(game_data["dungeon"])

    # Restore players list for game
    restored_players = list(lobby.players.values())

    # Restore turn
    turn = restore_turn_from_data(game_data["turn"])

    # Create new game instance
    lobby.game = Game(
        dungeon=dungeon,
        players=restored_players,
        turn=turn,
        version=game_data.get("version", 0),
    )
    lobby.game.ended = game_data.get("ended", False)

    # Register lobby as observer
    lobby.game.set_observer(lobby)

    # Restore current actor reference
    if game_data["turn"].get("current_actor"):
        current_actor = find_current_actor(
            game_data["turn"]["current_actor"], restored_players, dungeon.enemies
        )
        lobby.game.turn.current_actor = current_actor
    else:
        lobby.game.turn.current_actor = None

    return lobby


def create_restore_response(lobby_id: UUID, lobby_name: str) -> DebugRestoreResponse:
    """Create a restore response"""
    return DebugRestoreResponse(
        success=True,
        message=f"Game state restored successfully in new lobby '{lobby_name}'",
        lobby_id=str(lobby_id),
        timestamp=datetime.now().isoformat(),
    )
