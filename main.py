from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from uuid import UUID
from fastapi.middleware.cors import CORSMiddleware
from dto.base import (
    ConnectLobbyRequest, CreateLobbyRequest, DetailedBoolResponse,
    LobbyDTO, PlayerDTO, StartGameRequest, StartGameResponse
)
from lobby_manager import LobbyManager
from src.ai.enemy import SimpleEnemyAI
from src.turn import GamePhase
from fastapi.staticfiles import StaticFiles

from ws_utils import WSCloseCodes


app = FastAPI(docs_url="/api/docs", redoc_url="/redoc")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # для дебага
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory="static"), name="static")
lobby_manager = LobbyManager()


@app.post("/lobbies", description="Создать лобби")
def create_lobby(request: CreateLobbyRequest) -> dict[str, UUID]:
    game_lobby = lobby_manager.create_lobby(request)
    return {"lobby_id": game_lobby.id}


@app.post("/connect_lobby", description="Присоединиться к лобби (игрок)")
async def connect_lobby(request: ConnectLobbyRequest) -> DetailedBoolResponse:
    game_lobby = lobby_manager.get_lobby(request.lobby_id)
    if not game_lobby:
        raise HTTPException(status_code=404, detail="Lobby not found")
    result, detail = await game_lobby.connect_player(request.player)
    return DetailedBoolResponse(result=result, detail=detail)


@app.post("/start_game", description="Стартовать игру")
async def start_game(request: StartGameRequest) -> StartGameResponse:
    # TODO проверка что стартует именно тот игрок который указан как создатель в лобби (host)
    lobby = lobby_manager.get_lobby(request.lobby_id)
    if not lobby:
        raise HTTPException(status_code=404, detail="Lobby not found")
    result, detail = lobby.start_game()
    await lobby.broadcast_lobby_state()
    await lobby.broadcast_game_state()
    return StartGameResponse(
        lobby_id=request.lobby_id,
        result=result,
        detail=detail,
    )

# =========================
# WebSocket — игра
# =========================


@app.websocket("/ws/{lobby_id}/{player_id}")
async def websocket_endpoint(websocket: WebSocket, lobby_id: str, player_id: str):
    await websocket.accept()
    lobby_dto = LobbyDTO(id=lobby_id)
    player = PlayerDTO(id=player_id)
    lobby = lobby_manager.get_lobby(lobby_dto.id)
    if not lobby:
        # Сначала принимаем, чтобы иметь возможность отправить код закрытия
        await websocket.close(code=WSCloseCodes.LOBBY_NOT_FOUND, reason="Lobby not found")
        return
    if player_id not in lobby.players:
        await websocket.close(code=WSCloseCodes.PLAYER_NOT_IN_LOBBY, reason="Player not connected to lobby")
        return
    lobby.connect(player, websocket)
    # даже до первого сообщения игрока сразу даём ему состояние лобби и состояние игры
    print("BROADCASTING ON CONNECT")
    if not lobby.game:
        print("broadcasting lobby state")
        # Если игры нет, уведомляем всех, что зашел новый игрок + обновляем экран ожидания
        await lobby.broadcast_lobby_state()
    else:
        print("broadcasting game state")
        # Если игра уже идет (например, переподключение), шлем состояние игры
        await lobby.broadcast_game_state()

    print("entering cycle")
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
                performed = await lobby.handle_game_action(player, data)
                if performed:
                    await lobby.broadcast_game_state()
                    # проверить ход врагов, и если да - выполнить их ходы
                    if lobby.game.turn.phase == GamePhase.ENEMY_PHASE:
                        while (
                            lobby.game.turn.phase != GamePhase.PLAYER_PHASE
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
                                    action.actor, action.model_dump(mode="json")
                                )
                                if not performed:
                                    print(f"enemy action was not performed: {action.type}")
                                await lobby.broadcast_game_state()
                            await lobby.broadcast_game_state()
                    await lobby.broadcast_game_state()
                if lobby.game.ended:
                    break
            if lobby.game.ended:
                print("GAME END")
                break
    except WebSocketDisconnect:
        lobby.disconnect(player)
