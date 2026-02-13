import time

from src.action import Action, ActionType
from src.ai.base import AI
from src.base import Point, Queues
from src.constants import Attack


class SimpleEnemyAI(AI):
    WAKE_DISTANCE: int = 10

    def generate_action(self):
        time.sleep(1)
        players_distances = []
        for player in self.game.players:
            path = self.game.dungeon.map.bfs_path(self.actor.position, player.position)
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
        else:
            nearest_player_data = min(players_distances, key=lambda _list: _list[0])
            distance, path = nearest_player_data
            if distance > self.WAKE_DISTANCE:
                print("ENEMY AI - no near players")
            elif len(path) < 1:
                print(f"ENEMY AI - player {player} already near. no need to walk")
            else:
                # пытаемся подойти ближе
                available_moves = self.game.dungeon.map.get_available_moves(self.actor)
                # получаем путь в обратном направлении, отбрасываем последний элемент (наша позиция)
                rev_path = path[::-1][:-1]
                # идем настолько далеко от текущей позиции к игроку, насколько можем
                for step in rev_path:
                    if step in available_moves:
                        Queues.COMMAND_QUEUE.put(
                            Action(actor=self.actor, type=ActionType.MOVE, cell=step)
                        )
                        break

        # после фазы движения смотрим можем ли атаковать
        nearest_player_for_attack = None
        # если расстояние в 1 клетку (в т.ч. по диагонали) - надо атаковать
        for player in self.game.players:
            if Point.distance_chebyshev(player.position, self.actor.position) == 1:
                print("ENEMY AI - near player (1 cell), no need to move")
                nearest_player_for_attack = player
                break
        if nearest_player_for_attack:
            # пытаемся атаковать (пока не проверяем action points)
            Queues.COMMAND_QUEUE.put(
                Action(actor=self.actor, type=ActionType.ATTACK, cell=nearest_player_for_attack.position, params=Attack.SIMPLE.to_dict())
            )
        else:
            print("ENEMY AI - no players for attack")
        print("ENEMY AI - ENDING TURN")
        self.end_turn()

    def end_turn(self):
        Queues.COMMAND_QUEUE.put(
            Action(actor=self.actor, type=ActionType.END_TURN, cell=self.actor.position)
        )
