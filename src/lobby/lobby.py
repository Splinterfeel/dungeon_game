import asyncio
import copy
from dataclasses import dataclass, field
from uuid import uuid4, UUID
from fastapi import WebSocket
from typing import Optional, List

from dto.base import LobbyParticipantState, PlayerDTO
from dto.event import ActionResultEvent, GameEvent, LobbyClosedEvent
from dto.state import (
    GameState,
    LobbyState,
    LobbyStatePayload,
)
from src.lobby.automation import LobbyAutomation
from src.lobby.rewards import LobbyRewards
from src.lobby.state_view import LobbyStateView
from src.entities.base import Actor, Inventory
from src.entities.enemy import build_default_enemy
from src.game import Game
from src.arena import Arena
from src.entities.player import Player
from src.action import Action, ActionResult
from src.map import ArenaMap
from src.maps import default
from src.mech.presets import get_random_mech_preset
from src.game_observer import GameObserver
from src.garage_manager import GarageManager


@dataclass
class LobbyParticipant:
    player_id: str
    team: int
    name: str
    actor_ids: list[str] = field(default_factory=list)
    is_bot: bool = False


class Lobby(GameObserver):
    def __init__(
        self,
        name: str,
        players_num: int,
        created_by_player_id: UUID,
        garage_manager: GarageManager,
        vs_bot: bool = False,
    ):
        self.id = uuid4()
        self.name = name
        self.players_num = players_num
        self.vs_bot = vs_bot
        self.created_by_player_id = str(created_by_player_id)
        self.participants: dict[str, LobbyParticipant] = {}
        self.players: dict[str, Player] = {}
        self.garage_manager = garage_manager
        self.connections: dict[str, WebSocket] = {}

        self.lock = asyncio.Lock()
        self.automation_lock = asyncio.Lock()
        self.game = None
        self.end_announced = False

    async def on_game_event(
        self, event: GameEvent, receiver_player_ids: Optional[List[str]] = None
    ) -> None:
        """Observer interface implementation"""
        await self.broadcast_game_event(event, receiver_player_ids)

    async def on_state_change(self) -> None:
        """Observer interface implementation"""
        await self.broadcast_game_state()

    def _ready_to_start(self) -> bool:
        if not self.vs_bot:
            return len(self.participants) == self.players_num
        human_participants = [
            participant
            for participant in self.participants.values()
            if not participant.is_bot
        ]
        return (
            self.players_num == 2
            and len(human_participants) == 1
            and human_participants[0].team == 1
        )

    def _add_bot_participant(self) -> None:
        if any(participant.is_bot for participant in self.participants.values()):
            return

        bot_id = uuid4()
        bot_player_id = str(bot_id)
        self.participants[bot_player_id] = LobbyParticipant(
            player_id=bot_player_id,
            team=2,
            name="Бот",
            is_bot=True,
        )

    @staticmethod
    def _temporary_bot_players(bot_id: str, team: int) -> list[Player]:
        presets = [get_random_mech_preset(), get_random_mech_preset()]
        return [
            Player(
                id=bot_id,
                team=team,
                name="Бот",
                mech=preset.mech.model_copy(deep=True),
                stats=preset.mech.build_character_stats(action_points=10),
                inventory=Inventory(
                    weapons=[weapon.model_copy(deep=True) for weapon in preset.weapons]
                ),
            )
            for preset in presets
        ]

    async def connect_player(self, player: PlayerDTO) -> tuple[bool, str]:
        player_id = str(player.id)
        if player_id in self.participants:
            return False, "player already in lobby"
        if self.vs_bot:
            if player.team != 1:
                return (
                    False,
                    "Можно присоединиться только к 1 команде",
                )
            if any(
                not participant.is_bot for participant in self.participants.values()
            ):
                return False, "Нет ботов"
        if len(self.participants) == self.players_num:
            print(f"Can't connect player {player}, lobby full")
            return False, "lobby full"
        garage = await self.garage_manager.find_profile(player_id)
        if garage is None:
            try:
                garage = await self.garage_manager.create_starting_profile(
                    player_id=player.id,
                    mech_presets=player.mech_presets,
                )
            except ValueError as error:
                return False, str(error)
        self.participants[player_id] = LobbyParticipant(
            player_id=player_id,
            team=player.team,
            name=garage.name,
        )
        await self.broadcast_lobby_state()
        return True, "player connected"

    async def leave_player(self, player_id: str) -> tuple[bool, str, bool]:
        """Удаляет участника до старта и сообщает, ушёл ли хост."""
        if self.game is not None:
            return False, "Нельзя выйти из лобби после старта матча", False
        participant = self.participants.pop(player_id, None)
        if participant is None:
            return False, "Пилот не состоит в лобби", False
        self.disconnect(player_id)
        return True, "Пилот вышел из лобби", player_id == self.created_by_player_id

    async def start_game(self) -> tuple[bool, str]:
        if self.game is not None:
            return False, "Game already started"
        if not self._ready_to_start():
            detail = (
                f"Can't start game, players: "
                f"{len(self.participants)} / {self.players_num}"
            )
            print(
                f"Can't start game, players: "
                f"{len(self.participants)} / {self.players_num}"
            )
            return False, detail
        if self.vs_bot:
            self._add_bot_participant()
        arena_map = ArenaMap(
            width=copy.deepcopy(default.map_2["width"]),
            height=copy.deepcopy(default.map_2["height"]),
            tiles=copy.deepcopy(default.map_2["tiles"]),
        )
        arena = Arena(map=arena_map)
        enemies = []
        for spawn_point in arena.choose_enemy_spawn_points(2):
            enemy = build_default_enemy(
                min_action_points=9,
                max_action_points=12,
            )
            enemy.position = spawn_point
            enemies.append(enemy)
        self.players = {}
        for participant in self.participants.values():
            participant.actor_ids = []
            if participant.is_bot:
                starting_players = self._temporary_bot_players(
                    participant.player_id, participant.team
                )
                actors = await self.garage_manager.build_temporary_players(
                    starting_players, participant.team
                )
            else:
                actors = await self.garage_manager.build_players(
                    participant.player_id, participant.team
                )
            for actor in actors:
                actor_id = str(actor.id)
                participant.actor_ids.append(actor_id)
                self.players[actor_id] = actor
        self.game = Game(
            arena=arena,
            players=list(self.players.values()),
            enemies=enemies,
        )
        self.end_announced = False
        self.game.set_observer(self)  # Register as observer
        await self.game.launch()
        return True, "Game started"

    async def start_rematch(self, host_player_id: str) -> tuple[bool, str]:
        if host_player_id != self.created_by_player_id:
            return (
                False,
                "Рестартовать может только хост",
            )
        if self.game is None or not self.game.ended:
            return (
                False,
                "Игра еще не закончена или не создана",
            )
        result, detail = await self._start_fresh_game()
        if result:
            for participant in self.participants.values():
                if participant.is_bot:
                    continue
                await self.garage_manager.record_rematch(participant.player_id)
        return result, detail

    async def _start_fresh_game(self) -> tuple[bool, str]:
        self.game = None
        return await self.start_game()

    def connect(self, player_id: str, websocket: WebSocket):
        self.connections[player_id] = websocket

    def disconnect(self, player_id: str):
        self.connections.pop(player_id, None)

    async def broadcast_lobby_state(self):
        if self.game:
            status = "game started"
        elif self._ready_to_start():
            status = "Waiting for host to start the game..."
        else:
            status = "Waiting for all players to connect..."
        state = LobbyState(
            payload=LobbyStatePayload(
                status=status,
                players_num=self.players_num,
                connected_players=list(self.participants),
                created_by_player_id=self.created_by_player_id,
                vs_bot=self.vs_bot,
                participants=[
                    LobbyParticipantState(
                        player_id=participant.player_id,
                        name=participant.name,
                        team=participant.team,
                        is_bot=participant.is_bot,
                    )
                    for participant in self.participants.values()
                ],
            )
        )
        for ws in list(self.connections.values()):
            try:
                await ws.send_json(state.model_dump())
            except Exception as e:
                print("broadcast_lobby_state exception", e)

    async def broadcast_lobby_closed(self) -> None:
        event = LobbyClosedEvent(message="Хост закрыл лобби до старта матча")
        for ws in list(self.connections.values()):
            try:
                await ws.send_json(event.model_dump())
            except Exception as error:
                print("broadcast_lobby_closed exception", error)

    async def broadcast_action_result(
        self, player_id: str, result: ActionResult
    ) -> None:
        websocket = self.connections.get(player_id)
        if websocket is None:
            return
        event = ActionResultEvent(
            action_id=str(result.action.id),
            performed=result.performed,
            detail=result.detail,
        )
        try:
            await websocket.send_json(event.model_dump())
        except Exception as error:
            print("broadcast_action_result exception", error)

    async def broadcast_game_event(
        self, event: GameEvent, receiver_player_ids: list[str] = None
    ):
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

    def _winner_message(self) -> str:
        if self.game is None or self.game.winner is None:
            return "Ничья: обе команды уничтожены"
        return f"Победила команда {self.game.winner}!"

    async def publish_game_end_if_needed(self) -> None:
        if self.game is None or not self.game.ended or self.end_announced:
            return

        print("GAME END")
        await self.broadcast_game_event(GameEvent(message=self._winner_message()))
        await self.broadcast_game_event(GameEvent(message="Игра закончилась"))
        self.end_announced = True

    async def handle_game_action_result(
        self, requester: str | Actor, payload: dict
    ) -> ActionResult:
        action = Action(**payload)
        async with self.lock:
            if not self.game:
                return ActionResult(
                    action=action, performed=False, detail="Матч ещё не начат"
                )
            if self.game.ended:
                return ActionResult(
                    action=action, performed=False, detail="Матч уже завершён"
                )
            actors = {str(enemy.id): enemy for enemy in self.game.enemies}
            actors.update(self.players)
            actor = actors.get(action.actor_id)
            if actor is None:
                return ActionResult(
                    action=action, performed=False, detail="Указанный мех не найден"
                )
            if isinstance(requester, str):
                if not isinstance(actor, Player):
                    return ActionResult(
                        action=action,
                        performed=False,
                        detail="Игрок не может управлять нейтральным врагом",
                    )
                if str(actor.owner_player_id) != requester:
                    return ActionResult(
                        action=action,
                        performed=False,
                        detail="Этот мех принадлежит другому пилоту",
                    )
            elif actor is not requester:
                return ActionResult(
                    action=action,
                    performed=False,
                    detail="ИИ отправил действие не от имени текущего актора",
                )
            action_result = await self.game.perform_actor_action(actor, action)
            self.game.version += 1
            if self.game.ended:
                await self.finalize_match_rewards()
            return action_result

    async def handle_game_action(self, requester: str | Actor, payload: dict) -> bool:
        result = await self.handle_game_action_result(requester, payload)
        return result.performed

    async def run_automated_turns(self) -> None:
        await LobbyAutomation(self).run_automated_turns()

    async def publish_started_game(self) -> None:
        await self.broadcast_lobby_state()
        await self.broadcast_game_state()
        await self.run_automated_turns()
        await self.broadcast_game_state()
        await self.publish_game_end_if_needed()

    async def publish_after_game_action(self, performed: bool) -> None:
        if not performed:
            return
        await self.broadcast_game_state()
        await self.run_automated_turns()
        await self.broadcast_game_state()
        await self.publish_game_end_if_needed()

    async def finalize_match_rewards(self) -> None:
        await LobbyRewards(self).finalize_match_rewards()

    def filter_available_moves(
        self, game_state: GameState, player_id: str
    ) -> GameState:
        return LobbyStateView(self.game).filter_available_moves(game_state, player_id)

    async def broadcast_game_state(self):
        try:
            state = GameState.model_validate(self.game.dump_state())
        except Exception as e:
            print(e)
        else:
            state_view = LobbyStateView(self.game)
            states_for_teams = state_view.build_states_for_teams(state)
            for player_id, ws in self.connections.items():
                participant = self.participants[player_id]
                _state = states_for_teams[participant.team]
                _state = state_view.filter_available_moves(_state, str(player_id))
                try:
                    await ws.send_json(
                        {"type": "state_update", "payload": _state.model_dump()}
                    )
                except Exception as e:
                    print(f"Error sending to ws {ws}: {e}")

    def filter_visible_entities_for_team(
        self, game_state: GameState, team: int
    ) -> GameState:
        return LobbyStateView(self.game).filter_visible_entities_for_team(
            game_state, team
        )
