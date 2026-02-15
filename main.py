from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from uuid import UUID

from models import CreateLobbyRequest, PlayerDTO, LobbyDTO
from lobby_manager import LobbyManager


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

    try:
        while True:
            data = await websocket.receive_json()
            await lobby.handle_action(player, data)

    except WebSocketDisconnect:
        lobby.disconnect(player)
