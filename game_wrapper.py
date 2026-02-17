import asyncio
from fastapi import WebSocket

from models import PlayerDTO, LobbyDTO
from src.game import Game
from src.dungeon import Dungeon
from src.entities.player import Player
from src.entities.base import CharacterStats
from src.action import Action
from src.turn import GamePhase


class Lobby:
    def __init__(self, lobby: LobbyDTO, players: list[PlayerDTO]):
        self.id = lobby.id
        self.lobby = lobby
        std_character_stats = CharacterStats(
            health=8, damage=3, speed=5, action_points=10
        )
        self.players = {
            p.id: Player(id=p.id, stats=std_character_stats) for p in players
        }
        self.connections: dict[str, WebSocket] = {}

        dungeon = Dungeon(
            width=20,
            height=20,
            min_rooms=3,
            max_rooms=4,
            min_room_size=4,
            max_room_size=5,
            max_chests=3,
            enemies_num=2,
        )
        self.game = Game(dungeon=dungeon, players=list(self.players.values()))
        self.game.launch()

        self.lock = asyncio.Lock()

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
            action_result = self.game.perform_actor_action(actor, action)
            if action_result.performed:
                await self.broadcast_state()
            else:
                print(action_result)
            return action_result.performed

    async def broadcast_state(self):
        state = self.game.dump_state()

        for ws in self.connections.values():
            await ws.send_json({"type": "state_update", "payload": state})
