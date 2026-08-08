from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from dto.action import GameActionState
from dto.event import GameEvent
from src.lobby.lobby import Lobby
from src.lobby.manager import LobbyManager
from src.ws_utils import WSCloseCodes


router = APIRouter()


@router.websocket("/ws/{lobby_id}/{player_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    lobby_id: str,
    player_id: str,
):
    await websocket.accept()
    lobby_manager: LobbyManager = websocket.app.state.lobby_manager
    lobby: Lobby = lobby_manager.get_lobby(lobby_id)
    if not lobby:
        await websocket.close(
            code=WSCloseCodes.LOBBY_NOT_FOUND, reason="Lobby not found"
        )
        return
    if player_id not in lobby.participants:
        await websocket.close(
            code=WSCloseCodes.PLAYER_NOT_IN_LOBBY,
            reason="Player not connected to lobby",
        )
        return

    lobby.connect(player_id, websocket)
    if not lobby.game:
        await lobby.broadcast_lobby_state()
    else:
        await lobby.broadcast_game_state()
        await lobby.broadcast_game_event(
            GameEvent(message=f"Ход {lobby.game.turn.current_actor.name}"),
            receiver_player_ids=[player_id],
        )

    try:
        while True:
            data = await websocket.receive_json()
            if not lobby.game:
                await lobby.handle_lobby_action(player_id, data)
                await lobby.broadcast_lobby_state()
            else:
                game_action_state = GameActionState.model_validate(data)
                performed = await lobby.handle_game_action(
                    player_id, game_action_state.model_dump()
                )
                if performed:
                    await lobby.broadcast_game_state()
                    await lobby.run_automated_turns()
                    await lobby.broadcast_game_state()
                await lobby.announce_game_end_once()
    except WebSocketDisconnect:
        lobby.disconnect(player_id)
