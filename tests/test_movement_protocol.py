import asyncio
import random
from uuid import uuid4

from src.action import Action, ActionType
from src.ai.player import PlayerBotAI
from src.arena import Arena
from src.base import Point
from src.constants import CELL_TYPE
from src.entities.base import Inventory, OverwatchState
from src.entities.enemy import build_default_enemy
from src.entities.player import Player
from src.game import Game
from src.lobby.lobby import Lobby, LobbyParticipant
from src.map import ArenaMap
from src.mech.presets import get_mech_preset_by_name


class MovementObserver:
    def __init__(self):
        self.movements = []
        self.state_changes = 0

    async def on_game_event(self, event, receiver_player_ids=None):
        pass

    async def on_state_change(self):
        self.state_changes += 1

    async def on_actor_moved(self, movements):
        self.movements.append(movements)

    async def on_actor_attacked(self, attacks):
        pass


class RecordingSocket:
    def __init__(self):
        self.messages = []

    async def send_json(self, message):
        self.messages.append(message)


def make_player(team, x, y):
    preset = get_mech_preset_by_name("Fireworks Mk. 1")
    actor = Player(
        id=uuid4(),
        owner_player_id=uuid4(),
        loadout_id=uuid4(),
        team=team,
        name="Проверка маршрута",
        position=Point(x=x, y=y),
        mech=preset.mech,
        stats=preset.mech.build_character_stats(action_points=20),
        inventory=Inventory(weapons=preset.weapons),
        skills=[],
    )
    actor.stats.speed = 10
    return actor


def make_game(players, enemies=None):
    tiles = [[CELL_TYPE.WALL.value for _ in range(8)] for _ in range(12)]
    for x in range(1, 11):
        for y in range(1, 7):
            tiles[x][y] = CELL_TYPE.EMPTY.value
    tiles[1][6] = CELL_TYPE.START_TEAM_1.value
    tiles[10][6] = CELL_TYPE.START_TEAM_2.value
    arena = Arena(map=ArenaMap(width=12, height=8, tiles=tiles))
    arena.map.clear_start_points()
    game = Game(arena=arena, players=players, enemies=enemies or [])
    for actor in players:
        arena.map.set(actor.position, CELL_TYPE.PLAYER.value)
    return game


def move_action(actor, x, y=1):
    return Action(actor_id=str(actor.id), type=ActionType.MOVE, cell=Point(x=x, y=y))


def coordinates(paths):
    return [[(cell.x, cell.y) for cell in path] for path in paths]


def make_lobby(game):
    lobby = Lobby("Публикация маршрута", 2, uuid4(), garage_manager=None)
    lobby.game = game
    game.set_observer(lobby)
    lobby.players = {str(actor.id): actor for actor in game.players}
    for actor in game.players:
        owner = str(actor.owner_player_id)
        lobby.participants[owner] = LobbyParticipant(owner, actor.team, actor.name)
        lobby.connections[owner] = RecordingSocket()
    return lobby


def test_move_publishes_one_actual_route_without_step_snapshots():
    async def scenario():
        mover = make_player(1, 1, 1)
        opponent = make_player(2, 9, 6)
        opponent.stats.view_distance = 1
        game = make_game([mover, opponent])
        observer = MovementObserver()
        game.set_observer(observer)
        await game.prepare_actor_turn(mover)
        initial_ap = mover.current_action_points
        action = move_action(mover, 5)

        result = await game.perform_actor_action(mover, action)

        assert result.performed
        assert result.action_cost == result.speed_spent == 4
        assert mover.current_action_points == initial_ap - 4
        assert mover.current_speed_spent == 4
        assert mover.position == action.cell
        assert game.version == 0
        assert observer.state_changes == 0
        assert len(observer.movements) == 1
        assert set(observer.movements[0]) == {1}
        movement = observer.movements[0][1]
        assert movement.action_id == action.id
        assert movement.actor.position == Point(x=1, y=1)
        assert coordinates(movement.paths) == [[(x, 1) for x in range(1, 6)]]

    asyncio.run(scenario())


