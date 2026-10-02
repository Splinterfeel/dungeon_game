"""Преобразование строк БД в гараж и сохранение изменений гаража."""

from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.entities.base import Weapon
from src.garage import GarageMetrics, GarageProfile, MechLoadout
from src.mech.part import Part, PartSlot
from src.persistence.models import (
    LoadoutPartRecord,
    LoadoutWeaponRecord,
    MechLoadoutRecord,
    PartCatalogRecord,
    PartInstanceRecord,
    PendingSkillChoiceRecord,
    PilotRecord,
    PilotSkillRecord,
    SkillCatalogRecord,
    SkillChoiceRuleRecord,
)
from src.progression import PendingSkillChoice
from src.rewards import AFFIX_STAT_LABELS
from src.skills_catalog import Skill

METRIC_FIELDS = (
    "matches_finished",
    "reward_rolls",
    "rewards_received",
    "parts_equipped",
    "rematches_started",
)


def part_from_catalog(
    catalog: PartCatalogRecord, instance: PartInstanceRecord | None = None
) -> Part:
    data = {
        name: getattr(catalog, name)
        for name in (
            "catalog_key",
            "slot",
            "name",
            "rarity",
            "health",
            "speed",
            "accuracy",
            "melee_power",
            "view_distance",
            "max_health",
            "weight",
            "carry_capacity",
        )
    }
    if instance is not None:
        data.update(
            id=instance.id,
            affix_tier=instance.affix_tier,
            affix_stat=instance.affix_stat,
            affix_value=instance.affix_value,
        )
        if instance.affix_stat:
            stat = instance.affix_stat
            data[stat] += instance.affix_value
            data["name"] += f" +{instance.affix_tier} к {AFFIX_STAT_LABELS[stat]}"
    return Part.model_validate(data)


async def load_catalog(
    session: AsyncSession,
) -> tuple[list[Part], dict[str, Skill], dict[int, dict[str | None, tuple[str, ...]]]]:
    parts = (
        await session.scalars(
            select(PartCatalogRecord).order_by(PartCatalogRecord.catalog_key)
        )
    ).all()
    skills = (await session.scalars(select(SkillCatalogRecord))).all()
    rules = (
        await session.scalars(
            select(SkillChoiceRuleRecord).order_by(
                SkillChoiceRuleRecord.level, SkillChoiceRuleRecord.skill_key
            )
        )
    ).all()
    definitions = {
        row.skill_key: Skill(
            skill_key=row.skill_key,
            name=row.name,
            trigger=row.trigger,
            proc_chance=row.proc_chance,
            description=row.description,
        )
        for row in skills
    }
    tree: dict[int, dict[str | None, tuple[str, ...]]] = {}
    for row in rules:
        branch = tree.setdefault(row.level, {})
        branch[row.required_skill_key] = branch.get(row.required_skill_key, ()) + (
            row.skill_key,
        )
    return [part_from_catalog(row) for row in parts], definitions, tree


async def load_profile(
    session: AsyncSession, player_id: str | UUID, *, for_update: bool = False
) -> GarageProfile | None:
    pilot_id = UUID(str(player_id))
    statement = select(PilotRecord).where(PilotRecord.id == pilot_id)
    if for_update:
        statement = statement.with_for_update()
    pilot = (await session.scalars(statement)).one_or_none()
    if pilot is None:
        return None
    catalog_rows = (await session.scalars(select(PartCatalogRecord))).all()
    catalog = {row.catalog_key: row for row in catalog_rows}
    instances = (
        await session.scalars(
            select(PartInstanceRecord).where(PartInstanceRecord.pilot_id == pilot_id)
        )
    ).all()
    parts = [part_from_catalog(catalog[row.catalog_key], row) for row in instances]
    loadout_rows = (
        await session.scalars(
            select(MechLoadoutRecord)
            .where(MechLoadoutRecord.pilot_id == pilot_id)
            .order_by(MechLoadoutRecord.slot_index)
        )
    ).all()
    loadouts = []
    for row in loadout_rows:
        equipped = (
            await session.scalars(
                select(LoadoutPartRecord).where(LoadoutPartRecord.loadout_id == row.id)
            )
        ).all()
        weapons = (
            await session.scalars(
                select(LoadoutWeaponRecord).where(
                    LoadoutWeaponRecord.loadout_id == row.id
                )
            )
        ).all()
        weapons = sorted(weapons, key=lambda weapon: weapon.hand != "right")
        loadouts.append(
            MechLoadout(
                id=row.id,
                name=row.name,
                preset_name=row.preset_name,
                reactor_mode=row.reactor_mode,
                fire_control_mode=row.fire_control_mode,
                equipped_part_ids={
                    PartSlot(item.slot): item.part_id for item in equipped
                },
                weapons=[
                    Weapon(
                        type=weapon.weapon_type,
                        name=weapon.name,
                        damage=weapon.damage,
                        cost_ap=weapon.cost_ap,
                        range=weapon.attack_range,
                        accuracy=weapon.accuracy,
                        weight=weapon.weight,
                        hand=weapon.hand,
                    )
                    for weapon in weapons
                ],
            )
        )
    owned = (
        await session.scalars(
            select(PilotSkillRecord)
            .where(PilotSkillRecord.pilot_id == pilot_id)
            .order_by(PilotSkillRecord.skill_key)
        )
    ).all()
    pending = (
        await session.scalars(
            select(PendingSkillChoiceRecord)
            .where(PendingSkillChoiceRecord.pilot_id == pilot_id)
            .order_by(PendingSkillChoiceRecord.level)
        )
    ).all()
    templates, definitions, tree = await load_catalog(session)
    return GarageProfile(
        player_id=pilot.id,
        name=pilot.name,
        owned_parts=parts,
        loadouts=loadouts,
        metrics=GarageMetrics(**{name: getattr(pilot, name) for name in METRIC_FIELDS}),
        xp=pilot.xp,
        level=pilot.level,
        owned_skill_keys=[row.skill_key for row in owned],
        pending_skill_choices=[PendingSkillChoice(level=row.level) for row in pending],
        part_templates=templates,
        skill_definitions=definitions,
        skill_choice_rules=tree,
    )


