"""In-memory гараж для вертикального среза петли лута.

Профиль живёт в LobbyManager и намеренно не является боевым Player: каждый матч
получает свежие HP, прочность деталей и экземпляры оружия.
"""

import random
import uuid
from enum import Enum

from pydantic import BaseModel, Field

from src.entities.base import Inventory, UUIDStr, Weapon
from src.entities.mech import Mech
from src.entities.part import Part, PartRarity, PartSlot, PartType
from src.entities.player import Player

from src.progression import (
    MATCH_XP_REWARDS,
    PendingSkillChoice,
    ProgressionResult,
    award_xp as award_xp_progression,
    build_skills as build_pilot_skills,
    choose_skill as choose_pilot_skill,
    get_pending_skill_options as get_progression_pending_skill_options,
)
from src.rewards import (
    AFFIX_VALUES_BY_STAT,
    AFFIX_TIER_WEIGHTS,
    MATCH_REWARD_CHANCES,
    PART_TEMPLATES,
    RewardResult,
    apply_random_affix,
    weighted_roll_int,
)


class ReactorMode(str, Enum):
    FORTIFIED = "fortified"
    NEUTRAL = "neutral"
    OVERDRIVE = "overdrive"


class FireControlMode(str, Enum):
    PRECISION = "precision"
    NEUTRAL = "neutral"
    IMPACT = "impact"


REACTOR_HP_AP_DELTAS: dict[ReactorMode, tuple[int, int]] = {
    ReactorMode.FORTIFIED: (2, -1),
    ReactorMode.NEUTRAL: (0, 0),
    ReactorMode.OVERDRIVE: (-2, 1),
}
FIRE_CONTROL_DELTAS: dict[FireControlMode, tuple[int, int]] = {
    FireControlMode.PRECISION: (5, -1),
    FireControlMode.NEUTRAL: (0, 0),
    FireControlMode.IMPACT: (-5, 1),
}


def part_catalog_key(part: Part) -> PartType:
    return part.catalog_key


def fresh_part(part: Part, *, keep_id: bool = False) -> Part:
    """Клонирует деталь как целую: прочность боя никогда не хранится в гараже."""
    return part.fresh_copy(keep_id=keep_id)


class GarageMetrics(BaseModel):
    matches_finished: int = 0
    reward_rolls: int = 0
    rewards_received: int = 0
    parts_equipped: int = 0
    rematches_started: int = 0


class MechLoadout(BaseModel):
    id: UUIDStr = Field(default_factory=uuid.uuid4)
    name: str
    preset_name: str | None = None
    weapons: list[Weapon]
    equipped_part_ids: dict[PartSlot, UUIDStr]
    reactor_mode: ReactorMode = ReactorMode.NEUTRAL
    fire_control_mode: FireControlMode = FireControlMode.NEUTRAL


