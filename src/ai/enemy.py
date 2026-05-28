import random
import time

from src.action import Action, ActionType, AttackActionParams
from src.ai.base import AI
from src.base import Point


class SimpleEnemyAI(AI):
    WAKE_DISTANCE: int = 10

    def __init__(self, actor, game):
        super().__init__(actor, game)
        self.tried_to_walk_on_turn = False
        self.attacked_on_turn = False

    def decide(self) -> Action:
        time.sleep(0.3)

        # сначала проверяем ranged-атаку (до движения, чтобы хватило AP)
        if not self.attacked_on_turn:
            ranged_weapon = next(
                (w for w in self.actor.inventory.weapons if w.type == "ranged"), None
            )
            if ranged_weapon:
                for player in self.game.players:
                    if self.game.dungeon.map.can_shoot(
                        self.actor, ranged_weapon, player.position
                    ):
                        if random.random() < 1 / 3:
                            print(f"         ENEMY {self.actor.name} - RANGED ATTACK")
                            self.attacked_on_turn = True
                            attack_params = AttackActionParams(weapon_id=ranged_weapon.id)
                            return Action(
                                actor_id=str(self.actor.id),
                                type=ActionType.ATTACK,
                                cell=player.position,
                                params=attack_params,
                            )

        # фаза движения
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
            if self.actor.stats.speed - self.actor.current_speed_spent > 0:
                nearest_player_data = min(players_distances, key=lambda _list: _list[0])
                distance, path = nearest_player_data
                if distance > self.WAKE_DISTANCE:
                    print(f"         ENEMY {self.actor.name} - SLEEP")
                elif len(path) < 1:
                    print(f"ENEMY AI - player {player} already near. no need to walk")
                else:
                    rev_path = path[::-1][:-1]
                    if not self.game.turn.available_moves:
                        print(" ===== no available moves!")
                    for step in rev_path:
                        if step in self.game.turn.available_moves:
                            print(f"         ENEMY {self.actor.name} - MOVING")
                            return Action(
                                actor_id=str(self.actor.id),
                                type=ActionType.MOVE,
                                cell=step,
                            )

        # после движения — melee-атака
        nearest_player_for_attack = None
        # если расстояние в 1 клетку (в т.ч. по диагонали) - надо атаковать
        for player in self.game.players:
            if Point.distance_chebyshev(player.position, self.actor.position) == 1:
                print("ENEMY AI - near player (1 cell), no need to move")
                nearest_player_for_attack = player
                break
        if nearest_player_for_attack and not self.attacked_on_turn:
            print(f"         ENEMY {self.actor.name} - ATTACKING")
            self.attacked_on_turn = True
            melee_weapon = next(
                w for w in self.actor.inventory.weapons if w.type == "melee"
            )
            attack_params = AttackActionParams(weapon_id=melee_weapon.id)
            return Action(
                actor_id=str(self.actor.id),
                type=ActionType.ATTACK,
                cell=nearest_player_for_attack.position,
                params=attack_params,
            )
        print(f"         ENEMY {self.actor.name} - ENDING TURN")
        return self.end_turn()
