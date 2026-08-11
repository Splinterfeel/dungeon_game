import random
import typing
from enum import Enum

from pydantic import BaseModel, Field

from src.entities.base import Actor, HandSide, Weapon, WeaponType
from src.entities.player import Player
from src.skills_catalog import Skill, Skills

if typing.TYPE_CHECKING:
    from src.game import Game


HAND_LABELS_RU = {
    HandSide.LEFT: "левая рука",
    HandSide.RIGHT: "правая рука",
}


class AttackKind(str, Enum):
    REGULAR = "regular"
    OVERWATCH = "overwatch"


class AttackOutcome(BaseModel):
    hit: bool
    action_cost: int = 0
    damage: int = 0
    target_killed: bool = False
    skill_messages: list[str] = Field(default_factory=list)
    damaged_part_name: str | None = None
    part_destroyed: bool = False
    destroyed_part_location: str | None = None

    @property
    def skill_prefix(self) -> str:
        return f"{', '.join(self.skill_messages)}; " if self.skill_messages else ""

    @property
    def part_detail(self) -> str:
        if not self.part_destroyed:
            return ""
        return (
            f" Деталь «{self.damaged_part_name}» "
            f"({self.destroyed_part_location}) уничтожена!"
        )


class CombatResolver:
    def __init__(self, game: "Game"):
        self.game = game

    @staticmethod
    def _try_proc_skill(
        actor: Actor, skill_definition: Skill, procced_actor_ids: set[str]
    ) -> Skill | None:
        if str(actor.id) in procced_actor_ids or not isinstance(actor, Player):
            return None
        skill = next(
            (
                owned_skill
                for owned_skill in actor.skills
                if owned_skill.skill_key == skill_definition.skill_key
            ),
            None,
        )
        if skill is None or random.random() >= skill.proc_chance:
            return None
        procced_actor_ids.add(str(actor.id))
        return skill

    @staticmethod
    def _apply_locational_damage(
        player: Player, damage: int, outcome: AttackOutcome
    ) -> None:
        part = player.mech.apply_random_part_damage(damage)
        if part is None:
            return
        player.mech.recompute_live_stats(player.stats)
        outcome.damaged_part_name = part.name
        outcome.part_destroyed = part.destroyed
        if part.destroyed:
            side = player.mech.hand_side_of(part)
            outcome.destroyed_part_location = (
                HAND_LABELS_RU[side] if side else part.slot.value
            )

    def resolve_attack(
        self,
        attacker: Actor,
        target: Actor,
        weapon: Weapon,
        distance: float,
        kind: AttackKind,
    ) -> AttackOutcome:
        procced_actor_ids: set[str] = set()
        accuracy_bonus = 0
        damage_bonus = 0
        outcome = AttackOutcome(
            hit=False,
            action_cost=weapon.cost_ap if kind == AttackKind.REGULAR else 0,
        )

        if weapon.type == WeaponType.RANGED:
            skill = self._try_proc_skill(
                attacker, Skills.ACCURATE_SHOT, procced_actor_ids
            )
            if skill is not None:
                accuracy_bonus += 15
                outcome.skill_messages.append(f"срабатывает навык «{skill.name}»")
        if kind == AttackKind.REGULAR and weapon.type == WeaponType.MELEE:
            skill = self._try_proc_skill(
                attacker, Skills.HEAVY_STRIKE, procced_actor_ids
            )
            if skill is not None:
                damage_bonus += 3
                outcome.skill_messages.append(f"срабатывает навык «{skill.name}»")
        if kind == AttackKind.REGULAR:
            skill = self._try_proc_skill(
                attacker, Skills.COMBAT_IMPULSE, procced_actor_ids
            )
            if skill is not None:
                outcome.action_cost = 0
                outcome.skill_messages.append(f"срабатывает навык «{skill.name}»")

        attack_stats = attacker.stats.model_copy(
            update={"accuracy": attacker.stats.accuracy + accuracy_bonus}
        )
        outcome.hit = weapon.check_hit(actor_stats=attack_stats, distance=distance)
        if outcome.hit:
            skill = self._try_proc_skill(target, Skills.DODGE, procced_actor_ids)
            if skill is not None:
                outcome.hit = False
                outcome.skill_messages.append(
                    f"срабатывает навык «{skill.name}» у {target.name}"
                )

        if not outcome.hit:
            return outcome

        damage = weapon.roll_damage()
        if weapon.type == WeaponType.MELEE:
            damage += attacker.stats.melee_power
        damage += damage_bonus
        target.apply_damage(damage)
        outcome.damage = damage
        if isinstance(target, Player):
            self._apply_locational_damage(target, damage, outcome)
        if target.is_dead():
            outcome.target_killed = True
            self.game.remove_dead_actor(target)
        return outcome
