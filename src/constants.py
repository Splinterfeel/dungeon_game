from enum import Enum


class CELL_TYPE(Enum):
    WALL = " # "
    EMPTY = "   "
    START_TEAM_1 = " S1 "
    START_TEAM_2 = " S2 "
    CHEST = " C "
    ENEMY = " E "
    EXIT = " X "
    PLAYER = " P "
