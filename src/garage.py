"""In-memory гараж для вертикального среза петли лута.

Профиль живёт в LobbyManager и намеренно не является боевым Player: каждый матч
получает свежие HP, прочность деталей и экземпляры оружия.
"""

import copy
import random
import uuid

from pydantic import BaseModel, Field

from src.entities.base import CharacterStats, Inventory, UUIDStr, Weapon
from src.entities.mech import Mech
from src.entities.part import Part, PartRarity, PartSlot
from src.entities.player import Player
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


class GarageProfile(BaseModel):
    player_id: UUIDStr
    name: str
    owned_parts: list[Part]
    loadouts: list[MechLoadout] = Field(min_length=2, max_length=2)
    metrics: GarageMetrics = Field(default_factory=GarageMetrics)

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
        return Player(
            id=actor_id or self.player_id,
            owner_player_id=self.player_id,
            loadout_id=loadout.id,
            team=team,
            name=f"{self.name} / {loadout.name}",
            mech=mech,
            stats=mech.build_character_stats(action_points=10),
            inventory=Inventory(
                weapons=[
                    weapon.model_copy(update={"id": uuid.uuid4()})
                    for weapon in loadout.weapons
                ]
            ),
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
    """Один честный ролл: шанс -> редкость -> новая базовая деталь."""
    profile.metrics.reward_rolls += 1
    chance = MATCH_REWARD_CHANCES["winner" if is_winner else "loser"]
    if random.random() >= chance:
        return RewardResult(chance=chance, reason="Бросок награды не сработал")

    owned_keys = {part_catalog_key(part) for part in profile.owned_parts}
    available = [
        part for part in PART_TEMPLATES if part_catalog_key(part) not in owned_keys
    ]
    if not available:
        return RewardResult(
            chance=chance, reason="Все базовые детали каталога уже открыты"
        )

    selected_rarity = PartRarity.COMMON if random.random() < 0.70 else PartRarity.RARE
    rarity_pool = [part for part in available if part.rarity == selected_rarity]
    # Исчерпанный пул не превращает успешную награду в пустышку.
    part = fresh_part(random.choice(rarity_pool or available))
    profile.owned_parts.append(part)
    profile.metrics.rewards_received += 1
    return RewardResult(awarded_part=part, chance=chance, reason="Деталь получена")
