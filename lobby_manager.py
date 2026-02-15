from game_wrapper import Lobby
from models import PlayerDTO, LobbyDTO


class LobbyManager:
    def __init__(self):
        self.lobbies: dict[str, Lobby] = {}

    def create_lobby(self, players: list[PlayerDTO]) -> Lobby:
        lobby = Lobby(LobbyDTO(), players)
        self.lobbies[lobby.id] = lobby
        return lobby

    def get_lobby(self, lobby_id: str) -> Lobby:
        return self.lobbies[lobby_id]