def test_lethal_overwatch_truncates_route_and_charges_only_traversed_cells():
    async def scenario():
        mover = make_player(1, 1, 1)
        mover.stats.view_distance = 2
        watcher = make_player(2, 3, 3)
        hidden_enemy = build_default_enemy(10, 10)
        hidden_enemy.position = Point(x=5, y=3)
        game = make_game([mover, watcher], enemies=[hidden_enemy])
        observer = MovementObserver()
        game.set_observer(observer)
        await game.prepare_actor_turn(mover)
        initial_ap = mover.current_action_points
        mover.stats.health = 10
        weapon = watcher.inventory.weapons[0]
        weapon.range = 2
        weapon.accuracy = 100
        weapon.damage = 9990
        watcher.stats.accuracy = 100
        watcher.stats.view_distance = 20
        watcher.overwatch = OverwatchState(weapon_id=weapon.id)
        action = move_action(mover, 5)
        random.seed(1)

        result = await game.perform_actor_action(mover, action)

        assert result.performed
        assert mover.is_dead()
        assert mover not in game.players
        assert mover.position == Point(x=3, y=1)
        assert result.action_cost == result.speed_spent == 2
        assert mover.current_action_points == initial_ap - 2
        assert mover.current_speed_spent == 2
        assert game.turn.current_actor == watcher
        assert game.ended and game.winner == 2
        assert observer.state_changes == 0
        assert len(observer.movements) == 1
        movement = observer.movements[0][1]
        assert movement.actor.stats.health == 10
        assert coordinates(movement.paths) == [[(1, 1), (2, 1), (3, 1)]]
        # Увидели стрелка на смертельной клетке, но не врага за непройденным путём.
        assert [sighting.id for sighting in movement.sightings] == [watcher.id]

    asyncio.run(scenario())


def test_transient_stationary_enemy_is_preserved_without_revealing_hidden_actors():
    async def scenario():
        mover = make_player(1, 1, 1)
        mover.stats.view_distance = 2
        opponent = make_player(2, 10, 6)
        opponent.stats.view_distance = 1
        transient_enemy = build_default_enemy(10, 10)
        transient_enemy.position = Point(x=5, y=3)
        hidden_enemy = build_default_enemy(10, 10)
        hidden_enemy.position = Point(x=5, y=6)
        game = make_game([mover, opponent], enemies=[transient_enemy, hidden_enemy])
        lobby = Lobby("Краткая видимость", 2, uuid4(), garage_manager=None)
        lobby.game = game
        game.set_observer(lobby)
        owner = str(mover.owner_player_id)
        lobby.participants[owner] = LobbyParticipant(owner, 1, "Свой")
        socket = RecordingSocket()
        lobby.connections[owner] = socket
        await game.prepare_actor_turn(mover)
        socket.messages.clear()
        assert not game.arena.map.can_see(mover, transient_enemy)

        result = await game.perform_actor_action(mover, move_action(mover, 10))
        await lobby.broadcast_game_state()

        assert result.performed
        assert not game.arena.map.can_see(mover, transient_enemy)
        route = next(
            message for message in socket.messages if message["type"] == "actor_moved"
        )
        assert len(route["sightings"]) == 1
        assert route["sightings"][0]["id"] == str(transient_enemy.id)
        assert route["sightings"][0]["position"] == {"x": 5, "y": 3}
        final_state = socket.messages[-1]
        assert final_state["type"] == "state_update"
        assert final_state["payload"]["enemies"] == []

    asyncio.run(scenario())


