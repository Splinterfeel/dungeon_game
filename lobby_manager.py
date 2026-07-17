from dto.base import CreateLobbyRequest, LobbyDTO
from dto.garage import GarageMetricsState, GarageState
from lobby import Lobby
from src.garage import GarageProfile, MATCH_REWARD_CHANCES


class LobbyManager:
    def __init__(self):
        self.lobbies: dict[str, Lobby] = {}
        # Профиль гаража принадлежит пилоту, а не конкретному лобби. Пока
        # сервер работает без БД, это единственное in-memory хранилище.
        self.garages: dict[str, GarageProfile] = {}

    def create_lobby(self, request: CreateLobbyRequest) -> Lobby:
        _name = request.name
        if not _name:
            _name = f"Lobby #{len(self.lobbies) + 1}"
        lobby = Lobby(
            name=_name,
            players_num=request.players_num,
            created_by_player_id=request.created_by_player_id,
            garages=self.garages,
        )
        self.lobbies[str(lobby.id)] = lobby
        return lobby

    def get_lobby(self, lobby_id: str) -> Lobby | None:
        return self.lobbies.get(lobby_id)

    def get_garage_state(self, player_id: str) -> GarageState:
        garage = self.garages.get(player_id)
        if garage is None:
            raise ValueError(
                "Гараж пилота ещё не создан: сначала подключитесь через debug-карту"
            )
        player = garage.build_player()
        equipped_ids = set(garage.equipped_part_ids.values())
        return GarageState(
            player_id=player_id,
            mech=player.mech.model_dump(mode="json"),
            stats=player.stats.model_dump(),
            weapons=[
                weapon.model_dump(mode="json") for weapon in player.inventory.weapons
            ],
            stored_parts=[
                part.model_dump(mode="json")
                for part in garage.owned_parts
                if part.id not in equipped_ids
            ],
            reward_chances=MATCH_REWARD_CHANCES,
            metrics=GarageMetricsState.model_validate(garage.metrics.model_dump()),
        )

    def equip_garage_part(self, player_id: str, part_id: str) -> GarageState:
        garage = self.garages.get(player_id)
        if garage is None:
            raise ValueError(
                "Гараж пилота ещё не создан: сначала подключитесь через debug-карту"
            )
        garage.equip(part_id)
        return self.get_garage_state(player_id)

    def get_lobbies_list(self) -> list[LobbyDTO]:
        return [
            LobbyDTO(
                id=l.id,
                name=l.name,
                players_num=l.players_num,
                created_by_player_id=l.created_by_player_id,
                team_1_connected_players=len(
                    [p for p in l.players.values() if p.team == 1]
                ),
                team_2_connected_players=len(
                    [p for p in l.players.values() if p.team == 2]
                ),
                game_started=l.game is not None,
            )
            for l in self.lobbies.values()
        ]
