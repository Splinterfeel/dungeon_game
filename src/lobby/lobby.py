import asyncio
import copy
from dataclasses import dataclass, field
from uuid import uuid4, UUID
from fastapi import WebSocket
from typing import Optional, List

from dto.base import PlayerDTO
from dto.event import GameEvent
from dto.state import (
    GameState,
    LobbyState,
    LobbyStatePayload,
    PartState,
)
from src.lobby.automation import LobbyAutomation
from src.lobby.rewards import LobbyRewards
from src.lobby.state_view import LobbyStateView
from src.entities.base import Actor, Inventory
from src.game import Game
from src.arena import Arena
from src.entities.player import Player
from src.action import Action
from src.map import ArenaMap
from src.maps import default
from src.mech_presets import get_random_mech_preset, get_mech_preset_by_name
from src.game_observer import GameObserver
from src.garage import GarageProfile



@dataclass
class LobbyParticipant:
    player_id: str
    team: int
    actor_ids: list[str] = field(default_factory=list)
    is_bot: bool = False


class Lobby(GameObserver):
    def __init__(
        self,
        name: str,
        players_num: int,
        created_by_player_id: UUID,
        garages: dict[str, GarageProfile],
        vs_bot: bool = False,
    ):
        self.id = uuid4()
        self.name = name
        self.players_num = players_num
        self.vs_bot = vs_bot
        self.created_by_player_id = str(created_by_player_id)
        self.participants: dict[str, LobbyParticipant] = {}
        # Р‘РѕРµРІС‹Рµ Р°РєС‚РѕСЂС‹ Р·Р°РїРѕР»РЅСЏСЋС‚СЃСЏ РїСЂРё СЃС‚Р°СЂС‚Рµ РјР°С‚С‡Р°. РљР»СЋС‡ вЂ” actor id, Р° РЅРµ
        # player_id РїРѕРґРєР»СЋС‡С‘РЅРЅРѕРіРѕ РїРёР»РѕС‚Р°.
        self.players: dict[str, Player] = {}
        # Р“Р°СЂР°Р¶Рё Р¶РёРІСѓС‚ РІ LobbyManager Рё РѕР±С‰РёРµ РґР»СЏ РІСЃРµС… Р»РѕР±Р±Рё РїСЂРѕС†РµСЃСЃР°.
        self.garages = garages
        self.bot_garages: dict[str, GarageProfile] = {}
        self.connections: dict[str, WebSocket] = {}

        self.lock = asyncio.Lock()
        self.automation_lock = asyncio.Lock()
        self.game = None  # РґРѕ РјРѕРјРµРЅС‚Р° СЃС‚Р°СЂС‚Р° РёРіСЂС‹ РЅРµС‚

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
        presets = [get_random_mech_preset(), get_random_mech_preset()]
        starting_players = [
            Player(
                id=bot_id,
                team=2,
                name="Р‘РѕС‚",
                mech=preset.mech.model_copy(deep=True),
                stats=preset.mech.build_character_stats(action_points=10),
                inventory=Inventory(
                    weapons=[weapon.model_copy(deep=True) for weapon in preset.weapons]
                ),
            )
            for preset in presets
        ]
        bot_player_id = str(bot_id)
        self.bot_garages[bot_player_id] = GarageProfile.from_players(starting_players)
        self.participants[bot_player_id] = LobbyParticipant(
            player_id=bot_player_id,
            team=2,
            is_bot=True,
        )

    def _garage_for(self, participant: LobbyParticipant) -> GarageProfile:
        garages = self.bot_garages if participant.is_bot else self.garages
        return garages[participant.player_id]

    async def connect_player(self, player: PlayerDTO) -> tuple[bool, str]:
        player_id = str(player.id)
        if player_id in self.participants:
            return False, "player already in lobby"
        if self.vs_bot:
            if player.team != 1:
                return False, "Р’ РѕРґРёРЅРѕС‡РЅРѕРј СЂРµР¶РёРјРµ РёРіСЂРѕРє РґРѕР»Р¶РµРЅ РІС‹Р±СЂР°С‚СЊ РєРѕРјР°РЅРґСѓ 1"
            if any(
                not participant.is_bot for participant in self.participants.values()
            ):
                return False, "РћРґРёРЅРѕС‡РЅРѕРµ Р»РѕР±Р±Рё СѓР¶Рµ Р·Р°РЅСЏС‚Рѕ"
        if len(self.participants) == self.players_num:
            print(f"Can't connect player {player}, lobby full")
            return False, "lobby full"
        garage = self.garages.get(player_id)
        if garage is None:
            presets = []
            for preset_name in player.mech_presets:
                if preset_name:
                    preset = get_mech_preset_by_name(preset_name)
                    if preset is None:
                        return False, f"unknown mech preset: {preset_name}"
                else:
                    preset = get_random_mech_preset()
                presets.append(preset)

            starting_players = [
                Player(
                    id=player.id,
                    team=player.team,
                    mech=preset.mech,
                    stats=preset.mech.build_character_stats(action_points=10),
                    inventory=Inventory(weapons=preset.weapons),
                )
                for preset in presets
            ]
            garage = GarageProfile.from_players(starting_players)
            self.garages[player_id] = garage
        self.participants[player_id] = LobbyParticipant(
            player_id=player_id,
            team=player.team,
        )
        await self.broadcast_lobby_state()
        return True, "player connected"

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
        # РіРµРЅРµСЂР°С†РёСЏ
        # arena = Arena(
        #     enemies_num=2,
        #     width=20,
        #     height=15,
        #     min_rooms=3,
        #     max_rooms=4,
        #     min_room_size=3,
        #     max_room_size=5,
        # )

        # РіРѕС‚РѕРІС‹Рµ РєР°СЂС‚С‹
        arena_map = ArenaMap(
            width=copy.deepcopy(default.map_2["width"]),
            height=copy.deepcopy(default.map_2["height"]),
            tiles=copy.deepcopy(default.map_2["tiles"]),
        )
        arena = Arena(enemies_num=2, map=arena_map)
        # Р’СЃРµРіРґР° РїРµСЂРµСЃРѕР±РёСЂР°РµРј РІРµСЃСЊ РѕС‚СЂСЏРґ РёР· РіР°СЂР°Р¶Р°: HP Рё РїРѕР»РѕРјРєРё РїСЂРѕС€Р»РѕРіРѕ
        # РјР°С‚С‡Р° РЅРµ СЏРІР»СЏСЋС‚СЃСЏ РїСЂРѕРіСЂРµСЃСЃРѕРј, Р° СѓСЃС‚Р°РЅРѕРІР»РµРЅРЅС‹Рµ РґРµС‚Р°Р»Рё вЂ” СЏРІР»СЏСЋС‚СЃСЏ.
        self.players = {}
        for participant in self.participants.values():
            participant.actor_ids = []
            garage = self._garage_for(participant)
            for loadout in garage.loadouts:
                actor = garage.build_player(
                    team=participant.team,
                    loadout_id=loadout.id,
                    actor_id=uuid4(),
                )
                actor_id = str(actor.id)
                participant.actor_ids.append(actor_id)
                self.players[actor_id] = actor
        self.game = Game(arena=arena, players=list(self.players.values()))
        self.game.set_observer(self)  # Register as observer
        await self.game.launch()
        return True, "Game started"

    async def start_rematch(self, host_player_id: str) -> tuple[bool, str]:
        if host_player_id != self.created_by_player_id:
            return False, "РўРѕР»СЊРєРѕ С…РѕСЃС‚ Р»РѕР±Р±Рё РјРѕР¶РµС‚ РЅР°С‡Р°С‚СЊ СЂРµРјР°С‚С‡"
        if self.game is None or not self.game.ended:
            return False, "Р РµРјР°С‚С‡ РґРѕСЃС‚СѓРїРµРЅ С‚РѕР»СЊРєРѕ РїРѕСЃР»Рµ Р·Р°РІРµСЂС€РµРЅРёСЏ РјР°С‚С‡Р°"
        result, detail = await self._start_fresh_game()
        if result:
            for participant in self.participants.values():
                if participant.is_bot:
                    continue
                self.garages[participant.player_id].metrics.rematches_started += 1
        return result, detail

    async def _start_fresh_game(self) -> tuple[bool, str]:
        # start_game РїСЂРѕРІРµСЂСЏРµС‚ game is not None, РїРѕСЌС‚РѕРјСѓ РґР»СЏ СЂРµРјР°С‚С‡Р° РІСЂРµРјРµРЅРЅРѕ
        # РѕСЃРІРѕР±РѕР¶РґР°РµРј СЃР»РѕС‚, СЃРѕС…СЂР°РЅРёРІ Р·Р°РІРµСЂС€С‘РЅРЅС‹Р№ РјР°С‚С‡ С‚РѕР»СЊРєРѕ РІ СЃРѕР±С‹С‚РёСЏС…/РјРµС‚СЂРёРєР°С….
        self.game = None
        return await self.start_game()

    def connect(self, player_id: str, websocket: WebSocket):
        self.connections[player_id] = websocket

    def disconnect(self, player_id: str):
        self.connections.pop(player_id, None)

    async def handle_lobby_action(self, player, action):
        print("[LOBBY handle lobby action]", player, action)

    async def broadcast_lobby_state(self):
        # Р¤РѕСЂРјРёСЂСѓРµРј СЃС‚СЂСѓРєС‚СѓСЂСѓ РґР»СЏ Р»РѕР±Р±Рё (РґРѕ СЃС‚Р°СЂС‚Р° РёРіСЂС‹)
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
        "РћС‚РїСЂР°РІРєР° РёРЅС„РѕСЂРјР°С†РёРѕРЅРЅС‹С… СЃРѕРѕР±С‰РµРЅРёР№ - СЃРјРµСЂС‚СЊ РёРіСЂРѕРєР° Рё С‚ Рґ"
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

    async def handle_game_action(self, requester: str | Actor, payload: dict) -> bool:
        async with self.lock:
            if not self.game or self.game.ended:
                return False
            action = Action(**payload)
            actors = {str(e.id): e for e in self.game.arena.enemies}
            actors.update(self.players)
            actor = actors.get(action.actor_id)
            if actor is None:
                return False
            if isinstance(requester, str):
                if not isinstance(actor, Player):
                    return False
                if str(actor.owner_player_id) != requester:
                    return False
            elif actor is not requester:
                return False
            action_result = await self.game.perform_actor_action(actor, action)
            self.game.version += 1
            if self.game.ended:
                await self.finalize_match_rewards()
            return action_result.performed

    async def run_automated_turns(self) -> None:
        await LobbyAutomation(self).run_automated_turns()

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
