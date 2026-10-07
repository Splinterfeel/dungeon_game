import random

import names
from pydantic import Field

from src.constants import Accuracy
from src.entities.base import Actor, CharacterStats, Inventory, Weapon, WeaponType


class Enemy(Actor):
    name: str = Field(default_factory=lambda: f"[e]{names.get_full_name()}")


def build_default_enemy(
    min_action_points: int,
    max_action_points: int,
) -> Enemy:
    return Enemy(
        stats=CharacterStats(
            health=random.randint(8, 12) * 10,
            melee_power=random.randint(0, 1) * 10,
            speed=3,
            view_distance=5,
            accuracy=Accuracy.DEFAULT_ENEMY_STATS_ACCURACY,
            action_points=random.randint(min_action_points, max_action_points),
        ),
        inventory=Inventory(
            weapons=[
                Weapon(
                    type=WeaponType.MELEE,
                    name="Повреждённый ударный модуль",
                    damage=30,
                    cost_ap=5,
                    range=1,
                    accuracy=Accuracy.DEFAULT_ENEMY_MELEE_WEAPON_ACCURACY,
                ),
                Weapon(
                    type=WeaponType.RANGED,
                    name="Ржавая мех-винтовка",
                    damage=40,
                    cost_ap=8,
                    range=4,
                    accuracy=Accuracy.DEFAULT_ENEMY_RANGED_WEAPON_ACCURACY,
                ),
            ]
        ),
    )
