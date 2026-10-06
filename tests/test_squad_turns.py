import asyncio
import copy
import random
from uuid import uuid4

from dto.base import CreateLobbyRequest, PlayerDTO
from dto.state import GameState
from src.garage_manager import GarageManager
from src.lobby.manager import LobbyManager
from src.action import Action, ActionType
from src.base import Point
from src.ai.player import PlayerBotAI
from src.arena import Arena
from src.constants import CELL_TYPE
from src.entities.base import Inventory
from src.entities.enemy import build_default_enemy
from src.entities.player import Player
from src.game import Game
from src.map import ArenaMap
from src.maps import default
from src.mech.presets import get_mech_preset_by_name
from src.turn import GamePhase


def make_player(team: int, preset_name: str, owner_id) -> Player:
    preset = get_mech_preset_by_name(preset_name)
    return Player(
        id=uuid4(),
        owner_player_id=owner_id,
        loadout_id=uuid4(),
        team=team,
        mech=preset.mech,
        stats=preset.mech.build_character_stats(action_points=10),
        inventory=Inventory(weapons=preset.weapons),
    )


def build_squad_game(enemies_num: int = 0) -> tuple[Game, list[Player]]:
    arena_map = ArenaMap(
        width=copy.deepcopy(default.map_2["width"]),
        height=copy.deepcopy(default.map_2["height"]),
        tiles=copy.deepcopy(default.map_2["tiles"]),
    )
    owner_a = uuid4()
    owner_b = uuid4()
    players = [
        make_player(1, "SteelMan", owner_a),
        make_player(1, "Fireworks Mk. 1", owner_a),
        make_player(2, "SteelMan", owner_b),
        make_player(2, "Fireworks Mk. 1", owner_b),
    ]
    arena = Arena(map=arena_map)
    enemies = []
    for spawn_point in arena.choose_enemy_spawn_points(enemies_num):
        enemy = build_default_enemy(9, 12)
        enemy.position = spawn_point
        enemies.append(enemy)
    return Game(arena=arena, players=players, enemies=enemies), players


def build_overwatch_kill_game() -> tuple[Game, list[Player]]:
    tiles = [[CELL_TYPE.WALL.value for _ in range(5)] for _ in range(8)]
    for x in range(1, 7):
        for y in range(1, 4):
            tiles[x][y] = CELL_TYPE.EMPTY.value

    start_team_1 = [Point(x=1, y=1), Point(x=1, y=3)]
    start_team_2 = [Point(x=6, y=1), Point(x=6, y=3)]
    for point in start_team_1:
        tiles[point.x][point.y] = CELL_TYPE.START_TEAM_1.value
    for point in start_team_2:
        tiles[point.x][point.y] = CELL_TYPE.START_TEAM_2.value

    arena_map = ArenaMap(width=8, height=5, tiles=tiles)
    owner_a = uuid4()
    owner_b = uuid4()
    players = [
        make_player(1, "Fireworks Mk. 1", owner_a),
        make_player(1, "SteelMan", owner_a),
        make_player(2, "SteelMan", owner_b),
        make_player(2, "Fireworks Mk. 1", owner_b),
    ]
    return Game(arena=Arena(map=arena_map), players=players, enemies=[]), players


async def end_current_turn(game: Game) -> None:
    actor = game.turn.current_actor
    result = await game.perform_actor_action(
        actor,
        Action(
            actor_id=str(actor.id),
            type=ActionType.END_TURN,
            cell=actor.position,
        ),
    )
    assert result.performed, result.detail


def test_squad_turn_order_is_stable_and_alternates_teams():
    async def scenario():
        game, players = build_squad_game()
        expected = [players[0], players[2], players[1], players[3]]

        await game.launch()
        observed = []
        for _ in range(4):
            observed.append(game.turn.current_actor)
            await end_current_turn(game)

        assert observed == expected
        assert game.turn.current_actor == players[0]
        assert game.turn.number == 2
        assert game.turn.phase == GamePhase.PLAYER_PHASE

    asyncio.run(scenario())


def test_dead_mech_is_skipped_without_reordering_remaining_slots():
    async def scenario():
        game, players = build_squad_game()
        players[2].stats.health = 0

        await game.launch()
        assert game.turn.current_actor == players[0]
        await end_current_turn(game)

        assert game.turn.current_actor == players[1]

    asyncio.run(scenario())