def test_team_routes_split_hidden_gaps_and_reach_dead_pilot_spectators():
    async def scenario():
        mover = make_player(1, 1, 1)
        observers = [make_player(2, 2, 3), make_player(2, 8, 3)]
        for observer in observers:
            observer.stats.view_distance = 3
        game = make_game([mover, *observers])
        lobby = Lobby("Маршруты", 2, uuid4(), garage_manager=None)
        lobby.game = game
        game.set_observer(lobby)
        owner = str(mover.owner_player_id)
        spectator = str(uuid4())
        hidden_team = str(uuid4())
        lobby.participants = {
            owner: LobbyParticipant(owner, 1, "Свой"),
            spectator: LobbyParticipant(spectator, 2, "Без живых мехов"),
            hidden_team: LobbyParticipant(hidden_team, 3, "Другая команда"),
        }
        lobby.connections = {
            player_id: RecordingSocket() for player_id in lobby.participants
        }
        await game.prepare_actor_turn(mover)
        for socket in lobby.connections.values():
            socket.messages.clear()
        action = move_action(mover, 10)

        result = await game.perform_actor_action(mover, action)

        assert result.performed
        own_messages = lobby.connections[owner].messages
        visible_messages = lobby.connections[spectator].messages
        own = [message for message in own_messages if message["type"] == "actor_moved"]
        visible = [
            message for message in visible_messages if message["type"] == "actor_moved"
        ]
        assert len(own) == len(visible) == 1
        assert own[0]["action_id"] == visible[0]["action_id"] == str(action.id)
        assert own[0]["actor"]["team"] == 1
        assert own[0]["actor"]["owner_player_id"] == owner
        assert own[0]["paths"] == [[{"x": x, "y": 1} for x in range(1, 11)]]
        assert visible[0]["paths"] == [
            [{"x": x, "y": 1} for x in range(1, 5)],
            [{"x": x, "y": 1} for x in range(6, 11)],
        ]
        assert visible[0]["actor"]["position"] == {"x": 1, "y": 1}
        assert not any(message["type"] == "state_update" for message in own_messages)
        assert not any(
            message["type"] == "actor_moved"
            for message in lobby.connections[hidden_team].messages
        )

    asyncio.run(scenario())


def test_first_visible_actor_metadata_survives_hidden_final_position():
    async def scenario():
        mover = make_player(1, 1, 1)
        watcher = make_player(2, 5, 3)
        watcher.stats.view_distance = 2
        game = make_game([mover, watcher])
        observer = MovementObserver()
        game.set_observer(observer)
        await game.prepare_actor_turn(mover)

        result = await game.perform_actor_action(mover, move_action(mover, 10))

        assert result.performed
        movement = observer.movements[0][2]
        assert movement.actor.position == Point(x=5, y=1)
        assert coordinates(movement.paths) == [[(5, 1)]]
        assert not game.arena.map.can_see(watcher, mover)

    asyncio.run(scenario())


def test_neutral_actor_uses_the_same_filtered_route_protocol():
    async def scenario():
        allies = [make_player(1, 3, 3), make_player(2, 9, 6)]
        allies[0].stats.view_distance = 3
        allies[1].stats.view_distance = 1
        enemy = build_default_enemy(10, 10)
        enemy.position = Point(x=1, y=1)
        enemy.stats.speed = 10
        game = make_game(allies, enemies=[enemy])
        observer = MovementObserver()
        game.set_observer(observer)
        await game.prepare_actor_turn(enemy)

        result = await game.perform_actor_action(enemy, move_action(enemy, 5))

        assert result.performed
        assert set(observer.movements[0]) == {1}
        assert coordinates(observer.movements[0][1].paths) == [
            [(x, 1) for x in range(1, 6)]
        ]

    asyncio.run(scenario())


def test_rejected_move_does_not_publish_route_or_change_costs():
    async def scenario():
        mover = make_player(1, 1, 1)
        game = make_game([mover, make_player(2, 9, 6)])
        observer = MovementObserver()
        game.set_observer(observer)
        await game.prepare_actor_turn(mover)
        initial_ap = mover.current_action_points

        result = await game.perform_actor_action(mover, move_action(mover, 0))

        assert not result.performed
        assert not observer.movements
        assert observer.state_changes == 0
        assert mover.current_action_points == initial_ap
        assert mover.current_speed_spent == 0
        assert mover.position == Point(x=1, y=1)

    asyncio.run(scenario())


