"""In-memory гараж для вертикального среза петли лута.

Профиль живёт в LobbyManager и намеренно не является боевым Player: каждый матч
получает свежие HP, прочность деталей и экземпляры оружия.
"""

import copy
import random
import uuid
from enum import Enum

from pydantic import BaseModel, Field

from src.entities.base import CharacterStats, Inventory, UUIDStr, Weapon
from src.entities.mech import Mech
from src.entities.part import Part, PartRarity, PartSlot
from src.entities.player import Player
from src.skills_catalog import Skill, fresh_skills_by_keys, get_skill_choice_options
from src.parts_catalog import (
    DEFAULT_ARMS,
    DEFAULT_HEAD,
    DEFAULT_LEGS,
    DEFAULT_TORSO,
    FIREWORKS_ARMS,
    FIREWORKS_HEAD,
    FIREWORKS_LEGS,
    FIREWORKS_TORSO,
    STEELMAN_ARMS,
    STEELMAN_HEAD,
    STEELMAN_LEGS,
    STEELMAN_TORSO,
    STRIKEFORCE_ARMS,
    STRIKEFORCE_HEAD,
    STRIKEFORCE_LEGS,
    STRIKEFORCE_TORSO,
)


MATCH_REWARD_CHANCES = {"winner": 0.80, "loser": 0.35}
MATCH_XP_REWARDS = {"winner": 70, "loser": 30}
LEVEL_XP_THRESHOLDS = {2: 100, 3: 250}
AFFIX_TIER_WEIGHTS: tuple[tuple[int, float], ...] = (
    (3, 0.05),
    (2, 0.15),
    (1, 0.30),
    (0, 0.50),
)
AFFIX_STAT_POOLS: dict[PartSlot, tuple[str, ...]] = {
    PartSlot.TORSO: ("health",),
    PartSlot.LEGS: ("speed",),
    PartSlot.ARMS: ("accuracy", "melee_power"),
    PartSlot.HEAD: ("view_distance",),
}
AFFIX_VALUES_BY_STAT: dict[str, tuple[int, int, int]] = {
    # Торс на стеклянных пресетах (особенно StrikeForce) очень чувствителен
    # к плоскому приросту HP, поэтому health-аффикс держим намеренно
    # консервативным: +1/+1/+2 вместо линейной лесенки.
    "health": (1, 1, 2),
    "speed": (1, 2, 3),
    "accuracy": (4, 8, 12),
    "melee_power": (1, 2, 3),
    "view_distance": (1, 2, 3),
}
AFFIX_STAT_LABELS: dict[str, str] = {
    "health": "здоровью",
    "speed": "скорости",
    "accuracy": "точности",
    "melee_power": "силе удара",
    "view_distance": "обзору",
}