async def save_profile(session: AsyncSession, profile: GarageProfile) -> None:
    pilot_id = UUID(str(profile.player_id))
    pilot = await session.get(PilotRecord, pilot_id)
    if pilot is None:
        pilot = PilotRecord(id=pilot_id, name=profile.name)
        session.add(pilot)
    pilot.name = profile.name
    pilot.xp = profile.xp
    pilot.level = profile.level
    for name in METRIC_FIELDS:
        setattr(pilot, name, getattr(profile.metrics, name))
    await session.flush()

    existing_parts = set(
        (
            await session.scalars(
                select(PartInstanceRecord.id).where(
                    PartInstanceRecord.pilot_id == pilot_id
                )
            )
        ).all()
    )
    for part in profile.owned_parts:
        if part.id not in existing_parts:
            session.add(
                PartInstanceRecord(
                    id=part.id,
                    pilot_id=pilot_id,
                    catalog_key=part.catalog_key,
                    slot=part.slot.value,
                    affix_tier=part.affix_tier,
                    affix_stat=part.affix_stat,
                    affix_value=part.affix_value,
                )
            )
    await session.flush()
    for index, loadout in enumerate(profile.loadouts):
        row = await session.get(MechLoadoutRecord, loadout.id)
        if row is None:
            row = MechLoadoutRecord(
                id=loadout.id, pilot_id=pilot_id, slot_index=index, name=loadout.name
            )
            session.add(row)
        row.name = loadout.name
        row.preset_name = loadout.preset_name
        row.reactor_mode = loadout.reactor_mode.value
        row.fire_control_mode = loadout.fire_control_mode.value
        await session.flush()
        for slot, part_id in loadout.equipped_part_ids.items():
            equipped = await session.get(LoadoutPartRecord, (loadout.id, slot.value))
            if equipped is None:
                session.add(
                    LoadoutPartRecord(
                        loadout_id=loadout.id,
                        slot=slot.value,
                        pilot_id=pilot_id,
                        part_id=part_id,
                    )
                )
            else:
                equipped.part_id = part_id
        for weapon in loadout.weapons:
            held = await session.get(
                LoadoutWeaponRecord, (loadout.id, weapon.hand.value)
            )
            if held is None:
                held = LoadoutWeaponRecord(
                    loadout_id=loadout.id,
                    hand=weapon.hand.value,
                    weapon_type=weapon.type.value,
                    name=weapon.name,
                    damage=weapon.damage,
                    cost_ap=weapon.cost_ap,
                    attack_range=weapon.range,
                    accuracy=weapon.accuracy,
                    weight=weapon.weight,
                )
                session.add(held)
    await session.flush()
    owned_keys = set(profile.owned_skill_keys)
    current_keys = set(
        (
            await session.scalars(
                select(PilotSkillRecord.skill_key).where(
                    PilotSkillRecord.pilot_id == pilot_id
                )
            )
        ).all()
    )
    for key in owned_keys - current_keys:
        session.add(PilotSkillRecord(pilot_id=pilot_id, skill_key=key))
    pending_levels = {choice.level for choice in profile.pending_skill_choices}
    existing_levels = set(
        (
            await session.scalars(
                select(PendingSkillChoiceRecord.level).where(
                    PendingSkillChoiceRecord.pilot_id == pilot_id
                )
            )
        ).all()
    )
    for level in pending_levels - existing_levels:
        session.add(PendingSkillChoiceRecord(pilot_id=pilot_id, level=level))
    if existing_levels - pending_levels:
        await session.execute(
            delete(PendingSkillChoiceRecord).where(
                PendingSkillChoiceRecord.pilot_id == pilot_id,
                PendingSkillChoiceRecord.level.in_(existing_levels - pending_levels),
            )
        )