def test_reconnect_snapshot_waits_for_action_lock():
    async def scenario():
        mover = make_player(1, 1, 1)
        lobby = Lobby("Reconnect", 2, uuid4(), garage_manager=None)
        lobby.game = make_game([mover, make_player(2, 9, 6)])
        owner = str(mover.owner_player_id)
        lobby.participants[owner] = LobbyParticipant(owner, 1, "Свой")
        socket = RecordingSocket()
        lobby.connections[owner] = socket
        await lobby.game.prepare_actor_turn(mover)

        async with lobby.lock:
            snapshot_task = asyncio.create_task(lobby.broadcast_game_state())
            await asyncio.sleep(0)
            assert not snapshot_task.done()
            assert not socket.messages
            lobby.game.move_actor(mover, Point(x=4, y=1))

        await snapshot_task
        assert len(socket.messages) == 1
        assert socket.messages[0]["type"] == "state_update"
        actor = socket.messages[0]["payload"]["players"][0]
        assert actor["position"] == {"x": 4, "y": 1}

    asyncio.run(scenario())


def test_human_move_publication_sends_one_route_one_result_and_one_final_snapshot():
    async def scenario():
        mover = make_player(1, 1, 1)
        lobby = make_lobby(make_game([mover, make_player(2, 9, 6)]))
        await lobby.game.prepare_actor_turn(mover)
        owner = str(mover.owner_player_id)
        socket = lobby.connections[owner]
        socket.messages.clear()
        action = move_action(mover, 5)

        result = await lobby.handle_game_action_result(
            owner, action.model_dump(mode="json")
        )
        await lobby.broadcast_action_result(owner, result)
        await lobby.publish_after_game_action(result.performed)

        message_types = [message["type"] for message in socket.messages]
        assert message_types.count("actor_moved") == 1
        assert message_types.count("action_result") == 1
        assert message_types.count("state_update") == 1
        assert message_types.index("actor_moved") < message_types.index("state_update")
        assert socket.messages[-1]["payload"]["version"] == 1
        actor = socket.messages[-1]["payload"]["players"][0]
        assert actor["position"] == {"x": 5, "y": 1}
        assert actor["current_action_points"] == 16

    asyncio.run(scenario())


def test_match_start_publishes_initial_snapshot_once_without_automated_actor():
    async def scenario():
        mover = make_player(1, 1, 1)
        lobby = make_lobby(make_game([mover, make_player(2, 9, 6)]))
        await lobby.game.prepare_actor_turn(mover)
        socket = lobby.connections[str(mover.owner_player_id)]
        socket.messages.clear()

        await lobby.publish_started_game()

        assert [message["type"] for message in socket.messages] == [
            "lobby_state",
            "state_update",
        ]

    asyncio.run(scenario())


def test_automation_publishes_its_final_snapshot_without_duplicate(monkeypatch):
    monkeypatch.setattr(PlayerBotAI, "decide", lambda self: self.end_turn())

    async def scenario():
        mover = make_player(1, 1, 1)
        bot = make_player(2, 9, 6)
        lobby = make_lobby(make_game([mover, bot]))
        lobby.participants[str(bot.owner_player_id)].is_bot = True
        await lobby.game.prepare_actor_turn(mover)
        lobby.game.turn.player_order_index = 0
        owner = str(mover.owner_player_id)
        socket = lobby.connections[owner]
        socket.messages.clear()
        action = Action(
            actor_id=str(mover.id), type=ActionType.END_TURN, cell=mover.position
        )

        result = await lobby.handle_game_action_result(
            owner, action.model_dump(mode="json")
        )
        await lobby.publish_after_game_action(result.performed)

        snapshots = [
            message for message in socket.messages if message["type"] == "state_update"
        ]
        assert len(snapshots) == 2
        assert [snapshot["payload"]["version"] for snapshot in snapshots] == [1, 2]
        assert snapshots[-1]["payload"]["turn"]["current_actor"]["id"] == str(mover.id)
        assert lobby.game.turn.current_actor == mover

    asyncio.run(scenario())
