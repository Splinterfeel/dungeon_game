import asyncio
from fastapi import WebSocket

from models import PlayerDTO, LobbyDTO
from src.entities.enemy import Enemy
from src.game import Game
from src.dungeon import Dungeon
from src.entities.player import Player
from src.entities.base import CharacterStats
from src.action import Action
from src.map import DungeonMap
from src.turn import GamePhase
from src.maps import for_1_team


class Lobby:
    def __init__(self, lobby_dto: LobbyDTO, players_num: int = 2):
        self.id = lobby_dto.id
        self.lobby = lobby_dto
        self.players_num = players_num
        self.std_character_stats = CharacterStats(
            health=8, damage=3, speed=5, action_points=10
        )
        self.players: list[Player] = {}
        self.connections: dict[str, WebSocket] = {}

        self.lock = asyncio.Lock()
        self.game = None  # до момента старта игры нет

    def connect_player(self, player: PlayerDTO) -> bool:
        if len(self.players) == self.players_num:
            print(f"Can't connect player {player}, lobby full")
            return False
        self.players[player.id] = Player(id=player.id, team=player.team, stats=self.std_character_stats)
        return True

    def start_game(self) -> tuple[bool, str]:
        if self.game is not None:
            return False, "Game already started"
        if len(self.players) != self.players_num:
            detail = f"Can't start game, players: {len(self.players)} / {self.players_num}"
            print(f"Can't start game, players: {len(self.players)} / {self.players_num}")
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
            width=for_1_team.map_1["width"],
            height=for_1_team.map_1["height"],
            tiles=for_1_team.map_1["tiles"],
        )
        dungeon = Dungeon(
            max_chests=3,
            enemies_num=2,
            map=dungeon_map
        )
        self.game = Game(dungeon=dungeon, players=list(self.players.values()))
        self.game.launch()
        return True, "Game started"

    def connect(self, player: PlayerDTO, websocket: WebSocket):
        self.connections[player.id] = websocket

    def disconnect(self, player: PlayerDTO):
        self.connections.pop(player.id, None)

    async def handle_action(self, _actor: PlayerDTO, payload: dict) -> bool:
        async with self.lock:
            if self.game.turn.phase == GamePhase.PLAYER_PHASE:
                actor = self.players[_actor.id]
            else:
                actor = next(e for e in self.game.dungeon.enemies if e.id == _actor.id)
            action = Action(**payload)
            if isinstance(actor, Enemy):
                pass
            action_result = self.game.perform_actor_action(actor, action)
            self.game.version += 1
            return action_result.performed

    async def broadcast_state(self):
        state = self.game.dump_state()
        for x in state["dungeon"]["map"]["tiles"]:
            print(x)
        for ws in self.connections.values():
            print("sending to ws", ws)
            await ws.send_json({"type": "state_update", "payload": state})
