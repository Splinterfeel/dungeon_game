from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from uuid import UUID
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware
from dto.action import GameActionState
from dto.base import (
    ConnectLobbyRequest,
    CreateLobbyRequest,
    DetailedBoolResponse,
    LobbyDTO,
    StartGameRequest,
    StartGameResponse,
)
from dto.debug import (
    DebugDumpRequest,
    DebugDumpResponse,
    DebugRestoreRequest,
    DebugRestoreResponse,
)
from dto.event import GameEvent
from lobby import Lobby
from lobby_manager import LobbyManager
from src.ai.enemy import SimpleEnemyAI
from src.turn import GamePhase
from src.entities.chest import Chest
from src.entities.base import CharacterStats
from src.base import Point
from src.game import Game
from fastapi.staticfiles import StaticFiles

from ws_utils import WSCloseCodes


app = FastAPI(docs_url="/api/docs", redoc_url="/redoc")

# CORS — разрешаем текущий хост и localhost для дебага
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
lobby_manager = LobbyManager()


@app.get("/", response_class=HTMLResponse)
async def debug_map(request: Request):
    host = request.headers.get("host", "localhost:8000")
    return templates.TemplateResponse(
        "debug_map.html", {"request": request, "host": host}
    )


@app.get("/lobbies", description="Получить список лобби")
def get_lobbies_list() -> list[LobbyDTO]:
    return lobby_manager.get_lobbies_list()


@app.post("/lobbies", description="Создать лобби")
def create_lobby(request: CreateLobbyRequest) -> dict[str, UUID]:
    game_lobby = lobby_manager.create_lobby(request)
    return {"lobby_id": game_lobby.id}


@app.post("/connect_lobby", description="Присоединиться к лобби (игрок)")
async def connect_lobby(request: ConnectLobbyRequest) -> DetailedBoolResponse:
    lobby = lobby_manager.get_lobby(request.lobby_id)
    if not lobby:
        raise HTTPException(status_code=404, detail="Lobby not found")
    result, detail = await lobby.connect_player(request.player)
    return DetailedBoolResponse(result=result, detail=detail)


@app.post("/start_game", description="Стартовать игру")
async def start_game(request: StartGameRequest) -> StartGameResponse:
    # TODO проверка что стартует именно тот игрок который указан как создатель в лобби (host)
    lobby = lobby_manager.get_lobby(request.lobby_id)
    if not lobby:
        raise HTTPException(status_code=404, detail="Lobby not found")
    result, detail = await lobby.start_game()
    await lobby.broadcast_lobby_state()
    await lobby.broadcast_game_state()
    return StartGameResponse(
        lobby_id=request.lobby_id,
        result=result,
        detail=detail,
    )


# =========================
# Debug — dump/restore game state
# =========================


@app.post(
    "/debug/dump_game_state", description="Dump current game state to JSON (debug only)"
)
async def dump_game_state(request: DebugDumpRequest) -> DebugDumpResponse:
    """Dump game state for debugging purposes"""
    lobby = lobby_manager.get_lobby(request.lobby_id)
    if not lobby:
        raise HTTPException(status_code=404, detail="Lobby not found")

    if not lobby.game:
        raise HTTPException(
            status_code=400, detail="No game in progress for this lobby"
        )

    try:
        # Get game state as dictionary
        game_state = lobby.game.to_dict()

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
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to dump game state: {str(e)}"
        )


@app.post(
    "/debug/restore_game_state", description="Restore game state from JSON (debug only)"
)
async def restore_game_state(request: DebugRestoreRequest) -> DebugRestoreResponse:
    """Restore game state for debugging purposes - creates a fresh lobby with provided ID"""
    try:
        # Import necessary classes for reconstruction
        from src.dungeon import Dungeon, DungeonMap
        from src.entities.player import Player
        from src.entities.enemy import Enemy
        from src.turn import Turn
        from src.entities.base import Actor
        from src.action import Action
        import copy
        from src.maps import default

        # Get lobby info from game state dump
        game_data = request.game_state
        lobby_id = UUID(request.lobby_id)
        lobby_name = request.lobby_name or f"Restored Lobby {request.lobby_id[:8]}"

        # Create a fresh lobby with the provided ID
        lobby = Lobby(name=lobby_name, players_num=2, created_by_player_id=lobby_id)
        lobby.id = lobby_id  # Override the generated ID with the provided one

        # Extract and add players from the dump
        player_states = {p["id"]: p for p in game_data["players"]}

        for player_id, player_data in player_states.items():
            player_uuid = UUID(player_id)
            # Create player with restored state
            restored_player = Player(
                id=player_uuid,
                team=player_data["team"],
                stats=CharacterStats(
                    health=player_data["stats"]["health"],
                    damage=player_data["stats"]["damage"],
                    speed=player_data["stats"]["speed"],
                    action_points=player_data["stats"]["action_points"],
                    view_distance=player_data["stats"]["view_distance"],
                    accuracy=player_data["stats"]["accuracy"],
                ),
                inventory=player_data["inventory"],
            )
            # Restore current state
            restored_player.position = player_data["position"]
            restored_player.current_action_points = player_data["current_action_points"]
            restored_player.current_speed_spent = player_data.get(
                "current_speed_spent", 0
            )
            restored_player.overwatch = player_data.get("overwatch")
            restored_player.name = player_data.get(
                "name", f"Player {player_data['team']}"
            )

            # Add to lobby
            lobby.players[str(player_id)] = restored_player

        # Reconstruct dungeon
        dungeon_data = game_data["dungeon"]
        map_data = dungeon_data["map"]

        # Use model_construct to bypass all validation
        dungeon_data = game_data["dungeon"]
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

        # Use model_construct to completely bypass validation
        dungeon = Dungeon.model_construct(
            max_chests=dungeon_data["max_chests"],
            enemies_num=dungeon_data["enemies_num"],
            map=dungeon_map,
            start_points_team_1=start_points_team_1,
            start_points_team_2=start_points_team_2,
            enemies=restored_enemies,
            chests=restored_chests,
            exits=[
                (
                    Point(x=e["x"], y=e["y"])
                    if isinstance(e, dict)
                    else Point(x=e[0], y=e[1])
                )
                for e in dungeon_data["exits"]
            ],
        )

        # Restore players list for game (use the players we already added to lobby)
        restored_players = list(lobby.players.values())

        # Reconstruct turn
        turn_data = game_data["turn"]
        turn = Turn(
            number=turn_data["number"],
            phase=turn_data["phase"],
            actor_ids_passed_turn=set(turn_data.get("actor_ids_passed_turn", [])),
        )
        turn.available_moves = [
            Point(x=m["x"], y=m["y"]) if isinstance(m, dict) else Point(x=m[0], y=m[1])
            for m in turn_data.get("available_moves", [])
        ]

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
        if turn_data.get("current_actor"):
            current_actor_data = turn_data["current_actor"]
            actor_id = current_actor_data["id"]

            # Find actor in players or enemies
            current_actor = None
            for player in restored_players:
                if str(player.id) == actor_id:
                    current_actor = player
                    break

            if not current_actor:
                for enemy in dungeon.enemies:
                    if str(enemy.id) == actor_id:
                        current_actor = enemy
                        break

            if current_actor:
                lobby.game.turn.current_actor = current_actor
            else:
                lobby.game.turn.current_actor = None

        # Add the restored lobby to the lobby manager
        lobby_manager.lobbies[str(lobby_id)] = lobby

        return DebugRestoreResponse(
            success=True,
            message=f"Game state restored successfully in new lobby '{lobby_name}'",
            lobby_id=str(lobby_id),
            timestamp=datetime.now().isoformat(),
        )

    except Exception as e:
        import traceback

        error_details = f"Failed to restore game state: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        raise HTTPException(status_code=500, detail=error_details)