def test_neutral_ai_starts_only_after_all_living_player_mechs():
    async def scenario():
        game, players = build_squad_game(enemies_num=1)
        await game.launch()

        for expected in [players[0], players[2], players[1], players[3]]:
            assert game.turn.current_actor == expected
            await end_current_turn(game)

        assert game.turn.phase == GamePhase.AI_ENEMY_PHASE
        assert game.turn.current_actor in game.enemies

        await end_current_turn(game)
        assert game.turn.phase == GamePhase.PLAYER_PHASE
        assert game.turn.current_actor == players[0]

    asyncio.run(scenario())


def test_player_bot_actively_hunts_opposing_team():
    async def scenario():
        game, players = build_squad_game()
        await game.launch()
        bot_actor = players[2]
        await game.prepare_actor_turn(bot_actor)

        action = PlayerBotAI(bot_actor, game).decide()

        assert action.type in {ActionType.MOVE, ActionType.ATTACK}
        assert action.type != ActionType.END_TURN

    asyncio.run(scenario())


def test_solo_lobby_fills_team_two_and_runs_bot_turn():
    async def scenario():
        manager = LobbyManager(GarageManager())
        owner_id = uuid4()
        lobby = manager.create_lobby(
            CreateLobbyRequest(
                players_num=2,
                created_by_player_id=owner_id,
                vs_bot=True,
            )
        )
        connected, _ = await lobby.connect_player(
            PlayerDTO(
                id=owner_id,
                team=1,
                mech_presets=["SteelMan", "Fireworks Mk. 1"],
            )
        )
        assert connected

        started, detail = await lobby.start_game()
        assert started, detail
        bot_participants = [
            participant
            for participant in lobby.participants.values()
            if participant.is_bot
        ]
        assert len(bot_participants) == 1
        assert bot_participants[0].team == 2
        assert (
            await manager.garage_manager.find_profile(bot_participants[0].player_id)
            is None
        )
        assert len(lobby.players) == 4

        first_human_actor = lobby.game.turn.current_actor
        assert str(first_human_actor.owner_player_id) == str(owner_id)
        ended = Action(
            actor_id=str(first_human_actor.id),
            type=ActionType.END_TURN,
            cell=first_human_actor.position,
        )
        assert await lobby.handle_game_action(
            str(owner_id), ended.model_dump(mode="json")
        )

        bot_actor = lobby.game.turn.current_actor
        assert str(bot_actor.owner_player_id) == bot_participants[0].player_id
        await lobby.run_automated_turns()

        next_human_actor = lobby.game.turn.current_actor
        assert str(next_human_actor.owner_player_id) == str(owner_id)
        assert next_human_actor.id != first_human_actor.id

        lobby.game.ended = True
        lobby.game.winner = 1
        await lobby.finalize_match_rewards()
        assert (
            await manager.garage_manager.get_profile(str(owner_id))
        ).metrics.matches_finished == 1
        assert (
            await manager.garage_manager.find_profile(bot_participants[0].player_id)
            is None
        )

    asyncio.run(scenario())


def test_lobby_rejects_action_for_actor_owned_by_another_pilot():
    async def scenario():
        manager = LobbyManager(GarageManager())
        owner_id = uuid4()
        lobby = manager.create_lobby(
            CreateLobbyRequest(players_num=1, created_by_player_id=owner_id)
        )
        connected, _ = await lobby.connect_player(
            PlayerDTO(
                id=owner_id,
                team=1,
                mech_presets=["SteelMan", "Fireworks Mk. 1"],
            )
        )
        assert connected
        started, _ = await lobby.start_game()
        assert started

        actor = lobby.game.turn.current_actor
        payload = Action(
            actor_id=str(actor.id),
            type=ActionType.END_TURN,
            cell=actor.position,
        ).model_dump(mode="json")

        assert not await lobby.handle_game_action(str(uuid4()), payload)
        assert lobby.game.turn.current_actor == actor
        assert await lobby.handle_game_action(str(owner_id), payload)
        assert lobby.game.turn.current_actor != actor

    asyncio.run(scenario())


def test_match_ends_only_after_all_mechs_of_team_are_destroyed():
    game, players = build_squad_game()
    team_1 = [player for player in players if player.team == 1]

    game.players.remove(team_1[0])
    game.check_game_end()
    assert not game.ended

    game.players.remove(team_1[1])
    game.check_game_end()
    assert game.ended
    assert game.winner == 2
    assert GameState.model_validate(game.to_dict()).winner == 2


