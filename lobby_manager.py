from dto.base import LobbyDTO
from game_wrapper import Lobby


class LobbyManager:
    def __init__(self):
        self.lobbies: dict[str, Lobby] = {}

    def create_lobby(self, players_num: int) -> Lobby:
        lobby = Lobby(LobbyDTO(), players_num=players_num)
        self.lobbies[lobby.id] = lobby
        return lobby

    def get_lobby(self, lobby_id: str) -> Lobby | None:
        return self.lobbies.get(lobby_id)
