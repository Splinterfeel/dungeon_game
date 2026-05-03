from dto.base import CreateLobbyRequest, LobbyDTO
from lobby import Lobby


class LobbyManager:
    def __init__(self):
        self.lobbies: dict[str, Lobby] = {}

    def create_lobby(self, request: CreateLobbyRequest) -> Lobby:
        lobby = Lobby(LobbyDTO(), players_num=request.players_num, created_by_player_id=request.created_by_player_id)
        self.lobbies[lobby.id] = lobby
        return lobby

    def get_lobby(self, lobby_id: str) -> Lobby | None:
        return self.lobbies.get(lobby_id)
