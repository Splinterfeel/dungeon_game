from enum import Enum

from pydantic import BaseModel


class CELL_TYPE(Enum):
    WALL = " # "
    EMPTY = "   "
    START_TEAM_1 = " S1 "
    START_TEAM_2 = " S2 "
    CHEST = " C "
    ENEMY = " E "
    EXIT = " X "
    PLAYER = " P "


class AttackType(BaseModel):
    cost: int = 5
    default_multiplier: float = 1.0


class Attack:
    SIMPLE = AttackType(cost=5, default_multiplier=1.0)
    HEAVY = AttackType(cost=8, default_multiplier=1.5)


class ActionPoints:
    ATTACK = 5
    HEAVY_ATTACK = 7
