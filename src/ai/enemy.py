import time

from src.action import Action, ActionType
from src.ai.base import AI
from src.base import Point
from src.constants import Attack


class SimpleEnemyAI(AI):
    WAKE_DISTANCE: int = 10

    def __init__(self, actor, game):
        super().__init__(actor, game)
        self.tried_to_walk_on_turn = False
        self.attacked_on_turn = False

    def decide(self) -> Action:
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
            return self.end_turn()
        else:
            # если еще есть возможность двигаться
            if self.actor.stats.speed - self.actor.current_speed_spent > 0:
                nearest_player_data = min(players_distances, key=lambda _list: _list[0])
                distance, path = nearest_player_data
                if distance > self.WAKE_DISTANCE:
                    print(f"         ENEMY {self.actor.name} - SLEEP")
                elif len(path) < 1:
                    print(f"ENEMY AI - player {player} already near. no need to walk")
                else:
                    # пытаемся подойти ближе
                    # получаем путь в обратном направлении, отбрасываем последний элемент (наша позиция)
                    rev_path = path[::-1][:-1]
                    # идем настолько далеко от текущей позиции к игроку, насколько можем
                    if not self.game.turn.available_moves:
                        print(" ===== no available moves!")
                    for step in rev_path:
                        if step in self.game.turn.available_moves:
                            print(f"         ENEMY {self.actor.name} - MOVING")
                            return Action(
                                actor=self.actor, type=ActionType.MOVE, cell=step
                            )

        # после фазы движения смотрим можем ли атаковать
        nearest_player_for_attack = None
        # если расстояние в 1 клетку (в т.ч. по диагонали) - надо атаковать
        for player in self.game.players:
            if Point.distance_chebyshev(player.position, self.actor.position) == 1:
                print("ENEMY AI - near player (1 cell), no need to move")
                nearest_player_for_attack = player
                break
        if nearest_player_for_attack and not self.attacked_on_turn:
            print(f"         ENEMY {self.actor.name} - ATTACKING")
            # пытаемся атаковать (пока не проверяем action points)
            self.attacked_on_turn = True
            return Action(
                actor=self.actor,
                type=ActionType.ATTACK,
                cell=nearest_player_for_attack.position,
                params=Attack.SIMPLE.to_dict(),
            )
        print(f"         ENEMY {self.actor.name} - ENDING TURN")
        return self.end_turn()
