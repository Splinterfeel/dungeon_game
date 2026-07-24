import asyncio
import copy
from uuid import uuid4

from dto.base import CreateLobbyRequest, PlayerDTO
from lobby_manager import LobbyManager
from src.action import Action, ActionType
from src.arena import Arena
from src.entities.base import Inventory
from src.entities.player import Player
from src.game import Game
from src.map import ArenaMap
from src.maps import default
from src.mech_presets import get_mech_preset_by_name
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
    return (
        Game(arena=Arena(enemies_num=enemies_num, map=arena_map), players=players),
        players,
    )


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
        assert game.turn.current_actor in game.arena.enemies

        await end_current_turn(game)
        assert game.turn.phase == GamePhase.PLAYER_PHASE
        assert game.turn.current_actor == players[0]

    asyncio.run(scenario())


def test_lobby_rejects_action_for_actor_owned_by_another_pilot():
    async def scenario():
        manager = LobbyManager()
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


def test_match_reward_is_granted_once_per_pilot_not_per_mech():
    async def scenario():
        manager = LobbyManager()
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

        assert manager.garages[str(owner_a)].metrics.matches_finished == 1
        assert manager.garages[str(owner_b)].metrics.matches_finished == 1
        assert len(lobby.players) == 4

    asyncio.run(scenario())
