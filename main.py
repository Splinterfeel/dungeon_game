from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from uuid import UUID
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
from dto.garage import EquipGaragePartRequest, GarageState, RematchRequest
from dto.debug import (
    DebugDumpRequest,
    DebugDumpResponse,
    DebugRestoreRequest,
    DebugRestoreResponse,
)
from dto.state import MechPresetState

from src.mech_presets import MECH_PRESETS
from dto.event import GameEvent
from lobby_manager import LobbyManager
from src.ai.enemy import SimpleEnemyAI
from src.turn import GamePhase
from src.game import Game
from fastapi.staticfiles import StaticFiles

from ws_utils import WSCloseCodes
from game_state_utils import (
    create_debug_dump_response,
    restore_game_state as restore_game_state_util,
    create_restore_response,
)


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
    return templates.TemplateResponse(request, "debug_map.html", {"host": host})


@app.get("/lobbies", description="Получить список лобби")
def get_lobbies_list() -> list[LobbyDTO]:
    return lobby_manager.get_lobbies_list()


@app.get(
    "/mech_presets",
    description="Список доступных пресетов меха (для выбора при подключении к лобби)",
)
def get_mech_presets() -> list[MechPresetState]:
    return [
        MechPresetState.model_validate(preset.model_dump()) for preset in MECH_PRESETS
    ]


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


@app.get(
    "/debug/lobbies/{lobby_id}/garage/{player_id}",
    description="Состояние in-memory гаража пилота (debug only)",
)
def get_garage(lobby_id: str, player_id: str) -> GarageState:
    lobby = lobby_manager.get_lobby(lobby_id)
    if not lobby:
        raise HTTPException(status_code=404, detail="Lobby not found")
    try:
        return lobby.get_garage_state(player_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))


@app.post(
    "/debug/garage/equip",
    description="Установить деталь из гаража в сборку пилота (debug only)",
)
def equip_garage_part(request: EquipGaragePartRequest) -> GarageState:
    lobby = lobby_manager.get_lobby(request.lobby_id)
    if not lobby:
        raise HTTPException(status_code=404, detail="Lobby not found")
    try:
        return lobby.equip_garage_part(str(request.player_id), str(request.part_id))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@app.post("/rematch", description="Начать рематч тем же составом (debug only)")
async def start_rematch(request: RematchRequest) -> StartGameResponse:
    lobby = lobby_manager.get_lobby(request.lobby_id)
    if not lobby:
        raise HTTPException(status_code=404, detail="Lobby not found")
    result, detail = await lobby.start_rematch(str(request.host_player_id))
    if result:
        await lobby.broadcast_lobby_state()
        await lobby.broadcast_game_state()
    return StartGameResponse(lobby_id=request.lobby_id, result=result, detail=detail)


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
        game_state = lobby.game.to_dict()
        return create_debug_dump_response(lobby, game_state)
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
        game_data = request.game_state
        lobby_id = UUID(request.lobby_id)
        lobby_name = request.lobby_name or f"Restored Lobby {request.lobby_id[:8]}"

        # Restore game state using utility function
        lobby = restore_game_state_util(game_data, lobby_id, lobby_name)

        # Add the restored lobby to the lobby manager
        lobby_manager.lobbies[str(lobby_id)] = lobby

        return create_restore_response(lobby_id, lobby_name)

    except Exception as e:
        import traceback

        error_details = f"Failed to restore game state: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        raise HTTPException(status_code=500, detail=error_details)


# =========================
# WebSocket — игра
# =========================


def _winner_message(game: Game) -> str:
    if game.winner is None:
        return "Ничья: обе команды уничтожены"
    return f"Победила команда {game.winner}!"


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
                if lobby.game.ended and not lobby.game.end_announced:
                    print("GAME END")
                    await lobby.broadcast_game_event(
                        GameEvent(message=_winner_message(lobby.game))
                    )
                    await lobby.broadcast_game_event(
                        GameEvent(message="Игра закончилась")
                    )
                    lobby.game.end_announced = True
    except WebSocketDisconnect:
        lobby.disconnect(player)
