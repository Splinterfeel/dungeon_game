from fastapi import FastAPI, status, WebSocket, WebSocketDisconnect
from uuid import UUID
from fastapi.middleware.cors import CORSMiddleware
from models import CreateLobbyRequest, PlayerDTO, LobbyDTO
from lobby_manager import LobbyManager
from src.ai.enemy import SimpleEnemyAI
from src.turn import GamePhase
from fastapi.staticfiles import StaticFiles

from ws_utils import WSCloseCodes


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # для дебага
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory="static"), name="static")
lobby_manager = LobbyManager()


@app.post("/lobbies")
def create_lobby(request: CreateLobbyRequest) -> dict[str, UUID]:
    game_lobby = lobby_manager.create_lobby(request.players)
    return {"lobby_id": game_lobby.id}


# =========================
# WebSocket — игра
# =========================


@app.websocket("/ws/{lobby_id}/{player_id}")
async def websocket_endpoint(websocket: WebSocket, lobby_id: str, player_id: str):
    lobby_dto = LobbyDTO(id=lobby_id)
    player = PlayerDTO(id=player_id)
    lobby = lobby_manager.get_lobby(lobby_dto.id)
    if not lobby:
            # Сначала принимаем, чтобы иметь возможность отправить код закрытия
            await websocket.accept()
            await websocket.close(code=WSCloseCodes.LOBBY_NOT_FOUND, reason="Lobby not found")
            return
    await websocket.accept()
    lobby.connect(player, websocket)

    # --- отправляем текущее состояние игры сразу после подключения ---
    if lobby.game:  # если игра уже создана
        await lobby.broadcast_state()

    try:
        while not lobby.game.ended:
            data = await websocket.receive_json()
            performed = await lobby.handle_action(player, data)
            if performed:
                await lobby.broadcast_state()
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
                            performed = await lobby.handle_action(
                                action.actor, action.model_dump(mode="json")
                            )
                            if not performed:
                                print(f"enemy action was not performed: {action.type}")
                            await lobby.broadcast_state()
                        await lobby.broadcast_state()
                await lobby.broadcast_state()
        print("GAME END")

    except WebSocketDisconnect:
        lobby.disconnect(player)
