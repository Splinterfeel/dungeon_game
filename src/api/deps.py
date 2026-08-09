from fastapi import Request

from src.garage_manager import GarageManager
from src.lobby.manager import LobbyManager


def get_lobby_manager(request: Request) -> LobbyManager:
    return request.app.state.lobby_manager


def get_garage_manager(request: Request) -> GarageManager:
    return request.app.state.garage_manager
