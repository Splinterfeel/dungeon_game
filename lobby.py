import asyncio
import copy
from uuid import uuid4, UUID
from fastapi import WebSocket
from typing import Optional, List

from dto.base import PlayerDTO
from dto.event import GameEvent
from dto.state import GameState, LobbyState, LobbyStatePayload, PartState
from dto.garage import GarageState, GarageMetricsState
from src.entities.enemy import Enemy
from src.game import Game
from src.arena import Arena
from src.entities.player import Player
from src.entities.base import Inventory
from src.action import Action
from src.map import ArenaMap
from src.maps import default
from src.mech_presets import get_random_mech_preset, get_mech_preset_by_name
from src.game_observer import GameObserver
from src.garage import GarageProfile, MATCH_REWARD_CHANCES, roll_match_reward


class Lobby(GameObserver):
    def __init__(self, name: str, players_num: int, created_by_player_id: UUID):
        self.id = uuid4()
        self.name = name
        self.players_num = players_num
        self.created_by_player_id = str(created_by_player_id)
        self.players: dict[str, Player] = {}
        # Постоянное только в пределах процесса состояние петли лута. Player
        # ниже — боевой экземпляр текущего матча, профиль — гараж пилота.
        self.garages: dict[str, GarageProfile] = {}
        self.connections: dict[str, WebSocket] = {}

        self.lock = asyncio.Lock()
        self.game = None  # до момента старта игры нет

    async def on_game_event(
        self, event: GameEvent, receiver_player_ids: Optional[List[str]] = None
    ) -> None:
        """Observer interface implementation"""
        await self.broadcast_game_event(event, receiver_player_ids)

    async def on_state_change(self) -> None:
        """Observer interface implementation"""
        await self.broadcast_game_state()

    async def connect_player(self, player: PlayerDTO) -> tuple[bool, str]:
        if str(player.id) in self.players:
            return False, "player already in lobby"
        if len(self.players) == self.players_num:
            print(f"Can't connect player {player}, lobby full")
            return False, "lobby full"
        if player.mech_preset:
            preset = get_mech_preset_by_name(player.mech_preset)
            if preset is None:
                return False, f"unknown mech preset: {player.mech_preset}"
        else:
            preset = get_random_mech_preset()
        mech = preset.mech
        game_player = Player(
            id=player.id,
            team=player.team,
            mech=mech,
            stats=mech.build_character_stats(action_points=10),
            inventory=Inventory(weapons=preset.weapons),
        )
        self.players[str(player.id)] = game_player
        self.garages[str(player.id)] = GarageProfile.from_player(game_player)
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
        # arena = Arena(
        #     enemies_num=2,
        #     width=20,
        #     height=15,
        #     min_rooms=3,
        #     max_rooms=4,
        #     min_room_size=3,
        #     max_room_size=5,
        # )

        # готовые карты
        arena_map = ArenaMap(
            width=copy.deepcopy(default.map_2["width"]),
            height=copy.deepcopy(default.map_2["height"]),
            tiles=copy.deepcopy(default.map_2["tiles"]),
        )
        arena = Arena(enemies_num=2, map=arena_map)
        # Всегда пересобираем бой из гаража: HP и поломки прошлого матча не
        # являются прогрессом, а установленная деталь — является.
        self.players = {
            player_id: garage.build_player()
            for player_id, garage in self.garages.items()
        }
        self.game = Game(arena=arena, players=list(self.players.values()))
        self.game.set_observer(self)  # Register as observer
        await self.game.launch()
        return True, "Game started"

    async def start_rematch(self, host_player_id: str) -> tuple[bool, str]:
        if host_player_id != self.created_by_player_id:
            return False, "Только хост лобби может начать рематч"
        if self.game is None or not self.game.ended:
            return False, "Рематч доступен только после завершения матча"
        result, detail = await self._start_fresh_game()
        if result:
            for garage in self.garages.values():
                garage.metrics.rematches_started += 1
        return result, detail

    async def _start_fresh_game(self) -> tuple[bool, str]:
        # start_game проверяет game is not None, поэтому для рематча временно
        # освобождаем слот, сохранив завершённый матч только в событиях/метриках.
        self.game = None
        return await self.start_game()

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

    async def broadcast_game_event(
        self, event: GameEvent, receiver_player_ids: list[str] = None
    ):
        "Отправка информационных сообщений - смерть игрока и т д"
        _receivers = self.connections
        if receiver_player_ids:
            _receivers = {
                k: ws for k, ws in self.connections.items() if k in receiver_player_ids
            }
        for ws in _receivers.values():
            try:
                await ws.send_json(event.model_dump())
            except Exception as e:
                print("broadcast_game_event exception", e)

    async def handle_game_action(self, _actor: PlayerDTO, payload: dict) -> bool:
        async with self.lock:
            if not self.game or self.game.ended:
                return False
            actors = {str(e.id): e for e in self.game.arena.enemies}
            actors.update(self.players)
            actor = actors[str(_actor.id)]
            action = Action(**payload)
            if isinstance(actor, Enemy):
                pass
            action_result = await self.game.perform_actor_action(actor, action)
            self.game.version += 1
            if self.game.ended:
                await self.finalize_match_rewards()
            return action_result.performed

    async def finalize_match_rewards(self) -> None:
        """Начисляет награды ровно один раз, в том числе погибшим победителям."""
        if not self.game or self.game.rewards_granted:
            return
        self.game.rewards_granted = True
        for player_id, garage in self.garages.items():
            is_winner = self.game.winner is not None and garage.team == self.game.winner
            garage.metrics.matches_finished += 1
            reward = roll_match_reward(garage, is_winner)
            if reward.awarded_part is None:
                chance_percent = round(reward.chance * 100)
                await self.broadcast_game_event(
                    GameEvent(
                        message=(
                            f"Награда: ролл {chance_percent}% для {garage.name} — "
                            f"деталь не выпала. {reward.reason}."
                        )
                    ),
                    receiver_player_ids=[player_id],
                )
                continue
            part_state = PartState.model_validate(
                reward.awarded_part.model_dump(mode="json")
            )
            await self.broadcast_game_event(
                GameEvent(
                    message=(
                        f"Награда: {garage.name} получает {part_state.rarity} "
                        f"деталь «{part_state.name}»!"
                    ),
                    loot_part=part_state,
                )
            )

    def get_garage_state(self, player_id: str) -> GarageState:
        garage = self.garages.get(player_id)
        if garage is None:
            raise ValueError("Пилот не найден в лобби")
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
            raise ValueError("Пилот не найден в лобби")
        garage.equip(part_id)
        return self.get_garage_state(player_id)

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
        visible_players = [p for p in team_players]
        for enemy in game_state.arena.enemies:
            for player in team_players:
                if self.game.arena.map.can_see(player, enemy):
                    visible_enemies.append(enemy)
                    break
        for another_player in another_team_players:
            for player in team_players:
                if self.game.arena.map.can_see(player, another_player):
                    visible_players.append(another_player)
                    break
        game_state.players = visible_players
        game_state.arena.enemies = visible_enemies
        return game_state
