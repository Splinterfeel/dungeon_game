"""Game state dump/restore utilities"""

from uuid import UUID
from datetime import datetime
from typing import Dict, Any

from dto.debug import DebugDumpResponse, DebugRestoreResponse
from src.arena import Arena, ArenaMap
from src.entities.player import Player
from src.garage import GarageProfile
from src.entities.enemy import Enemy
from src.entities.base import CharacterStats
from src.entities.mech import Mech
from src.skills_catalog import Skill
from src.turn import Turn
from src.base import Point
from src.game import Game
from lobby import Lobby, LobbyParticipant


def create_debug_dump_response(
    lobby: Lobby, game_state: Dict[str, Any]
) -> DebugDumpResponse:
    """Create a debug dump response from lobby and game state"""
    # Get players info
    players_info = [
        {
            "id": participant.player_id,
            "team": participant.team,
            "actor_ids": participant.actor_ids,
            "is_connected": participant.player_id in lobby.connections,
        }
        for participant in lobby.participants.values()
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
        owner_player_id=player_data.get("owner_player_id", player_uuid),
        loadout_id=player_data.get("loadout_id"),
        name=player_data.get("name"),
        mech=Mech.model_validate(player_data["mech"]),
        xp=player_data.get("xp", 0),
        level=player_data.get("level", 1),
        skills=[Skill.model_validate(skill) for skill in player_data.get("skills", [])],
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
    return restored_player


def restore_arena_from_data(arena_data: Dict[str, Any]) -> Arena:
    """Restore an Arena object from dump data"""
    map_data = arena_data["map"]

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

    # Create ArenaMap
    arena_map = ArenaMap.model_construct(
        width=map_data["width"],
        height=map_data["height"],
        tiles=map_data["tiles"],
        start_points_team_1=start_points_team_1,
        start_points_team_2=start_points_team_2,
    )

    # Restore enemies
    restored_enemies = []
    for e in arena_data["enemies"]:
        restored_enemies.append(Enemy.model_validate(e))

    # Create Arena
    arena = Arena.model_construct(
        enemies_num=arena_data["enemies_num"],
        map=arena_map,
        start_points_team_1=start_points_team_1,
        start_points_team_2=start_points_team_2,
        enemies=restored_enemies,
    )

    # Initialize _initial_map since model_construct bypasses validation.
    # Только террейн, без маркеров сущностей — см. Arena.__save_initial_map.
    arena._initial_map = arena_map.model_copy(deep=True)
    arena._initial_map.keep_only_terrain()

    return arena


def restore_turn_from_data(turn_data: Dict[str, Any]) -> Turn:
    """Restore a Turn object from dump data"""
    turn = Turn(
        number=turn_data["number"],
        phase=turn_data["phase"],
        actor_ids_passed_turn=set(turn_data.get("actor_ids_passed_turn", [])),
        player_actor_order=turn_data.get("player_actor_order", []),
        player_order_index=turn_data.get("player_order_index", -1),
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
    game_data: Dict[str, Any], lobby_id: UUID, lobby_name: str, garages: dict
) -> Lobby:
    """Restore complete game state from dump data"""
    # Create a fresh lobby with the provided ID
    owner_ids = list(
        dict.fromkeys(
            str(player.get("owner_player_id", player["id"]))
            for player in game_data["players"]
        )
    )
    lobby = Lobby(
        name=lobby_name,
        players_num=len(owner_ids),
        created_by_player_id=owner_ids[0] if owner_ids else lobby_id,
        garages=garages,
    )
    lobby.id = lobby_id  # Override the generated ID with the provided one

    # Extract and add players from the dump
    restored_by_owner: dict[str, list[Player]] = {}
    for player_data in game_data["players"]:
        restored_player = restore_player_from_data(player_data)
        actor_id = str(restored_player.id)
        owner_id = str(restored_player.owner_player_id)
        lobby.players[actor_id] = restored_player
        restored_by_owner.setdefault(owner_id, []).append(restored_player)

    for owner_id, owned_actors in restored_by_owner.items():
        lobby.participants[owner_id] = LobbyParticipant(
            player_id=owner_id,
            team=owned_actors[0].team,
            actor_ids=[str(actor.id) for actor in owned_actors],
        )
        if owner_id not in garages:
            garages[owner_id] = GarageProfile.from_players(owned_actors)

    # Restore arena
    arena = restore_arena_from_data(game_data["arena"])

    # Restore players list for game
    restored_players = list(lobby.players.values())

    # Restore turn
    turn = restore_turn_from_data(game_data["turn"])

    # Create new game instance
    lobby.game = Game(
        arena=arena,
        players=restored_players,
        turn=turn,
        version=game_data.get("version", 0),
    )
    lobby.game.ended = game_data.get("ended", False)
    lobby.game.winner = game_data.get("winner")

    # Register lobby as observer
    lobby.game.set_observer(lobby)

    # Restore current actor reference
    if game_data["turn"].get("current_actor"):
        current_actor = find_current_actor(
            game_data["turn"]["current_actor"], restored_players, arena.enemies
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