def test_match_reward_is_granted_once_per_pilot_not_per_mech():
    async def scenario():
        manager = LobbyManager(GarageManager())
        owner_a = uuid4()
        owner_b = uuid4()
        lobby = manager.create_lobby(
            CreateLobbyRequest(players_num=2, created_by_player_id=owner_a)
        )
        for owner_id, team in ((owner_a, 1), (owner_b, 2)):
            connected, _ = await lobby.connect_player(
                PlayerDTO(
                    id=owner_id,
                    team=team,
                    mech_presets=["SteelMan", "Fireworks Mk. 1"],
                )
            )
            assert connected

        started, _ = await lobby.start_game()
        assert started
        lobby.game.ended = True
        lobby.game.winner = 1

        await lobby.finalize_match_rewards()
        await lobby.finalize_match_rewards()

        assert (
            await manager.garage_manager.get_profile(str(owner_a))
        ).metrics.matches_finished == 1
        assert (
            await manager.garage_manager.get_profile(str(owner_b))
        ).metrics.matches_finished == 1
        assert len(lobby.players) == 4

    asyncio.run(scenario())


def test_move_into_overwatch_can_kill_actor_and_pass_turn_to_next_slot():
    async def scenario():
        game, players = build_overwatch_kill_game()
        watcher = players[0]
        next_teammate = players[1]
        moving_target = players[2]

        await game.launch()
        game.arena.map.clear_start_points(clear_players_points=True)
        watcher.position = Point(x=2, y=2)
        next_teammate.position = Point(x=1, y=1)
        moving_target.position = Point(x=5, y=2)
        players[3].position = Point(x=5, y=3)
        for player in players:
            game.arena.map.set(player.position, CELL_TYPE.PLAYER.value)

        ranged_weapon = watcher.inventory.weapons[0]
        ranged_weapon.accuracy = 100
        ranged_weapon.damage = 999
        watcher.skills = []
        moving_target.skills = []
        moving_target.stats.health = 1

        overwatch_result = await game.perform_actor_action(
            watcher,
            Action(
                actor_id=str(watcher.id),
                type=ActionType.OVERWATCH,
                cell=watcher.position,
                params={"weapon_id": str(ranged_weapon.id)},
            ),
        )
        assert overwatch_result.performed, overwatch_result.detail
        assert game.turn.current_actor == moving_target

        random.seed(1)
        move_result = await game.perform_actor_action(
            moving_target,
            Action(
                actor_id=str(moving_target.id),
                type=ActionType.MOVE,
                cell=Point(x=4, y=2),
            ),
        )

        assert move_result.performed, move_result.detail
        assert "огнев" in move_result.detail.lower()
        assert moving_target.is_dead()
        assert moving_target not in game.players
        assert watcher.overwatch is None
        assert game.turn.current_actor == next_teammate
        assert game.turn.phase == GamePhase.PLAYER_PHASE
        assert str(game.turn.current_actor.id) == str(next_teammate.id)

    asyncio.run(scenario())


def test_lobby_publishes_game_end_once_and_resets_for_rematch():
    async def scenario():
        manager = LobbyManager(GarageManager())
        owner_a = uuid4()
        owner_b = uuid4()
        lobby = manager.create_lobby(
            CreateLobbyRequest(players_num=2, created_by_player_id=owner_a)
        )
        for owner_id, team in ((owner_a, 1), (owner_b, 2)):
            connected, detail = await lobby.connect_player(
                PlayerDTO(
                    id=owner_id,
                    team=team,
                    mech_presets=["SteelMan", "Fireworks Mk. 1"],
                )
            )
            assert connected, detail

        started, detail = await lobby.start_game()
        assert started, detail

        messages = []

        async def collect_event(event, receiver_player_ids=None):
            messages.append(event.message)

        lobby.broadcast_game_event = collect_event
        lobby.game.ended = True
        lobby.game.winner = 2

        await lobby.publish_game_end_if_needed()
        await lobby.publish_game_end_if_needed()

        assert messages == ["Победила команда 2!", "Игра закончилась"]
        assert lobby.end_announced

        started, detail = await lobby.start_rematch(str(owner_a))
        assert started, detail
        assert not lobby.end_announced

    asyncio.run(scenario())
