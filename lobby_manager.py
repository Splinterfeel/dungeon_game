from dto.base import CreateLobbyRequest, LobbyDTO
from lobby import Lobby


class LobbyManager:
    def __init__(self):
        self.lobbies: dict[str, Lobby] = {}

    def create_lobby(self, request: CreateLobbyRequest) -> Lobby:
        _name = request.name
        if not _name:
            _name = f"Lobby #{len(self.lobbies) + 1}"
        lobby = Lobby(
            name=_name,
            players_num=request.players_num,
            created_by_player_id=request.created_by_player_id,
        )
        self.lobbies[str(lobby.id)] = lobby
        return lobby

    def get_lobby(self, lobby_id: str) -> Lobby | None:
        return self.lobbies.get(lobby_id)

    def get_lobbies_list(self) -> list[LobbyDTO]:
        return [
            LobbyDTO(
                id=l.id,
                name=l.name,
                players_num=l.players_num,
                created_by_player_id=l.created_by_player_id,
                team_1_connected_players=len([p for p in l.players.values() if p.team == 1]),
                team_2_connected_players=len([p for p in l.players.values() if p.team == 2]),
                game_started=l.game is not None,
            )
            for l in self.lobbies.values()
        ]
