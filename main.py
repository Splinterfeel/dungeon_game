from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from uuid import UUID

from models import CreateLobbyRequest, PlayerDTO, LobbyDTO
from lobby_manager import LobbyManager
from src.turn import GamePhase


app = FastAPI()
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
    await websocket.accept()
    lobby_dto = LobbyDTO(id=lobby_id)
    player = PlayerDTO(id=player_id)
    lobby = lobby_manager.get_lobby(lobby_dto.id)
    lobby.connect(player, websocket)

    # --- отправляем текущее состояние игры сразу после подключения ---
    if lobby.game:  # если игра уже создана
        await lobby.broadcast_state()

    try:
        while True:
            data = await websocket.receive_json()
            performed = await lobby.handle_action(player, data)
            if performed:
                await lobby.broadcast_state()
                # проверить ход врагов, и если да - выполнить их ходы
                if lobby.game.turn.phase == GamePhase.ENEMY_PHASE:
                    print("NOW ENEMY PHASE")
                    while lobby.game.turn.phase != GamePhase.PLAYER_PHASE:
                        action = lobby.game.generate_enemy_action()
                        performed = await lobby.handle_action(action.actor, data)
                        if not performed:
                            raise ValueError(f"enemy action was not performed: {action}")
                        await lobby.broadcast_state()
                await lobby.broadcast_state()

    except WebSocketDisconnect:
        lobby.disconnect(player)
