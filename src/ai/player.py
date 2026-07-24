from src.action import Action, ActionType, AttackActionParams, OverwatchActionParams
from src.ai.base import AI
from src.base import Point
from src.entities.player import Player


class PlayerBotAI(AI):
    """Простой командный PvP-бот, управляющий одним мехом."""

    actor: Player

    def __init__(self, actor: Player, game):
        super().__init__(actor, game)
        self.attacked_on_turn = False

    def _hostiles(self) -> list[Player]:
        return [
            player
            for player in self.game.players
            if self.game._is_hostile(self.actor, player) and not player.is_dead()
        ]

    def _pick_weapon(self, weapon_type: str):
        for weapon in self.actor.inventory.weapons:
            if weapon.type != weapon_type:
                continue
            if weapon.hand and self.actor.mech.arm_for(weapon.hand).destroyed:
                continue
            return weapon
        return None

    def decide(self) -> Action:
        hostiles = self._hostiles()
        if not hostiles:
            return self.end_turn()

        if not self.attacked_on_turn:
            ranged_weapon = self._pick_weapon("ranged")
            if (
                ranged_weapon
                and self.actor.current_action_points >= ranged_weapon.cost_ap
            ):
                shootable = [
                    player
                    for player in hostiles
                    if self.game.arena.map.can_shoot(
                        self.actor, ranged_weapon, player.position
                    )
                ]
                if shootable:
                    target = min(shootable, key=lambda player: player.stats.health)
                    self.attacked_on_turn = True
                    return Action(
                        actor_id=str(self.actor.id),
                        type=ActionType.ATTACK,
                        cell=target.position,
                        params=AttackActionParams(weapon_id=ranged_weapon.id),
                    )

        if self.actor.stats.speed - self.actor.current_speed_spent > 0:
            paths = []
            for player in hostiles:
                path = self.game.arena.map.bfs_path(
                    self.actor.position, player.position
                )
                if path:
                    paths.append((len(path), path))
            if paths:
                _, path = min(paths, key=lambda item: item[0])
                for step in path[::-1][:-1]:
                    if step in self.game.turn.available_moves:
                        return Action(
                            actor_id=str(self.actor.id),
                            type=ActionType.MOVE,
                            cell=step,
                        )

        adjacent_target = next(
            (
                player
                for player in hostiles
                if Point.distance_chebyshev(player.position, self.actor.position) == 1
            ),
            None,
        )
        if adjacent_target and not self.attacked_on_turn:
            melee_weapon = self._pick_weapon("melee")
            if (
                melee_weapon
                and self.actor.current_action_points >= melee_weapon.cost_ap
            ):
                self.attacked_on_turn = True
                return Action(
                    actor_id=str(self.actor.id),
                    type=ActionType.ATTACK,
                    cell=adjacent_target.position,
                    params=AttackActionParams(weapon_id=melee_weapon.id),
                )

        if self.actor.overwatch is None:
            ranged_weapon = self._pick_weapon("ranged")
            if (
                ranged_weapon
                and self.actor.current_action_points >= ranged_weapon.cost_ap
            ):
                can_see_any = any(
                    self.game.arena.map.can_see(self.actor, player)
                    for player in hostiles
                )
                if can_see_any:
                    return Action(
                        actor_id=str(self.actor.id),
                        type=ActionType.OVERWATCH,
                        cell=self.actor.position,
                        params=OverwatchActionParams(weapon_id=ranged_weapon.id),
                    )

        return self.end_turn()
