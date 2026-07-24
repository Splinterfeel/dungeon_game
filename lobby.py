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
    PlayerState,
)
from src.ai.enemy import SimpleEnemyAI
from src.ai.player import PlayerBotAI
from src.entities.base import Actor, Inventory
from src.entities.enemy import Enemy
from src.game import Game
from src.arena import Arena
from src.entities.player import Player
from src.action import Action, ActionType
from src.map import ArenaMap
from src.maps import default
from src.mech_presets import get_random_mech_preset, get_mech_preset_by_name
from src.game_observer import GameObserver
from src.garage import GarageProfile, MATCH_XP_REWARDS, roll_match_reward
from src.turn import GamePhase


MAX_AUTOMATED_ACTIONS_PER_ACTOR = 20


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
        # Боевые акторы заполняются при старте матча. Ключ — actor id, а не
        # player_id подключённого пилота.
        self.players: dict[str, Player] = {}
        # Гаражи живут в LobbyManager и общие для всех лобби процесса.
        self.garages = garages
        self.bot_garages: dict[str, GarageProfile] = {}
        self.connections: dict[str, WebSocket] = {}

        self.lock = asyncio.Lock()
        self.automation_lock = asyncio.Lock()
        self.game = None  # до момента старта игры нет

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
                name="Бот",
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
                return False, "В одиночном режиме игрок должен выбрать команду 1"
            if any(
                not participant.is_bot for participant in self.participants.values()
            ):
                return False, "Одиночное лобби уже занято"
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
        # Всегда пересобираем весь отряд из гаража: HP и поломки прошлого
        # матча не являются прогрессом, а установленные детали — являются.
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
            return False, "Только хост лобби может начать рематч"
        if self.game is None or not self.game.ended:
            return False, "Рематч доступен только после завершения матча"
        result, detail = await self._start_fresh_game()
        if result:
            for participant in self.participants.values():
                if participant.is_bot:
                    continue
                self.garages[participant.player_id].metrics.rematches_started += 1
        return result, detail

    async def _start_fresh_game(self) -> tuple[bool, str]:
        # start_game проверяет game is not None, поэтому для рематча временно
        # освобождаем слот, сохранив завершённый матч только в событиях/метриках.
        self.game = None
        return await self.start_game()

    def connect(self, player_id: str, websocket: WebSocket):
        self.connections[player_id] = websocket

    def disconnect(self, player_id: str):
        self.connections.pop(player_id, None)

    async def handle_lobby_action(self, player, action):
        print("[LOBBY handle lobby action]", player, action)

    async def broadcast_lobby_state(self):
        # Формируем структуру для лобби (до старта игры)
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
        """Выполняет ходы PvP-ботов и нейтральных врагов до хода человека."""
        async with self.automation_lock:
            automated_actor_id = None
            ai = None
            actions_for_actor = 0

            while self.game and not self.game.ended:
                actor = self.game.turn.current_actor
                if isinstance(actor, Player):
                    participant = self.participants.get(str(actor.owner_player_id))
                    if participant is None or not participant.is_bot:
                        return
                    ai_class = PlayerBotAI
                elif (
                    isinstance(actor, Enemy)
                    and self.game.turn.phase == GamePhase.AI_ENEMY_PHASE
                ):
                    ai_class = SimpleEnemyAI
                else:
                    return

                actor_id = str(actor.id)
                if actor_id != automated_actor_id:
                    automated_actor_id = actor_id
                    ai = ai_class(actor, self.game)
                    actions_for_actor = 0

                if actions_for_actor >= MAX_AUTOMATED_ACTIONS_PER_ACTOR:
                    action = ai.end_turn()
                else:
                    action = ai.decide()
                actions_for_actor += 1

                performed = await self.handle_game_action(
                    actor, action.model_dump(mode="json")
                )
                await self.broadcast_game_state()
                if performed:
                    continue

                if action.type == ActionType.END_TURN:
                    return
                fallback = ai.end_turn()
                fallback_performed = await self.handle_game_action(
                    actor, fallback.model_dump(mode="json")
                )
                await self.broadcast_game_state()
                if not fallback_performed:
                    return

    async def finalize_match_rewards(self) -> None:
        """Начисляет награды ровно один раз, в том числе погибшим победителям."""
        if not self.game or self.game.rewards_granted:
            return
        self.game.rewards_granted = True
        for player_id, participant in self.participants.items():
            if participant.is_bot:
                continue
            garage = self.garages[player_id]
            is_winner = (
                self.game.winner is not None and participant.team == self.game.winner
            )
            garage.metrics.matches_finished += 1
            progression = garage.award_xp(
                MATCH_XP_REWARDS["winner" if is_winner else "loser"]
            )
            if progression.level_after > progression.level_before:
                await self.broadcast_game_event(
                    GameEvent(
                        message=(
                            f"Прогресс пилота {garage.name}: +{progression.xp_awarded} XP, "
                            f"уровень {progression.level_before} → {progression.level_after}. "
                            f"Новый выбор навыка доступен в гараже."
                        )
                    ),
                    receiver_player_ids=[player_id],
                )
            else:
                await self.broadcast_game_event(
                    GameEvent(
                        message=(
                            f"Прогресс пилота {garage.name}: +{progression.xp_awarded} XP "
                            f"(всего {garage.xp}), уровень {garage.level}."
                        )
                    ),
                    receiver_player_ids=[player_id],
                )
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

    def filter_available_moves(
        self, game_state: GameState, player_id: str
    ) -> GameState:
        game_state = game_state.model_copy(deep=True)
        if not game_state.turn.current_actor:
            # если нет текущего актора (значит это Enemy AI) - не отдаём доступные клетки
            game_state.turn.available_moves = []
            return game_state
        current_actor = game_state.turn.current_actor
        if (
            not isinstance(current_actor, PlayerState)
            or current_actor.owner_player_id != player_id
        ):
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
                participant = self.participants[player_id]
                _state = states_for_teams[participant.team]
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
        if (
            game_state.turn.current_actor is not None
            and game_state.turn.current_actor.team != team
            and all(
                player.id != game_state.turn.current_actor.id
                for player in visible_players
            )
        ):
            # Порядок хода не должен превращаться в радар: скрытый вражеский
            # мех не отдаём вместе с позицией, статами и оружием.
            game_state.turn.current_actor = None
            game_state.turn.available_moves = []
        return game_state
