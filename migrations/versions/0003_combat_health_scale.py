"""HP, прочность и урон переходят на десятикратный масштаб."""

from alembic import op
import sqlalchemy as sa


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Меняем сохранённые числа ровно один раз, включая нестандартные детали
    # и оружие пилотов. AP, шанс/уровень аффикса и остальные статы не трогаем.
    op.execute(
        "UPDATE part_catalog SET health = health * 10, "
        "melee_power = melee_power * 10, max_health = max_health * 10"
    )
    op.execute(
        "UPDATE part_instances SET affix_value = affix_value * 10 "
        "WHERE affix_stat IN ('health', 'melee_power')"
    )
    op.execute("UPDATE loadout_weapons SET damage = damage * 10")
    op.execute(
        sa.text(
            "UPDATE skill_catalog SET description = :description "
            "WHERE skill_key = 'heavy_strike'"
        ).bindparams(
            description="Шанс на атаку: +30 к силе удара для текущей атаки ближнего боя."
        )
    )


def downgrade() -> None:
    op.execute(
        "UPDATE part_catalog SET health = health / 10, "
        "melee_power = melee_power / 10, max_health = max_health / 10"
    )
    op.execute(
        "UPDATE part_instances SET affix_value = affix_value / 10 "
        "WHERE affix_stat IN ('health', 'melee_power')"
    )
    op.execute("UPDATE loadout_weapons SET damage = damage / 10")
    op.execute(
        sa.text(
            "UPDATE skill_catalog SET description = :description "
            "WHERE skill_key = 'heavy_strike'"
        ).bindparams(
            description="Шанс на атаку: +3 к силе удара для текущей атаки ближнего боя."
        )
    )