class GarageProfile(BaseModel):
    player_id: UUIDStr
    name: str
    owned_parts: list[Part]
    loadouts: list[MechLoadout] = Field(min_length=2, max_length=2)
    metrics: GarageMetrics = Field(default_factory=GarageMetrics)
    xp: int = 0
    level: int = 1
    owned_skill_keys: list[str] = Field(default_factory=list)
    pending_skill_choices: list[PendingSkillChoice] = Field(default_factory=list)

    @classmethod
    def from_players(cls, players: list[Player]) -> "GarageProfile":
        if len(players) != 2:
            raise ValueError("Стартовый гараж должен содержать ровно два меха")

        owned_parts: list[Part] = []
        loadouts: list[MechLoadout] = []
        for index, player in enumerate(players, start=1):
            parts = [
                fresh_part(player.mech.torso, keep_id=True),
                fresh_part(player.mech.legs, keep_id=True),
                fresh_part(player.mech.arms_left, keep_id=True),
                fresh_part(player.mech.head, keep_id=True),
            ]
            owned_parts.extend(parts)
            loadouts.append(
                MechLoadout(
                    name=f"Мех {index}",
                    preset_name=player.mech.preset_name,
                    weapons=[
                        weapon.model_copy(deep=True)
                        for weapon in player.inventory.weapons
                    ],
                    equipped_part_ids={part.slot: part.id for part in parts},
                )
            )

        return cls(
            player_id=players[0].id,
            name=players[0].name,
            owned_parts=owned_parts,
            loadouts=loadouts,
        )

    def part_by_id(self, part_id: UUIDStr) -> Part:
        for part in self.owned_parts:
            if str(part.id) == str(part_id):
                return part
        raise ValueError("Деталь не найдена в гараже пилота")

    def loadout_by_id(self, loadout_id: UUIDStr | str | None = None) -> MechLoadout:
        if loadout_id is None:
            return self.loadouts[0]
        for loadout in self.loadouts:
            if str(loadout.id) == str(loadout_id):
                return loadout
        raise ValueError("Лоадаут не найден в гараже пилота")

    def equipped_part(self, loadout: MechLoadout, slot: PartSlot) -> Part:
        return self.part_by_id(loadout.equipped_part_ids[slot])

    def build_mech(self, loadout_id: UUIDStr | str | None = None) -> Mech:
        loadout = self.loadout_by_id(loadout_id)
        arms = self.equipped_part(loadout, PartSlot.ARMS)
        return Mech.from_part_selection(
            torso=self.equipped_part(loadout, PartSlot.TORSO),
            legs=self.equipped_part(loadout, PartSlot.LEGS),
            arms=arms,
            head=self.equipped_part(loadout, PartSlot.HEAD),
            preset_name=loadout.preset_name,
        )

    def build_player(
        self,
        team: int = 1,
        loadout_id: UUIDStr | str | None = None,
        actor_id: UUIDStr | None = None,
    ) -> Player:
        loadout = self.loadout_by_id(loadout_id)
        mech = self.build_mech(loadout.id)
        stats = mech.build_character_stats(action_points=10)
        hp_delta, ap_delta = REACTOR_HP_AP_DELTAS[loadout.reactor_mode]
        accuracy_delta, damage_delta = FIRE_CONTROL_DELTAS[loadout.fire_control_mode]
        stats.health += hp_delta
        stats.max_health += hp_delta
        stats.action_points += ap_delta
        stats.accuracy += accuracy_delta
        return Player(
            id=actor_id or self.player_id,
            owner_player_id=self.player_id,
            loadout_id=loadout.id,
            team=team,
            name=f"{self.name} / {loadout.name}",
            mech=mech,
            stats=stats,
            skills=self.build_skills(),
            inventory=Inventory(
                weapons=[
                    weapon.model_copy(
                        update={
                            "id": uuid.uuid4(),
                            "damage": max(1, weapon.damage + damage_delta),
                        }
                    )
                    for weapon in loadout.weapons
                ]
            ),
        )

    def build_skills(self):
        return build_pilot_skills(self.owned_skill_keys)

    def get_pending_skill_options(self):
        return get_progression_pending_skill_options(
            self.pending_skill_choices,
            self.owned_skill_keys,
        )

    def award_xp(self, xp_amount: int) -> ProgressionResult:
        self.xp, self.level, result = award_xp_progression(
            current_xp=self.xp,
            current_level=self.level,
            pending_skill_choices=self.pending_skill_choices,
            xp_amount=xp_amount,
        )
        return result

    def choose_skill(self, skill_key: str) -> None:
        choose_pilot_skill(
            owned_skill_keys=self.owned_skill_keys,
            pending_skill_choices=self.pending_skill_choices,
            skill_key=skill_key,
        )

    def equip(self, loadout_id: UUIDStr | str, part_id: UUIDStr) -> None:
        loadout = self.loadout_by_id(loadout_id)
        part = self.part_by_id(part_id)
        previous_id = loadout.equipped_part_ids.get(part.slot)
        if previous_id == part.id:
            return

        for other_loadout in self.loadouts:
            if other_loadout.id == loadout.id:
                continue
            if any(
                str(equipped_id) == str(part.id)
                for equipped_id in other_loadout.equipped_part_ids.values()
            ):
                raise ValueError(f"Деталь уже установлена на «{other_loadout.name}»")

        proposed = loadout.equipped_part_ids | {part.slot: part.id}
        self._validate_loadout(loadout, proposed)
        loadout.equipped_part_ids = proposed
        self.metrics.parts_equipped += 1

    def set_tuning(
        self,
        loadout_id: UUIDStr | str,
        reactor_mode: ReactorMode,
        fire_control_mode: FireControlMode,
    ) -> None:
        loadout = self.loadout_by_id(loadout_id)
        loadout.reactor_mode = reactor_mode
        loadout.fire_control_mode = fire_control_mode

    def _validate_loadout(
        self,
        loadout: MechLoadout,
        equipped_ids: dict[PartSlot, UUIDStr],
    ) -> None:
        parts = {
            slot: self.part_by_id(part_id) for slot, part_id in equipped_ids.items()
        }
        mech = Mech.from_part_selection(
            torso=parts[PartSlot.TORSO],
            legs=parts[PartSlot.LEGS],
            arms=parts[PartSlot.ARMS],
            head=parts[PartSlot.HEAD],
        )
        total_weight = mech.parts_weight + sum(
            weapon.weight for weapon in loadout.weapons
        )
        if total_weight > mech.weight_capacity:
            raise ValueError(
                f"Сборка весит {total_weight}, превышен грузоподъём меха "
                f"({mech.weight_capacity})"
            )


def roll_match_reward(profile: GarageProfile, is_winner: bool) -> RewardResult:
    """Один честный ролл: шанс -> редкость -> деталь -> аффикс."""
    profile.metrics.reward_rolls += 1
    chance = MATCH_REWARD_CHANCES["winner" if is_winner else "loser"]
    if random.random() >= chance:
        return RewardResult(chance=chance, reason="Бросок награды не сработал")

    owned_keys = {part_catalog_key(part) for part in profile.owned_parts}
    selected_rarity = PartRarity.COMMON if random.random() < 0.70 else PartRarity.RARE
    rarity_pool = [part for part in PART_TEMPLATES if part.rarity == selected_rarity]
    if not rarity_pool:
        rarity_pool = list(PART_TEMPLATES)

    affix_tier = weighted_roll_int(AFFIX_TIER_WEIGHTS)
    if affix_tier == 0:
        undiscovered_pool = [
            part for part in rarity_pool if part_catalog_key(part) not in owned_keys
        ]
        selected_template = random.choice(undiscovered_pool or rarity_pool)
        part = fresh_part(selected_template)
    else:
        selected_template = random.choice(rarity_pool)
        part = apply_random_affix(fresh_part(selected_template), affix_tier)

    profile.owned_parts.append(part)
    profile.metrics.rewards_received += 1
    return RewardResult(awarded_part=part, chance=chance, reason="Деталь получена")


__all__ = [
    "FireControlMode",
    "GarageMetrics",
    "GarageProfile",
    "MATCH_REWARD_CHANCES",
    "MATCH_XP_REWARDS",
    "MechLoadout",
    "PendingSkillChoice",
    "ProgressionResult",
    "REACTOR_HP_AP_DELTAS",
    "FIRE_CONTROL_DELTAS",
    "ReactorMode",
    "RewardResult",
    "apply_random_affix",
    "AFFIX_VALUES_BY_STAT",
    "fresh_part",
    "part_catalog_key",
    "roll_match_reward",
]
