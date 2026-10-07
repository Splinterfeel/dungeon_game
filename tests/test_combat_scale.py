"""Новые единицы HP/урона сохраняют пропорции сборок и цену действий."""

from importlib import import_module

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
import sqlalchemy as sa

from src.entities.base import Weapon
from src.mech.catalog import default_mech
from src.mech.presets import get_mech_preset_by_name


@pytest.mark.parametrize(
    "name,hp,melee,speed,damages,costs,ranges,weights",
    [
        ("SteelMan", 190, 40, 4, [60, 30], [6, 6], [1, 3], [8, 2]),
        ("Fireworks Mk. 1", 110, 0, 6, [50, 20], [8, 5], [5, 1], [5, 1]),
        ("StrikeForce", 90, 0, 3, [100, 20], [8, 4], [6, 1], [14, 2]),
    ],
)
def test_presets_use_scaled_combat_values_but_same_action_costs(
    name, hp, melee, speed, damages, costs, ranges, weights
):
    preset = get_mech_preset_by_name(name)
    stats = preset.mech.build_character_stats(action_points=10)
    assert stats.health == stats.max_health == hp
    assert stats.melee_power == melee
    assert stats.speed == speed
    assert stats.action_points == 10
    assert [weapon.damage for weapon in preset.weapons] == damages
    assert [weapon.cost_ap for weapon in preset.weapons] == costs
    assert [weapon.range for weapon in preset.weapons] == ranges
    assert [weapon.weight for weapon in preset.weapons] == weights
    for part in (
        preset.mech.torso,
        preset.mech.legs,
        preset.mech.arms_left,
        preset.mech.arms_right,
        preset.mech.head,
    ):
        assert part.max_health == part.current_health == 100


def test_default_mech_uses_same_combat_scale():
    stats = default_mech().build_character_stats(action_points=10)
    assert stats.health == stats.max_health == 150
    assert stats.melee_power == 20
    assert stats.speed == stats.view_distance == 5
    assert stats.action_points == 10


@pytest.mark.parametrize(
    "multiplier,expected", [(0.875, 44), (0.98, 49), (1, 50), (1.02, 51), (1.125, 56)]
)
def test_damage_rounds_after_variance_in_new_units(monkeypatch, multiplier, expected):
    def roll(low, high):
        assert (low, high) == (0.875, 1.125)
        return multiplier

    monkeypatch.setattr("src.entities.base.random.uniform", roll)
    weapon = Weapon(
        type="ranged",
        name="Проверка разброса",
        damage=50,
        cost_ap=8,
        range=5,
        accuracy=90,
    )
    assert weapon.roll_damage() == expected


def test_migration_preserves_unrelated_stats_and_scales_custom_saved_values():
    migration = import_module("migrations.versions.0003_combat_health_scale")
    metadata = sa.MetaData()
    catalog = sa.Table(
        "part_catalog",
        metadata,
        sa.Column("health", sa.Integer),
        sa.Column("melee_power", sa.Integer),
        sa.Column("max_health", sa.Integer),
        sa.Column("speed", sa.Integer),
    )
    instances = sa.Table(
        "part_instances",
        metadata,
        sa.Column("affix_stat", sa.String),
        sa.Column("affix_value", sa.Integer),
        sa.Column("affix_tier", sa.Integer),
    )
    weapons = sa.Table(
        "loadout_weapons",
        metadata,
        sa.Column("damage", sa.Integer),
        sa.Column("cost_ap", sa.Integer),
        sa.Column("attack_range", sa.Integer),
    )
    skills = sa.Table(
        "skill_catalog",
        metadata,
        sa.Column("skill_key", sa.String),
        sa.Column("description", sa.String),
        sa.Column("proc_chance", sa.Float),
    )
    engine = sa.create_engine("sqlite://")
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            catalog.insert(), dict(health=17, melee_power=3, max_health=11, speed=4)
        )
        connection.execute(
            instances.insert(),
            [
                dict(affix_stat="health", affix_value=2, affix_tier=3),
                dict(affix_stat="melee_power", affix_value=2, affix_tier=2),
                dict(affix_stat="accuracy", affix_value=8, affix_tier=2),
                dict(affix_stat="speed", affix_value=1, affix_tier=1),
            ],
        )
        connection.execute(weapons.insert(), dict(damage=7, cost_ap=6, attack_range=3))
        old_description = (
            "Шанс на атаку: +3 к силе удара для текущей атаки ближнего боя."
        )
        connection.execute(
            skills.insert(),
            dict(
                skill_key="heavy_strike", description=old_description, proc_chance=0.15
            ),
        )
        tables = (catalog, instances, weapons, skills)
        before = [connection.execute(sa.select(table)).all() for table in tables]
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            assert connection.execute(sa.select(catalog)).one() == (170, 30, 110, 4)
            assert connection.execute(sa.select(instances)).all() == [
                ("health", 20, 3),
                ("melee_power", 20, 2),
                ("accuracy", 8, 2),
                ("speed", 1, 1),
            ]
            assert connection.execute(sa.select(weapons)).one() == (70, 6, 3)
            skill = connection.execute(sa.select(skills)).one()
            assert skill.description == old_description.replace("+3 ", "+30 ")
            assert skill.proc_chance == 0.15
            migration.downgrade()
        assert [
            connection.execute(sa.select(table)).all() for table in tables
        ] == before
    engine.dispose()
