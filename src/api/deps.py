from fastapi import Request

from src.lobby.manager import LobbyManager


def get_lobby_manager(request: Request) -> LobbyManager:
    return request.app.state.lobby_manager
