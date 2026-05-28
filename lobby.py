import asyncio
import copy
from uuid import uuid4, UUID
from fastapi import WebSocket

from dto.base import PlayerDTO
from dto.event import GameEvent
from dto.state import GameState, LobbyState, LobbyStatePayload
from src.constants import Accuracy
from src.entities.enemy import Enemy
from src.game import Game
from src.dungeon import Dungeon
from src.entities.player import Player
from src.entities.base import CharacterStats, Inventory, Weapon
from src.action import Action
from src.map import DungeonMap
from src.maps import default


class Lobby:
    def __init__(self, name: str, players_num: int, created_by_player_id: UUID):
        self.id = uuid4()
        self.name = name
        self.players_num = players_num
        self.created_by_player_id = str(created_by_player_id)
        self.players: dict[str, Player] = {}
        self.connections: dict[str, WebSocket] = {}

        self.lock = asyncio.Lock()
        self.game = None  # до момента старта игры нет

    async def connect_player(self, player: PlayerDTO) -> tuple[bool, str]:
        if str(player.id) in self.players:
            return False, "player already in lobby"
        if len(self.players) == self.players_num:
            print(f"Can't connect player {player}, lobby full")
            return False, "lobby full"
        self.players[str(player.id)] = Player(
            id=player.id,
            team=player.team,
            stats=CharacterStats(
                health=15,
                damage=5,
                speed=5,
                action_points=10,
                view_distance=5,
                accuracy=Accuracy.DEFAULT_PLAYER_STATS_ACCURACY,
            ),
            inventory=Inventory(
                weapons=[
                    Weapon(
                        type="melee",
                        name="Кортик",
                        damage=3,
                        cost_ap=5,
                        range=1,
                        accuracy=Accuracy.DEFAULT_PLAYER_MELEE_WEAPON_ACCURACY,
                    ),
                    Weapon(
                        type="ranged",
                        name="Пистолет",
                        damage=5,
                        cost_ap=8,
                        range=4,
                        accuracy=Accuracy.DEFAULT_PLAYER_RANGED_WEAPON_ACCURACY,
                    ),
                ]
            ),
        )
        await self.broadcast_lobby_state()
        return True, "player connected"

    async def start_game(self) -> tuple[bool, str]:
        if self.game is not None:
            return False, "Game already started"
        if len(self.players) != self.players_num:
            detail = (
                f"Can't start game, players: {len(self.players)} / {self.players_num}"
            )
            print(
                f"Can't start game, players: {len(self.players)} / {self.players_num}"
            )
            return False, detail
        # генерация
        # dungeon = Dungeon(
        #     max_chests=3,
        #     enemies_num=2,
        #     width=20,
        #     height=15,
        #     min_rooms=3,
        #     max_rooms=4,
        #     min_room_size=3,
        #     max_room_size=5,
        # )

        # готовые карты
        dungeon_map = DungeonMap(
            width=copy.deepcopy(default.map_2["width"]),
            height=copy.deepcopy(default.map_2["height"]),
            tiles=copy.deepcopy(default.map_2["tiles"]),
        )
        dungeon = Dungeon(max_chests=3, enemies_num=2, map=dungeon_map)
        self.game = Game(
            lobby=self, dungeon=dungeon, players=list(self.players.values())
        )
        await self.game.launch()
        return True, "Game started"

    def connect(self, player: PlayerDTO, websocket: WebSocket):
        self.connections[player.id] = websocket

    def disconnect(self, player: PlayerDTO):
        self.connections.pop(player.id, None)

    async def handle_lobby_action(self, player, action):
        print("[LOBBY handle lobby action]", player, action)

    async def broadcast_lobby_state(self):
        # Формируем структуру для лобби (до старта игры)
        if self.game:
            status = "game started"
        elif self.players_num == len(self.players):
            status = "Waiting for host to start the game..."
        else:
            status = "Waiting for all players to connect..."
        state = LobbyState(
            payload=LobbyStatePayload(
                status=status,
                players_num=self.players_num,
                connected_players=[str(p.id) for p in list(self.players.values())],
                created_by_player_id=self.created_by_player_id,
            )
        )
        for ws in list(self.connections.values()):
            try:
                await ws.send_json(state.model_dump())
            except Exception as e:
                print("broadcast_lobby_state exception", e)

    async def broadcast_game_event(self, event: GameEvent):
        "Отправка информационных сообщений - смерть игрока и т д"
        for ws in list(self.connections.values()):
            try:
                await ws.send_json(event.model_dump())
            except Exception as e:
                print("broadcast_game_event exception", e)

    async def handle_game_action(self, _actor: PlayerDTO, payload: dict) -> bool:
        async with self.lock:
            actors = {str(e.id): e for e in self.game.dungeon.enemies}
            actors.update(self.players)
            actor = actors[str(_actor.id)]
            action = Action(**payload)
            if isinstance(actor, Enemy):
                pass
            action_result = await self.game.perform_actor_action(actor, action)
            self.game.version += 1
            return action_result.performed

    def filter_available_moves(
        self, game_state: GameState, player_id: str
    ) -> GameState:
        game_state = game_state.model_copy(deep=True)
        if not game_state.turn.current_actor:
            # если нет текущего актора (значит это Enemy AI) - не отдаём доступные клетки
            game_state.turn.available_moves = []
            return game_state
        if game_state.turn.current_actor.id != player_id:
            game_state.turn.available_moves = []
        return game_state

    async def broadcast_game_state(self):
        try:
            state = GameState.model_validate(self.game.dump_state())
        except Exception as e:
            print(e)
        else:
            states_for_teams = {
                1: self.filter_visible_entities_for_team(state, 1),
                2: self.filter_visible_entities_for_team(state, 2),
            }
            for player_id, ws in self.connections.items():
                player = self.players[str(player_id)]
                _state = states_for_teams[player.team]
                _state = self.filter_available_moves(_state, str(player_id))
                try:
                    await ws.send_json(
                        {"type": "state_update", "payload": _state.model_dump()}
                    )
                except Exception as e:
                    print(f"Error sending to ws {ws}: {e}")

    def filter_visible_entities_for_team(
        self, game_state: GameState, team: int
    ) -> GameState:
        # исключаем те, которые больше view_distance по Евклиду и имеют препятствия
        game_state = game_state.model_copy(deep=True)
        team_players = [p for p in game_state.players if p.team == team]
        another_team_players = [p for p in game_state.players if p.team != team]
        visible_enemies = []
        visible_chests = []
        visible_players = [p for p in team_players]
        for enemy in game_state.dungeon.enemies:
            for player in team_players:
                if self.game.dungeon.map.can_see(player, enemy):
                    visible_enemies.append(enemy)
                    break
        for chest in game_state.dungeon.chests:
            for player in team_players:
                if self.game.dungeon.map.can_see(player, chest):
                    visible_chests.append(chest)
                    break
        for another_player in another_team_players:
            for player in team_players:
                if self.game.dungeon.map.can_see(player, another_player):
                    visible_players.append(another_player)
                    break
        game_state.players = visible_players
        game_state.dungeon.enemies = visible_enemies
        game_state.dungeon.chests = visible_chests
        return game_state