# =========================
# WebSocket — игра
# =========================


@app.websocket("/ws/{lobby_id}/{player_id}")
async def websocket_endpoint(websocket: WebSocket, lobby_id: str, player_id: str):
    await websocket.accept()
    lobby = lobby_manager.get_lobby(lobby_id)
    if not lobby:
        # Сначала принимаем, чтобы иметь возможность отправить код закрытия
        await websocket.close(
            code=WSCloseCodes.LOBBY_NOT_FOUND, reason="Lobby not found"
        )
        return
    if player_id not in lobby.players:
        await websocket.close(
            code=WSCloseCodes.PLAYER_NOT_IN_LOBBY,
            reason="Player not connected to lobby",
        )
        return
    player = lobby.players[player_id]
    lobby.connect(player, websocket)
    # даже до первого сообщения игрока сразу даём ему состояние лобби и состояние игры
    print("BROADCASTING ON CONNECT")
    if not lobby.game:
        # Если игры нет, уведомляем всех, что зашел новый игрок + обновляем экран ожидания
        await lobby.broadcast_lobby_state()
    else:
        # Если игра уже идет (например, переподключение), шлем состояние игры
        await lobby.broadcast_game_state()
        await lobby.broadcast_game_event(
            GameEvent(message=f"Ход {lobby.game.turn.current_actor.name}"),
            receiver_player_ids=[player.id],
        )
    if lobby.game.ended:
        await lobby.broadcast_game_event(GameEvent(message="Игра закончилась"))
        await websocket.close(code=WSCloseCodes.GAME_ENDED, reason="Game ended")
        return
    try:
        while True:
            data = await websocket.receive_json()
            if not lobby.game:
                # Игра еще не началась, обрабатываем действия лобби (чат, готовность)
                print("await lobby.handle_lobby_action(player, data)")
                await lobby.handle_lobby_action(player, data)
                # Если нужно, уведомляем всех о новом игроке/готовности
                print("await lobby.broadcast_lobby_state()")
                await lobby.broadcast_lobby_state()
            else:
                game_action_state = GameActionState.model_validate(data)
                performed = await lobby.handle_game_action(
                    player, game_action_state.model_dump()
                )
                if performed:
                    await lobby.broadcast_game_state()
                    # проверить ход врагов, и если да - выполнить их ходы
                    if lobby.game.turn.phase == GamePhase.AI_ENEMY_PHASE:
                        while (
                            lobby.game.turn.phase != GamePhase.TEAM_1_PHASE
                            and not lobby.game.ended
                        ):
                            actor = lobby.game.turn.current_actor
                            ai = SimpleEnemyAI(actor, lobby.game)
                            while (
                                lobby.game.turn.current_actor == actor
                                and not lobby.game.ended
                            ):
                                action = ai.decide()
                                performed = await lobby.handle_game_action(
                                    actor, action.model_dump(mode="json")
                                )
                                if not performed:
                                    print(
                                        f"enemy action was not performed: {action.type}"
                                    )
                                await lobby.broadcast_game_state()
                            await lobby.broadcast_game_state()
                        # конец хода ИИ врагов, ход окружения игры
                        print("=== ХОД ОКРУЖЕНИЯ ===")
                    await lobby.broadcast_game_state()
                if lobby.game.ended:
                    print("GAME END")
                    await lobby.broadcast_game_event(
                        GameEvent(message="Игра закончилась")
                    )
                    break
            if lobby.game.ended:
                print("GAME END")
                await lobby.broadcast_game_event(GameEvent(message="Игра закончилась"))
                break
    except WebSocketDisconnect:
        lobby.disconnect(player)