PART_TEMPLATES = (
    DEFAULT_TORSO,
    DEFAULT_LEGS,
    DEFAULT_ARMS,
    DEFAULT_HEAD,
    STEELMAN_TORSO,
    STEELMAN_LEGS,
    STEELMAN_ARMS,
    STEELMAN_HEAD,
    FIREWORKS_TORSO,
    FIREWORKS_LEGS,
    FIREWORKS_ARMS,
    FIREWORKS_HEAD,
    STRIKEFORCE_TORSO,
    STRIKEFORCE_LEGS,
    STRIKEFORCE_ARMS,
    STRIKEFORCE_HEAD,
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


def part_catalog_key(part: Part) -> str:
    return part.catalog_key or f"{part.slot.value}:{part.name}"


def fresh_part(part: Part, *, keep_id: bool = False) -> Part:
    """Клонирует деталь как целую: прочность боя никогда не хранится в гараже."""
    max_health = part.max_health or Part.DEFAULT_MAX_HEALTH
    return part.model_copy(
        update={
            "id": part.id if keep_id else uuid.uuid4(),
            "catalog_key": part_catalog_key(part),
            "max_health": max_health,
            "current_health": max_health,
        }
    )


def weighted_roll_int(weighted_values: tuple[tuple[int, float], ...]) -> int:
    roll = random.random()
    cumulative = 0.0
    for value, weight in weighted_values:
        cumulative += weight
        if roll < cumulative:
            return value
    return weighted_values[-1][0]


def apply_random_affix(part: Part, affix_tier: int | None = None) -> Part:
    affix_tier = affix_tier or weighted_roll_int(AFFIX_TIER_WEIGHTS)
    if affix_tier == 0:
        return part

    stat_name = random.choice(AFFIX_STAT_POOLS[part.slot])
    affix_value = AFFIX_VALUES_BY_STAT[stat_name][affix_tier - 1]
    setattr(part, stat_name, getattr(part, stat_name) + affix_value)
    part.affix_tier = affix_tier
    part.affix_stat = stat_name
    part.affix_value = affix_value
    part.name = (
        f"{part.name} +{affix_tier} к {AFFIX_STAT_LABELS[stat_name]}"
    )
    return part


class GarageMetrics(BaseModel):
    matches_finished: int = 0
    reward_rolls: int = 0
    rewards_received: int = 0
    parts_equipped: int = 0
    rematches_started: int = 0


class PendingSkillChoice(BaseModel):
    level: int


class ProgressionResult(BaseModel):
    xp_awarded: int
    level_before: int
    level_after: int
    pending_choices_added: list[int] = Field(default_factory=list)


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
            # Руки — одна физическая деталь гаража, хотя в бою она создаёт
            # две раздельно повреждаемые руки.
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
        return Mech(
            torso=fresh_part(self.equipped_part(loadout, PartSlot.TORSO)),
            legs=fresh_part(self.equipped_part(loadout, PartSlot.LEGS)),
            arms_left=fresh_part(arms),
            arms_right=fresh_part(arms),
            head=fresh_part(self.equipped_part(loadout, PartSlot.HEAD)),
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

    def build_skills(self) -> list[Skill]:
        return fresh_skills_by_keys(self.owned_skill_keys)

    def get_pending_skill_options(self) -> list[tuple[int, list[Skill]]]:
        pending_options: list[tuple[int, list[Skill]]] = []
        for pending_choice in self.pending_skill_choices:
            options = get_skill_choice_options(pending_choice.level, self.owned_skill_keys)
            pending_options.append((pending_choice.level, options))
        return pending_options

    def award_xp(self, xp_amount: int) -> ProgressionResult:
        level_before = self.level
        self.xp += xp_amount
        pending_levels_added: list[int] = []
        for level, threshold in sorted(LEVEL_XP_THRESHOLDS.items()):
            if self.level >= level:
                continue
            if self.xp < threshold:
                break
            self.level = level
            self.pending_skill_choices.append(PendingSkillChoice(level=level))
            pending_levels_added.append(level)
        return ProgressionResult(
            xp_awarded=xp_amount,
            level_before=level_before,
            level_after=self.level,
            pending_choices_added=pending_levels_added,
        )

    def choose_skill(self, skill_key: str) -> None:
        if not self.pending_skill_choices:
            raise ValueError("У пилота нет доступного выбора навыка")
        pending_choice = self.pending_skill_choices[0]
        allowed_keys = {
            skill.skill_key
            for skill in get_skill_choice_options(
                pending_choice.level, self.owned_skill_keys
            )
        }
        if not allowed_keys:
            raise ValueError("Для текущего выбора навыка пока не выполнены условия ветки")
        if skill_key not in allowed_keys:
            raise ValueError("Выбран недоступный навык для текущего уровня")
        if skill_key in self.owned_skill_keys:
            raise ValueError("Этот навык уже выбран у пилота")
        self.owned_skill_keys.append(skill_key)
        self.pending_skill_choices.pop(0)

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
        mech = Mech(
            torso=fresh_part(parts[PartSlot.TORSO]),
            legs=fresh_part(parts[PartSlot.LEGS]),
            arms_left=fresh_part(parts[PartSlot.ARMS]),
            arms_right=fresh_part(parts[PartSlot.ARMS]),
            head=fresh_part(parts[PartSlot.HEAD]),
        )
        total_weight = mech.parts_weight + sum(
            weapon.weight for weapon in loadout.weapons
        )
        if total_weight > mech.weight_capacity:
            raise ValueError(
                f"Сборка весит {total_weight}, превышен грузоподъём меха "
                f"({mech.weight_capacity})"
            )


class RewardResult(BaseModel):
    awarded_part: Part | None = None
    chance: float
    reason: str


def roll_match_reward(profile: GarageProfile, is_winner: bool) -> RewardResult:
    """Один честный ролл: шанс -> редкость -> деталь -> аффикс."""
    profile.metrics.reward_rolls += 1
    chance = MATCH_REWARD_CHANCES["winner" if is_winner else "loser"]
    if random.random() >= chance:
        return RewardResult(chance=chance, reason="Бросок награды не сработал")

    owned_keys = {part_catalog_key(part) for part in profile.owned_parts}
    if not PART_TEMPLATES:
        return RewardResult(
            chance=chance, reason="Каталог деталей пуст"
        )

    selected_rarity = PartRarity.COMMON if random.random() < 0.70 else PartRarity.RARE
    rarity_pool = [part for part in PART_TEMPLATES if part.rarity == selected_rarity]
    if not rarity_pool:
        rarity_pool = list(PART_TEMPLATES)

    affix_tier = weighted_roll_int(AFFIX_TIER_WEIGHTS)
    if affix_tier == 0:
        undiscovered_pool = [
            part
            for part in rarity_pool
            if part_catalog_key(part) not in owned_keys
        ]
        selected_template = random.choice(undiscovered_pool or rarity_pool)
        part = fresh_part(selected_template)
    else:
        selected_template = random.choice(rarity_pool)
        part = apply_random_affix(fresh_part(selected_template), affix_tier)

    profile.owned_parts.append(part)
    profile.metrics.rewards_received += 1
    return RewardResult(awarded_part=part, chance=chance, reason="Деталь получена")
