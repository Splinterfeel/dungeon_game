from dto.base import CreateLobbyRequest, LobbyDTO
from src.lobby.lobby import Lobby
from src.garage_manager import GarageManager


class LobbyManager:
    def __init__(self, garage_manager: GarageManager):
        self.lobbies: dict[str, Lobby] = {}
        self.garage_manager = garage_manager

    def create_lobby(self, request: CreateLobbyRequest) -> Lobby:
        _name = request.name
        if not _name:
            _name = f"Lobby #{len(self.lobbies) + 1}"
        lobby = Lobby(
            name=_name,
            players_num=request.players_num,
            created_by_player_id=request.created_by_player_id,
            garage_manager=self.garage_manager,
            vs_bot=request.vs_bot,
        )
        self.lobbies[str(lobby.id)] = lobby
        return lobby

    def get_lobby(self, lobby_id: str) -> Lobby | None:
        return self.lobbies.get(lobby_id)

    def get_lobbies_list(self) -> list[LobbyDTO]:
        return [
            LobbyDTO(
                id=lobby.id,
                name=lobby.name,
                players_num=lobby.players_num,
                vs_bot=lobby.vs_bot,
                created_by_player_id=lobby.created_by_player_id,
                team_1_connected_players=len(
                    [p for p in lobby.participants.values() if p.team == 1]
                ),
                team_2_connected_players=len(
                    [p for p in lobby.participants.values() if p.team == 2]
                ),
                game_started=lobby.game is not None,
            )
            for lobby in self.lobbies.values()
        ]
