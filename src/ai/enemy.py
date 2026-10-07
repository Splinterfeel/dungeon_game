import random
import time

from src.action import Action, ActionType, AttackActionParams, OverwatchActionParams
from src.ai.base import AI
from src.base import Point
from src.entities.base import WeaponType


class SimpleEnemyAI(AI):
    WAKE_DISTANCE: int = 10

    def __init__(self, actor, game):
        super().__init__(actor, game)
        self.attacked_on_turn = False

    def decide(self) -> Action:
        time.sleep(0.3)

        # сначала проверяем ranged-атаку (до движения, чтобы хватило AP)
        if not self.attacked_on_turn:
            ranged_weapon = next(
                iter(self.actor.get_usable_weapons(WeaponType.RANGED)), None
            )
            if (
                ranged_weapon
                and self.actor.current_action_points >= ranged_weapon.cost_ap
            ):
                for player in self.game.players:
                    if self.game.arena.map.can_shoot(
                        self.actor, ranged_weapon, player.position
                    ):
                        if random.random() < 1 / 3:
                            print(f"         ENEMY {self.actor.name} - RANGED ATTACK")
                            self.attacked_on_turn = True
                            attack_params = AttackActionParams(
                                weapon_id=ranged_weapon.id
                            )
                            return Action(
                                actor_id=str(self.actor.id),
                                type=ActionType.ATTACK,
                                cell=player.position,
                                params=attack_params,
                            )

        # Единственное движение за ход выполняем до дальнейшей атаки/дозора.
        if self.actor.current_speed_spent == 0 and self.game.turn.available_moves:
            players_distances = []
            for player in self.game.players:
                path = self.game.arena.map.bfs_path(
                    self.actor.position, player.position
                )
                if path:
                    players_distances.append((len(path), path))
            if players_distances:
                distance, path = min(players_distances, key=lambda item: item[0])
                if distance > self.WAKE_DISTANCE:
                    print(f"         ENEMY {self.actor.name} - SLEEP")
                else:
                    # Ищем дальнюю доступную клетку, чтобы не тратить MOVE
                    # на короткий шаг при доступном полном маршруте.
                    for step in path[::-1][:-1]:
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
            melee_weapon = next(
                iter(self.actor.get_usable_weapons(WeaponType.MELEE)), None
            )
            if (
                melee_weapon
                and self.actor.current_action_points >= melee_weapon.cost_ap
            ):
                print(f"         ENEMY {self.actor.name} - ATTACKING")
                self.attacked_on_turn = True
                attack_params = AttackActionParams(weapon_id=melee_weapon.id)
                return Action(
                    actor_id=str(self.actor.id),
                    type=ActionType.ATTACK,
                    cell=nearest_player_for_attack.position,
                    params=attack_params,
                )

        # если не атаковали и не двигались — пробуем огневой дозор
        if self.actor.overwatch is None:
            ranged_weapon = next(
                iter(self.actor.get_usable_weapons(WeaponType.RANGED)), None
            )
            if (
                ranged_weapon
                and self.actor.current_action_points >= ranged_weapon.cost_ap
            ):
                # trying to overwatch
                can_see_any_player = any(
                    Point.distance_euklid(self.actor.position, p.position)
                    <= self.actor.stats.view_distance
                    for p in self.game.players
                )
                if can_see_any_player:
                    print(f"         ENEMY {self.actor.name} - OVERWATCH")
                    overwatch_params = OverwatchActionParams(weapon_id=ranged_weapon.id)
                    return Action(
                        actor_id=str(self.actor.id),
                        type=ActionType.OVERWATCH,
                        cell=self.actor.position,
                        params=overwatch_params,
                    )

        print(f"         ENEMY {self.actor.name} - ENDING TURN")
        return self.end_turn()
