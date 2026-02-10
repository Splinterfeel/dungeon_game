from src.action import Action
import time
import typing_extensions

from src.action import ActionType
from src.ai.base import AI
from src.base import Point, Queues
from src.entities.base import Actor

if typing_extensions.TYPE_CHECKING:
    from src.game import Game


class SimpleEnemyAI(AI):
    WAKE_DISTANCE: int = 10

    def perform_action(self, actor: Actor, game: "Game"):
        # TODO пока просто завершаем ход за противника
        time.sleep(2)
        Queues.COMMAND_QUEUE.put(
            Action(actor=actor, type=ActionType.END_TURN, cell=actor.position)
        )
        # если расстояние в 1 клетку (в т.ч. по диагонали) - надо атаковать
        for player in game.players:
            if Point.distance_chebyshev(player.position, actor.position) == 1:
                print("ENEMY AI - near player (1), attacking")
                return
        # строим путь до каждого игрока
        players_distances = []
        for player in game.players:
            # nearest_player = min(
            #     game.players,
            #     key=lambda p: Point.distance_euklid(enemy.position, p.position),
            # )
            # distance = Point.distance_euklid(nearest_player.position, enemy.position)
            # if distance > self.WAKE_DISTANCE:
            #     print("ENEMY AI - no near players")
            #     return
            path = game.dungeon.map.bfs_path(actor.position, player.position)
            if not path:
                continue
            players_distances.append(
                [
                    len(path),
                    path,
                ]
            )
        if not players_distances:
            print("ENEMY AI - can't find any player path")
            return

        nearest_player_data = min(players_distances, key=lambda _list: _list[0])
        distance = nearest_player_data[0]
        distance, path = nearest_player_data
        if distance > self.WAKE_DISTANCE:
            print("ENEMY AI - no near players")
            return
        if len(path) < 1:
            print(f"ENEMY AI - player {player} already near")
            return
        available_moves = game.dungeon.map.get_available_moves(actor)
        # path[1:] — пропускаем текущую позицию
        for step in path[1:]:
            if step in available_moves:
                actor.position = step  # делаем максимально возможный шаг по пути
            else:
                break  # дальше по пути нельзя идти, упираемся в препятствие
