"""Таблицы гаража: игровые сущности собираются из них перед матчем."""

from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint
from sqlmodel import Field, SQLModel


class PilotRecord(SQLModel, table=True):
    __tablename__ = "pilots"
    __table_args__ = (CheckConstraint("xp >= 0 AND level >= 1 AND currency >= 0"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str
    xp: int = 0
    level: int = 1
    currency: int = 0
    matches_finished: int = 0
    reward_rolls: int = 0
    rewards_received: int = 0
    parts_equipped: int = 0
    rematches_started: int = 0


class PartCatalogRecord(SQLModel, table=True):
    __tablename__ = "part_catalog"
    __table_args__ = (
        UniqueConstraint("catalog_key", "slot"),
        CheckConstraint("slot IN ('torso', 'legs', 'arms', 'head')"),
        CheckConstraint("rarity IN ('common', 'rare', 'epic')"),
        CheckConstraint("max_health > 0 AND weight >= 0 AND carry_capacity >= 0"),
    )

    catalog_key: str = Field(primary_key=True)
    slot: str
    name: str
    rarity: str
    health: int = 0
    speed: int = 0
    accuracy: int = 0
    melee_power: int = 0
    view_distance: int = 0
    max_health: int = 10
    weight: int = 0
    carry_capacity: int = 0


class PartInstanceRecord(SQLModel, table=True):
    __tablename__ = "part_instances"
    __table_args__ = (
        ForeignKeyConstraint(
            ["catalog_key", "slot"],
            ["part_catalog.catalog_key", "part_catalog.slot"],
        ),
        UniqueConstraint("id", "pilot_id", "slot"),
        CheckConstraint(
            "(affix_tier = 0 AND affix_stat IS NULL AND affix_value = 0) OR "
            "(affix_tier BETWEEN 1 AND 3 AND affix_stat IS NOT NULL "
            "AND affix_value > 0)"
        ),
        CheckConstraint(
            "affix_stat IS NULL OR "
            "(slot = 'torso' AND affix_stat = 'health') OR "
            "(slot = 'legs' AND affix_stat = 'speed') OR "
            "(slot = 'arms' AND affix_stat IN ('accuracy', 'melee_power')) OR "
            "(slot = 'head' AND affix_stat = 'view_distance')"
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    pilot_id: UUID = Field(foreign_key="pilots.id", index=True)
    catalog_key: str
    # Дублируется только для составного FK, который проверяет слот установки.
    slot: str
    affix_tier: int = 0
    affix_stat: str | None = None
    affix_value: int = 0


class MechLoadoutRecord(SQLModel, table=True):
    __tablename__ = "mech_loadouts"
    __table_args__ = (
        UniqueConstraint("pilot_id", "slot_index"),
        UniqueConstraint("id", "pilot_id"),
        CheckConstraint("slot_index IN (0, 1)"),
        CheckConstraint("reactor_mode IN ('fortified', 'neutral', 'overdrive')"),
        CheckConstraint("fire_control_mode IN ('precision', 'neutral', 'impact')"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    pilot_id: UUID = Field(foreign_key="pilots.id", index=True)
    slot_index: int
    name: str
    preset_name: str | None = None
    reactor_mode: str = "neutral"
    fire_control_mode: str = "neutral"


class LoadoutPartRecord(SQLModel, table=True):
    __tablename__ = "loadout_parts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["loadout_id", "pilot_id"], ["mech_loadouts.id", "mech_loadouts.pilot_id"]
        ),
        ForeignKeyConstraint(
            ["part_id", "pilot_id", "slot"],
            ["part_instances.id", "part_instances.pilot_id", "part_instances.slot"],
        ),
        UniqueConstraint("part_id"),
    )

    loadout_id: UUID = Field(primary_key=True)
    slot: str = Field(primary_key=True)
    pilot_id: UUID
    part_id: UUID


class LoadoutWeaponRecord(SQLModel, table=True):
    __tablename__ = "loadout_weapons"
    __table_args__ = (
        CheckConstraint("hand IN ('left', 'right')"),
        CheckConstraint("weapon_type IN ('melee', 'ranged')"),
        CheckConstraint(
            "damage > 0 AND cost_ap > 0 AND attack_range > 0 AND weight >= 0"
        ),
        CheckConstraint("accuracy BETWEEN 0 AND 100"),
    )

    loadout_id: UUID = Field(foreign_key="mech_loadouts.id", primary_key=True)
    hand: str = Field(primary_key=True)
    weapon_type: str
    name: str
    damage: int
    cost_ap: int
    attack_range: int
    accuracy: int
    weight: int = 0


class SkillCatalogRecord(SQLModel, table=True):
    __tablename__ = "skill_catalog"
    __table_args__ = (
        CheckConstraint("trigger IN ('attack', 'defense')"),
        CheckConstraint("proc_chance BETWEEN 0 AND 1"),
    )

    skill_key: str = Field(primary_key=True)
    name: str
    trigger: str
    proc_chance: float
    description: str


class SkillChoiceRuleRecord(SQLModel, table=True):
    __tablename__ = "skill_choice_rules"
    __table_args__ = (CheckConstraint("level >= 2"),)

    level: int = Field(primary_key=True)
    skill_key: str = Field(foreign_key="skill_catalog.skill_key", primary_key=True)
    required_skill_key: str | None = Field(
        default=None, foreign_key="skill_catalog.skill_key"
    )


class PilotSkillRecord(SQLModel, table=True):
    __tablename__ = "pilot_skills"

    pilot_id: UUID = Field(foreign_key="pilots.id", primary_key=True)
    skill_key: str = Field(foreign_key="skill_catalog.skill_key", primary_key=True)


class PendingSkillChoiceRecord(SQLModel, table=True):
    __tablename__ = "pending_skill_choices"
    __table_args__ = (CheckConstraint("level >= 2"),)

    pilot_id: UUID = Field(foreign_key="pilots.id", primary_key=True)
    level: int = Field(primary_key=True)


class MatchRecord(SQLModel, table=True):
    __tablename__ = "matches"

    id: UUID = Field(primary_key=True)
    winner: int | None = None
    finalized: bool = False


class MatchParticipantRecord(SQLModel, table=True):
    __tablename__ = "match_participants"
    __table_args__ = (CheckConstraint("team IN (1, 2)"),)

    match_id: UUID = Field(foreign_key="matches.id", primary_key=True)
    pilot_id: UUID = Field(foreign_key="pilots.id", primary_key=True)
    team: int


class MatchRewardRecord(SQLModel, table=True):
    __tablename__ = "match_rewards"

    match_id: UUID = Field(foreign_key="matches.id", primary_key=True)
    pilot_id: UUID = Field(foreign_key="pilots.id", primary_key=True)
    xp_awarded: int
    part_id: UUID | None = Field(default=None, foreign_key="part_instances.id")
    chance: float
    reason: str
